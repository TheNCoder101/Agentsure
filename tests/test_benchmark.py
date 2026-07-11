"""Tests for the benchmark harness itself.

Judge *accuracy* against the labeled case set requires a live Anthropic call
and is run manually via `uv run python -m app.verify.benchmark` — never in
CI (CLAUDE.md rule 10: no network side-effects). These tests only prove the
harness scores a judge's answers correctly, using a scripted fake judge.
"""

from app.models import SourceDocument
from app.verify.benchmark import CASES, BenchmarkCase, run_benchmark
from app.verify.judge import JudgeVerdict


class _ScriptedJudge:
    def __init__(self, answers: dict[str, bool]) -> None:
        self._answers = answers

    def judge(self, claim: str, sources: list[SourceDocument]) -> JudgeVerdict:
        return JudgeVerdict(supported=self._answers[claim], confidence=1.0, reason="scripted")


def _case(name: str, claim: str, expected: bool) -> BenchmarkCase:
    return BenchmarkCase(
        name=name,
        claim=claim,
        sources=[SourceDocument(id="doc-1", text="text")],
        expected_supported=expected,
    )


class TestRunBenchmark:
    def test_perfect_judge_scores_100_percent(self) -> None:
        cases = [_case("a", "claim-a", True), _case("b", "claim-b", False)]
        judge = _ScriptedJudge({"claim-a": True, "claim-b": False})
        result = run_benchmark(judge, cases)
        assert result.accuracy == 1.0
        assert result.correct == 2
        assert result.misses == []

    def test_false_positive_counted(self) -> None:
        cases = [_case("a", "claim-a", False)]
        judge = _ScriptedJudge({"claim-a": True})
        result = run_benchmark(judge, cases)
        assert result.false_positives == 1
        assert result.false_negatives == 0
        assert result.misses == ["a"]

    def test_false_negative_counted(self) -> None:
        cases = [_case("a", "claim-a", True)]
        judge = _ScriptedJudge({"claim-a": False})
        result = run_benchmark(judge, cases)
        assert result.false_negatives == 1
        assert result.accuracy == 0.0

    def test_default_case_set_is_labeled_and_unique(self) -> None:
        assert len(CASES) >= 5
        names = [c.name for c in CASES]
        assert len(names) == len(set(names))
