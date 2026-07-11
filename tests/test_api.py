"""End-to-end API tests: /verify, /receipt/verify, keys, credits, landing."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.accounts import store
from app.main import app, get_judge
from app.models import SourceDocument
from app.verify.judge import JudgeVerdict
from tests.conftest import GROUNDED_SOURCE

GROUNDED_OUTPUT = (
    "Revenue for the third quarter increased 12% year over year to $4.1M. "
    "The board approved a $9M share buyback program."
)
UNGROUNDED_OUTPUT = "The company was founded in 1901 in Zurich by three brothers."
MIXED_OUTPUT = (
    "Revenue for the third quarter increased 12% year over year to $4.1M. "
    "The company opened an office in Antarctica last month."
)


def _verify(client: TestClient, key: str, output: str, rigor: str = "standard") -> Any:
    return client.post(
        "/verify",
        headers={"X-API-Key": key},
        json={
            "output": output,
            "source_documents": [{"id": "10q-2026", "text": GROUNDED_SOURCE}],
            "rigor_level": rigor,
        },
    )


class SpyJudge:
    def __init__(self) -> None:
        self.claims: list[str] = []

    def judge(self, claim: str, sources: list[SourceDocument]) -> JudgeVerdict:
        self.claims.append(claim)
        return JudgeVerdict(supported=False, confidence=0.9, reason="judge: not substantiated")


class TestVerifyContract:
    def test_grounded_output_supported_all_rigor_levels(
        self, client: TestClient, api_key: str
    ) -> None:
        for rigor in ("fast", "standard", "strict"):
            body = _verify(client, api_key, GROUNDED_OUTPUT, rigor).json()
            assert body["verdict"] == "supported"
            assert body["unsupported_claims"] == []
            assert len(body["per_claim_evidence"]) == 2
            assert all(e["supported"] for e in body["per_claim_evidence"])
            assert 0.0 <= body["confidence"] <= 1.0
            receipt = body["receipt"]
            assert receipt["rigor_level"] == rigor
            assert receipt["verdict"] == "supported"
            assert len(receipt["output_sha256"]) == 64
            assert len(receipt["signature"]) == 64

    def test_known_unsupported_claim_is_caught(self, client: TestClient, api_key: str) -> None:
        body = _verify(client, api_key, UNGROUNDED_OUTPUT).json()
        assert body["verdict"] != "supported"
        assert body["unsupported_claims"]

    def test_mixed_output_partially_supported(self, client: TestClient, api_key: str) -> None:
        body = _verify(client, api_key, MIXED_OUTPUT).json()
        assert body["verdict"] == "partially_supported"
        assert len(body["unsupported_claims"]) == 1

    def test_signing_key_never_in_response(self, client: TestClient, api_key: str) -> None:
        response = _verify(client, api_key, GROUNDED_OUTPUT)
        assert "test-signing-key" not in response.text


class TestEscalationCostControl:
    def _with_spy(self, client: TestClient, key: str, output: str, rigor: str) -> SpyJudge:
        spy = SpyJudge()
        app.dependency_overrides[get_judge] = lambda: spy
        try:
            assert _verify(client, key, output, rigor).status_code == 200
        finally:
            app.dependency_overrides.pop(get_judge)
        return spy

    def test_unflagged_claims_never_escalated(self, client: TestClient, api_key: str) -> None:
        spy = self._with_spy(client, api_key, MIXED_OUTPUT, "standard")
        assert len(spy.claims) == 1
        assert "Antarctica" in spy.claims[0]

    def test_fast_rigor_never_escalates(self, client: TestClient, api_key: str) -> None:
        spy = self._with_spy(client, api_key, MIXED_OUTPUT, "fast")
        assert spy.claims == []

    def test_strict_rigor_samples_judge(self, client: TestClient, api_key: str) -> None:
        spy = self._with_spy(client, api_key, MIXED_OUTPUT, "strict")
        assert len(spy.claims) == 3
        assert all("Antarctica" in c for c in spy.claims)


class TestReceiptEndpoint:
    def test_round_trip_receipt_is_valid(self, client: TestClient, api_key: str) -> None:
        receipt = _verify(client, api_key, GROUNDED_OUTPUT).json()["receipt"]
        assert client.post("/receipt/verify", json=receipt).json() == {
            "valid": True,
            "ed25519_valid": True,
        }

    def test_tampered_receipt_is_invalid(self, client: TestClient, api_key: str) -> None:
        receipt = _verify(client, api_key, UNGROUNDED_OUTPUT).json()["receipt"]
        tampered = dict(receipt, verdict="supported")  # launder the verdict
        assert client.post("/receipt/verify", json=tampered).json() == {
            "valid": False,
            "ed25519_valid": False,
        }

    def test_public_key_endpoint(self, client: TestClient) -> None:
        response = client.get("/.well-known/agentsure-receipt-key")
        assert response.status_code == 200
        body = response.json()
        assert body["algorithm"] == "ed25519"
        assert len(body["public_key_b64"]) > 0

    def test_receipt_verifiable_offline_with_published_key(
        self, client: TestClient, api_key: str
    ) -> None:
        from app.receipt import ed25519

        receipt = _verify(client, api_key, GROUNDED_OUTPUT).json()["receipt"]
        public_key = client.get("/.well-known/agentsure-receipt-key").json()["public_key_b64"]
        assert ed25519.verify(receipt, public_key) is True

    def test_tampered_receipt_fails_offline_verification(
        self, client: TestClient, api_key: str
    ) -> None:
        from app.receipt import ed25519

        receipt = _verify(client, api_key, GROUNDED_OUTPUT).json()["receipt"]
        public_key = client.get("/.well-known/agentsure-receipt-key").json()["public_key_b64"]
        tampered = dict(receipt, output_sha256="0" * 64)
        assert ed25519.verify(tampered, public_key) is False


class TestReceiptPersistence:
    def test_receipt_lookup_round_trips(self, client: TestClient, api_key: str) -> None:
        receipt = _verify(client, api_key, GROUNDED_OUTPUT).json()["receipt"]
        response = client.get(
            f"/receipts/{receipt['receipt_id']}", headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        assert response.json() == receipt

    def test_unknown_receipt_id_is_404(self, client: TestClient, api_key: str) -> None:
        response = client.get("/receipts/does-not-exist", headers={"X-API-Key": api_key})
        assert response.status_code == 404

    def test_receipt_not_visible_to_a_different_key(
        self, client: TestClient, api_key: str
    ) -> None:
        receipt = _verify(client, api_key, GROUNDED_OUTPUT).json()["receipt"]
        other_key = client.post("/keys", json={"email": "other@example.com"}).json()["api_key"]
        response = client.get(
            f"/receipts/{receipt['receipt_id']}", headers={"X-API-Key": other_key}
        )
        assert response.status_code == 404

    def test_list_receipts_scoped_to_key(self, client: TestClient, api_key: str) -> None:
        _verify(client, api_key, GROUNDED_OUTPUT)
        _verify(client, api_key, UNGROUNDED_OUTPUT)
        other_key = client.post("/keys", json={"email": "other2@example.com"}).json()["api_key"]
        _verify(client, other_key, GROUNDED_OUTPUT)

        response = client.get("/receipts", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        assert len(response.json()["receipts"]) == 2

    def test_list_receipts_as_csv(self, client: TestClient, api_key: str) -> None:
        receipt = _verify(client, api_key, GROUNDED_OUTPUT).json()["receipt"]
        response = client.get("/receipts?format=csv", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert receipt["receipt_id"] in response.text
        assert receipt["signature"] in response.text

    def test_receipt_pdf_export(self, client: TestClient, api_key: str) -> None:
        receipt = _verify(client, api_key, GROUNDED_OUTPUT).json()["receipt"]
        response = client.get(
            f"/receipts/{receipt['receipt_id']}/pdf", headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF-")

    def test_receipts_require_auth(self, client: TestClient) -> None:
        assert client.get("/receipts").status_code == 401
        assert client.get("/receipts/anything").status_code == 401

    def test_verify_returns_503_when_ed25519_key_missing(
        self, client: TestClient, api_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ED25519_SIGNING_KEY")
        assert _verify(client, api_key, GROUNDED_OUTPUT).status_code == 503


class TestAuthAndCredits:
    def test_missing_key_rejected(self, client: TestClient) -> None:
        response = client.post("/verify", json={})
        assert response.status_code == 401

    def test_invalid_key_rejected(self, client: TestClient) -> None:
        response = _verify(client, "vg-not-a-real-key", GROUNDED_OUTPUT)
        assert response.status_code == 401

    def test_credits_metered_by_rigor(self, client: TestClient, api_key: str) -> None:
        _verify(client, api_key, GROUNDED_OUTPUT, "fast")
        _verify(client, api_key, GROUNDED_OUTPUT, "strict")
        usage = client.get("/usage", headers={"X-API-Key": api_key}).json()
        assert usage["credits_used"] == 4  # fast=1 + strict=3
        assert usage["plan"] == "free"
        assert usage["credits_remaining"] == 996

    def test_exhausted_credits_return_402(self, client: TestClient, api_key: str) -> None:
        record = store.resolve_key(api_key)
        assert record is not None
        store.charge(record, 999)
        response = _verify(client, api_key, GROUNDED_OUTPUT, "standard")
        assert response.status_code == 402
        assert "credit limit" in response.json()["detail"]


class TestKeysAndSubscription:
    def test_key_created_with_prefix(self, client: TestClient) -> None:
        body = client.post("/keys", json={"email": "cto@bank.example"}).json()
        assert body["api_key"].startswith(store.KEY_PREFIX)
        assert body["plan"] == "free"
        assert body["monthly_credits"] == 1000

    def test_invalid_email_rejected(self, client: TestClient) -> None:
        assert client.post("/keys", json={"email": "not-an-email"}).status_code == 422

    def test_subscribe_upgrades_plan(self, client: TestClient, api_key: str) -> None:
        response = client.post(
            "/subscribe", headers={"X-API-Key": api_key}, json={"plan": "growth"}
        )
        assert response.json()["monthly_credits"] == 15000
        usage = client.get("/usage", headers={"X-API-Key": api_key}).json()
        assert usage["plan"] == "growth"

    def test_enterprise_is_sales_assisted(self, client: TestClient, api_key: str) -> None:
        response = client.post(
            "/subscribe", headers={"X-API-Key": api_key}, json={"plan": "enterprise"}
        )
        assert response.status_code == 422


class TestLanding:
    def test_landing_page_served(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        for marker in ("Create my API key", "Pricing", "Agentsure", "/receipt/verify"):
            assert marker in response.text
