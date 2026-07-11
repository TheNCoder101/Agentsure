"""Fixture-mocked tests for AnthropicJudge — no live network calls.

Fixtures model the shape of a real Anthropic Messages API response (content
blocks with `type`/`text`) so response parsing is exercised against a
realistic structure without hitting the network, per CLAUDE.md rule 10
(no network side-effects in tests).
"""

import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import pytest
from anthropic.types import TextBlock

from app.models import SourceDocument
from app.verify.judge import AnthropicJudge, _parse_judge_response


def _docs(*texts: str) -> list[SourceDocument]:
    return [SourceDocument(id=f"doc-{i}", text=t) for i, t in enumerate(texts, 1)]


def _fake_response(payload: dict[str, Any]) -> SimpleNamespace:
    block = TextBlock(type="text", text=json.dumps(payload))
    return SimpleNamespace(content=[block])


class _FakeMessages:
    def __init__(
        self, response: SimpleNamespace | None = None, error: Exception | None = None
    ) -> None:
        self._response = response
        self._error = error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


class _FakeClient:
    def __init__(
        self, response: SimpleNamespace | None = None, error: Exception | None = None
    ) -> None:
        self.messages = _FakeMessages(response, error)


class TestAnthropicJudgeFixtures:
    def test_supported_claim(self) -> None:
        response = _fake_response(
            {
                "supported": True,
                "confidence": 0.92,
                "reason": "source states the figure directly",
            }
        )
        judge = AnthropicJudge(client=_FakeClient(response))  # type: ignore[arg-type]
        verdict = judge.judge("Revenue grew 12%", _docs("Revenue grew 12% year over year."))
        assert verdict.supported
        assert verdict.confidence == pytest.approx(0.92)

    def test_unsupported_claim(self) -> None:
        response = _fake_response(
            {"supported": False, "confidence": 0.85, "reason": "no source mentions Antarctica"}
        )
        judge = AnthropicJudge(client=_FakeClient(response))  # type: ignore[arg-type]
        verdict = judge.judge(
            "The company opened an office in Antarctica", _docs("Revenue grew 12%.")
        )
        assert not verdict.supported
        assert "Antarctica" in verdict.reason

    def test_sends_claim_and_sources_in_prompt(self) -> None:
        response = _fake_response({"supported": True, "confidence": 0.7, "reason": "ok"})
        fake_client = _FakeClient(response)
        judge = AnthropicJudge(client=fake_client)  # type: ignore[arg-type]
        judge.judge("Revenue grew 12%", _docs("Revenue grew 12% year over year."))
        sent = fake_client.messages.calls[0]
        assert "Revenue grew 12%" in sent["messages"][0]["content"]
        assert "year over year" in sent["messages"][0]["content"]

    def test_confidence_clamped_to_unit_interval(self) -> None:
        response = _fake_response({"supported": True, "confidence": 5.0, "reason": "ok"})
        judge = AnthropicJudge(client=_FakeClient(response))  # type: ignore[arg-type]
        verdict = judge.judge("claim", _docs("source"))
        assert verdict.confidence == 1.0

    def test_api_error_fails_closed(self) -> None:
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        error = anthropic.APIConnectionError(request=request)
        judge = AnthropicJudge(client=_FakeClient(error=error))  # type: ignore[arg-type]
        verdict = judge.judge("claim", _docs("source"))
        assert not verdict.supported
        assert verdict.confidence == 0.0
        assert "judge unavailable" in verdict.reason


class TestParseJudgeResponse:
    def test_malformed_json_fails_closed(self) -> None:
        verdict = _parse_judge_response("not json at all")
        assert not verdict.supported
        assert verdict.confidence == 0.0
        assert "unparsable" in verdict.reason

    def test_missing_fields_fail_closed(self) -> None:
        verdict = _parse_judge_response(json.dumps({"supported": True}))
        assert not verdict.supported

    def test_valid_json_with_surrounding_whitespace(self) -> None:
        verdict = _parse_judge_response(
            "\n  " + json.dumps({"supported": True, "confidence": 0.6, "reason": "r"}) + "  \n"
        )
        assert verdict.supported
