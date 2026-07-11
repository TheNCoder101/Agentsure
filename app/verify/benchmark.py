"""Labeled accuracy benchmark for the judge.

A small, hand-labeled set of (claim, sources, expected `supported`) cases
covering grounded claims, ungrounded claims, and adversarial cases (near-miss
numbers, fabricated citations, unstated causal reasoning) — the kind of case
a naive token-overlap check gets wrong but a real judge should not.

Run against the real judge (requires ANTHROPIC_API_KEY):

    uv run python -m app.verify.benchmark

This is intentionally NOT run against a live judge in pytest — CI must never
make network calls (CLAUDE.md rule 10). `tests/test_benchmark.py` exercises
the harness itself with a deterministic scripted judge instead.
"""

from dataclasses import dataclass

from app.models import SourceDocument
from app.verify.judge import JudgeClient


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    claim: str
    sources: list[SourceDocument]
    expected_supported: bool


def _doc(id_: str, text: str) -> SourceDocument:
    return SourceDocument(id=id_, text=text)


CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        name="grounded-direct-statement",
        claim="Revenue increased 12% year over year to $4.1M.",
        sources=[
            _doc("doc-1", "Revenue for the third quarter increased 12% year over year to $4.1M.")
        ],
        expected_supported=True,
    ),
    BenchmarkCase(
        name="ungrounded-unrelated-fact",
        claim="The company opened an office in Antarctica.",
        sources=[
            _doc("doc-1", "Revenue for the third quarter increased 12% year over year to $4.1M.")
        ],
        expected_supported=False,
    ),
    BenchmarkCase(
        name="adversarial-near-miss-number",
        claim="Revenue increased 21% year over year.",
        sources=[_doc("doc-1", "Revenue increased 12% year over year to $4.1M.")],
        expected_supported=False,
    ),
    BenchmarkCase(
        name="adversarial-fabricated-citation",
        claim="The trial reduced risk according to the study [12].",
        sources=[_doc("doc-1", "The trial found the treatment reduced risk in preliminary data.")],
        expected_supported=False,
    ),
    BenchmarkCase(
        name="adversarial-unstated-causal-reasoning",
        claim="The board approved the buyback due to strong investor confidence.",
        sources=[_doc("doc-1", "The board approved a $9M share buyback program.")],
        expected_supported=False,
    ),
    BenchmarkCase(
        name="grounded-paraphrase",
        claim="Margins widened to 40 percent this quarter.",
        sources=[_doc("doc-1", "Gross margin expanded to 40% in the third quarter.")],
        expected_supported=True,
    ),
    BenchmarkCase(
        name="ungrounded-contradiction",
        claim="The CEO resigned yesterday.",
        sources=[_doc("doc-1", "Revenue increased 12% to $4.1M in the third quarter.")],
        expected_supported=False,
    ),
    BenchmarkCase(
        name="grounded-multi-source",
        claim="The board approved a $9M buyback after a strong quarter.",
        sources=[
            _doc("doc-1", "Revenue for the third quarter increased 12% year over year to $4.1M."),
            _doc("doc-2", "The board approved a $9M share buyback program."),
        ],
        expected_supported=True,
    ),
]


@dataclass(frozen=True)
class BenchmarkResult:
    total: int
    correct: int
    false_positives: int  # judge said supported, ground truth says unsupported
    false_negatives: int  # judge said unsupported, ground truth says supported
    accuracy: float
    misses: list[str]


def run_benchmark(judge: JudgeClient, cases: list[BenchmarkCase] = CASES) -> BenchmarkResult:
    correct = 0
    false_positives = 0
    false_negatives = 0
    misses: list[str] = []
    for case in cases:
        verdict = judge.judge(case.claim, case.sources)
        if verdict.supported == case.expected_supported:
            correct += 1
        else:
            misses.append(case.name)
            if verdict.supported:
                false_positives += 1
            else:
                false_negatives += 1
    total = len(cases)
    return BenchmarkResult(
        total=total,
        correct=correct,
        false_positives=false_positives,
        false_negatives=false_negatives,
        accuracy=correct / total if total else 0.0,
        misses=misses,
    )


def _main() -> None:  # pragma: no cover - manual invocation only, not run in CI
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY must be set to run the benchmark against the real judge."
        )
    from app.verify.judge import AnthropicJudge

    result = run_benchmark(AnthropicJudge())
    print(f"accuracy: {result.correct}/{result.total} ({result.accuracy:.1%})")
    print(f"false positives: {result.false_positives}  false negatives: {result.false_negatives}")
    if result.misses:
        print(f"missed cases: {', '.join(result.misses)}")


if __name__ == "__main__":  # pragma: no cover
    _main()
