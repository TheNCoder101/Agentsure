"""Unit tests for claim extraction, the cheap pass, and the judge."""

from app.models import SourceDocument
from app.verify.cheap import check_claim
from app.verify.claims import extract_claims
from app.verify.judge import HeuristicJudge, JudgeVerdict, self_consistent_judge


def _docs(*texts: str) -> list[SourceDocument]:
    return [SourceDocument(id=f"doc-{i}", text=t) for i, t in enumerate(texts, 1)]


class TestClaimExtraction:
    def test_splits_sentences(self) -> None:
        claims = extract_claims("Revenue grew 12% in Q3. The board approved a buyback.")
        assert claims == ["Revenue grew 12% in Q3.", "The board approved a buyback."]

    def test_splits_compound_clauses(self) -> None:
        claims = extract_claims("Revenue grew 12% in Q3, and margins expanded to 40%.")
        assert len(claims) == 2

    def test_drops_trivial_fragments(self) -> None:
        assert extract_claims("Yes. Revenue grew twelve percent this quarter.") == [
            "Revenue grew twelve percent this quarter."
        ]

    def test_abbreviations_do_not_split(self) -> None:
        claims = extract_claims("Costs fell, e.g. hosting dropped sharply this year.")
        assert len(claims) == 1


class TestCheapPass:
    def test_grounded_claim_supported(self) -> None:
        result = check_claim(
            "Revenue increased 12% to $4.1M",
            _docs("Revenue for the quarter increased 12% year over year to $4.1M."),
        )
        assert result.supported
        assert result.source_id == "doc-1"
        assert result.score > 0.5

    def test_ungrounded_claim_flagged(self) -> None:
        result = check_claim(
            "The company opened an office in Antarctica",
            _docs("Revenue for the quarter increased 12% year over year to $4.1M."),
        )
        assert not result.supported
        assert result.flagged
        assert "insufficient evidence" in result.reason

    def test_number_mismatch_flagged(self) -> None:
        result = check_claim(
            "Revenue for the quarter increased 15% year over year",
            _docs("Revenue for the quarter increased 12% year over year to $4.1M."),
        )
        assert not result.supported
        assert "number mismatch" in result.reason
        assert "15" in result.reason

    def test_quarter_labels_are_not_numbers(self) -> None:
        result = check_claim(
            "Q3 revenue grew 12% to $4.1M",
            _docs("Revenue for the third quarter increased 12% year over year to $4.1M."),
        )
        assert result.supported, result.reason  # "Q3" must not trigger a number mismatch

    def test_fabricated_citation_flagged(self) -> None:
        result = check_claim(
            "The treatment reduced risk according to the trial [7]",
            _docs("The trial found the treatment reduced risk according to preliminary data."),
        )
        assert not result.supported
        assert "fabricated citation" in result.reason

    def test_present_citation_not_flagged(self) -> None:
        result = check_claim(
            "The treatment reduced risk according to the trial [7]",
            _docs("The trial found the treatment reduced risk [7] in preliminary data."),
        )
        assert result.supported

    def test_negated_claim_against_affirmative_source_flagged(self) -> None:
        result = check_claim(
            "Revenue did not increase this quarter",
            _docs("Revenue increased 12% this quarter."),
        )
        assert not result.supported
        assert "negation mismatch" in result.reason

    def test_affirmative_claim_against_negated_source_flagged(self) -> None:
        result = check_claim(
            "Revenue increased this quarter",
            _docs("Revenue did not increase this quarter."),
        )
        assert not result.supported
        assert "negation mismatch" in result.reason

    def test_negation_contraction_detected(self) -> None:
        result = check_claim(
            "Revenue wasn't up this quarter",
            _docs("Revenue was up sharply this quarter."),
        )
        assert not result.supported
        assert "negation mismatch" in result.reason

    def test_matching_negation_on_both_sides_not_flagged(self) -> None:
        result = check_claim(
            "The trial found no evidence of harm",
            _docs("The trial found no evidence of harm in the treatment group."),
        )
        assert result.supported

    def test_negation_elsewhere_in_unrelated_sentence_not_flagged(self) -> None:
        # "not" appears in the source, but not in the sentence that actually
        # matches the claim — must not spuriously trigger a negation flag.
        result = check_claim(
            "Revenue increased 12% to $4.1M",
            _docs(
                "The board did not comment on strategy. "
                "Revenue increased 12% to $4.1M this quarter."
            ),
        )
        assert result.supported

    def test_stemming_matches_tense_variants(self) -> None:
        # Isolates stemming specifically: without it, only "quarterly"/"costs"
        # overlap (2/4 = 0.5, below threshold). Stemming "declined" and
        # "declining" to the same root is what tips this over 0.55.
        result = check_claim(
            "Quarterly costs declined significantly",
            _docs("Quarterly costs are declining due to efficiency gains."),
        )
        assert result.supported, result.reason


class TestJudge:
    def test_heuristic_judge_confirms_unsupported(self) -> None:
        verdict = HeuristicJudge().judge(
            "The CEO resigned yesterday",
            _docs("Revenue increased 12% to $4.1M in the third quarter."),
        )
        assert not verdict.supported

    def test_heuristic_judge_rescues_supported(self) -> None:
        verdict = HeuristicJudge().judge(
            "Revenue increased 12%",
            _docs("Revenue increased 12%. Unrelated filler text follows here."),
        )
        assert verdict.supported

    def test_judge_does_not_split_decimal_amounts(self) -> None:
        verdict = HeuristicJudge().judge(
            "Revenue grew 12% to $4.1M",
            _docs("Revenue grew 12% to $4.1M, beating guidance. Unrelated sentence here."),
        )
        assert verdict.supported

    def test_self_consistency_majority(self) -> None:
        class FlipJudge:
            def __init__(self) -> None:
                self.calls = 0

            def judge(self, claim: str, sources: list[SourceDocument]) -> JudgeVerdict:
                self.calls += 1
                supported = self.calls != 2  # 2 of 3 samples say supported
                return JudgeVerdict(supported=supported, confidence=0.9, reason="r")

        verdict = self_consistent_judge(FlipJudge(), "claim", _docs("text"), samples=3)
        assert verdict.supported
        assert verdict.confidence < 0.9  # discounted by imperfect agreement
