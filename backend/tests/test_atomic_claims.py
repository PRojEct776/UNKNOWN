"""
Unit & Integration Tests for Atomic Claim Verification (Task A5)

Acceptance Criteria:
- wrong number -> removed
- paraphrase -> supported
- contradicting passage -> contradicted
- end-to-end test where final answer has zero unsupported claims
"""

from __future__ import annotations

import pytest

from app.api.schemas import AnswerResponse, Claim
from app.rag.atomic_claims import (
    build_answer_response,
    check_named_entity_presence,
    check_number_and_date_compatibility,
    classify_nli,
    extract_dates,
    extract_named_entities,
    extract_quantities,
    process_and_verify_claims,
    regenerate_claim_from_passage,
    split_into_atomic_claims,
    verify_atomic_claim,
)


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------

class FakeLLM:
    """Mock LLM for claim splitting and regeneration tests."""

    def __init__(self, responses: list[str | None]):
        self._responses = iter(responses)

    def generate(self, prompt: str, system: str | None = None):
        try:
            val = next(self._responses)
        except StopIteration:
            val = None

        class Resp:
            def __init__(self, answer: str | None):
                self.answer = answer or ""
                self.success = answer is not None
                self.error = "" if answer is not None else "failed"

        return Resp(val)


# ---------------------------------------------------------------------------
# 1. Number and Date Normalization & Matching
# ---------------------------------------------------------------------------

class TestNumberAndDateNormalization:
    def test_percentage_normalization_and_match(self):
        # 5% equals 0.05
        q_pct = extract_quantities("The error rate dropped by 5%.")
        q_dec = extract_quantities("The error rate dropped by 0.05.")
        assert len(q_pct) == 1
        assert len(q_dec) == 1
        assert q_pct[0].value == pytest.approx(0.05)
        assert q_dec[0].value == pytest.approx(0.05)

        ok, reason = check_number_and_date_compatibility(
            claim="The error rate dropped by 5%.",
            passage="The measured reduction was 0.05 in total error.",
        )
        assert ok is True
        assert reason == "compatible"

    def test_wrong_number_detected(self):
        # Claim claims 50%, passage says 5%
        ok, reason = check_number_and_date_compatibility(
            claim="The model improved throughput by 50%.",
            passage="The measured improvement was only 5%.",
        )
        assert ok is False
        assert reason == "wrong_number"

    def test_unit_conversion_kilometer_to_meter(self):
        # 5 km equals 5000 m
        ok, reason = check_number_and_date_compatibility(
            claim="The vehicle traveled 5 km.",
            passage="The sensor recorded 5000 meters traveled.",
        )
        assert ok is True
        assert reason == "compatible"

    def test_wrong_unit_scalar_conflict(self):
        # 10 km vs 5 km
        ok, reason = check_number_and_date_compatibility(
            claim="The range is 10 km.",
            passage="Maximum tested range was 5000 m.",
        )
        assert ok is False
        assert reason == "wrong_number"

    def test_date_iso_and_month_name_match(self):
        ok, reason = check_number_and_date_compatibility(
            claim="The release occurred on May 12, 2021.",
            passage="Published on 2021-05-12 in IEEE transactions.",
        )
        assert ok is True
        assert reason == "compatible"

    def test_conflicting_dates(self):
        ok, reason = check_number_and_date_compatibility(
            claim="The trial began in 2023.",
            passage="The project completed all trials in 2019.",
        )
        assert ok is False
        assert reason == "wrong_date"


# ---------------------------------------------------------------------------
# 2. Named Entity Recognition
# ---------------------------------------------------------------------------

class TestNamedEntityPresence:
    def test_entity_present_in_passage(self):
        claim = "The experiments were conducted using ImageNet and PyTorch."
        passage = "We benchmarked our architecture on the ImageNet dataset using a PyTorch pipeline."
        ok, missing = check_named_entity_presence(claim, passage)
        assert ok is True
        assert missing == []

    def test_hallucinated_entity_missing(self):
        claim = "The algorithm was evaluated on CIFAR-100 and AlphaFold."
        passage = "The model was trained exclusively on the CIFAR-100 image benchmark."
        ok, missing = check_named_entity_presence(claim, passage)
        assert ok is False
        assert any("alphafold" in m for m in missing)


# ---------------------------------------------------------------------------
# 3. Acceptance Criterion: Paraphrase -> Supported
# ---------------------------------------------------------------------------

class TestParaphraseSupported:
    def test_paraphrase_is_supported(self):
        passage = "The SAC-RAG framework reduces overall query latency by 35% on standard benchmarks."
        # Paraphrase using fraction 0.35 and semantic rewording
        claim = "On standard benchmarks, SAC-RAG decreases total latency by 0.35."
        result = verify_atomic_claim(claim, passage)
        assert result.label == "supported"


# ---------------------------------------------------------------------------
# 4. Acceptance Criterion: Contradicting Passage -> Contradicted
# ---------------------------------------------------------------------------

class TestContradictionDetection:
    def test_antonym_contradiction_is_labeled_contradicted(self):
        passage = "The optimization technique failed to converge and degraded performance across all trials."
        claim = "The optimization technique succeeded and improved performance across all trials."
        result = verify_atomic_claim(claim, passage)
        assert result.label == "contradicted"

    def test_wrong_number_causes_contradiction(self):
        passage = "Accuracy increased by 5% after fine-tuning."
        claim = "Accuracy increased by 50% after fine-tuning."
        result = verify_atomic_claim(claim, passage)
        assert result.label == "contradicted"


# ---------------------------------------------------------------------------
# 5. Acceptance Criterion: Wrong Number -> Removed
# ---------------------------------------------------------------------------

class TestWrongNumberRemoved:
    def test_wrong_number_removed_in_processing(self):
        passage = {"1": "The catalyst achieved a 5% yield improvement."}
        answer = "The catalyst achieved a 50% yield improvement."

        # Mock LLM that cannot regenerate anything factual (or returns None)
        llm = FakeLLM([None])
        surviving_claims, refined_answer = process_and_verify_claims(answer, passage, llm=llm)

        # Claim with wrong number must be removed!
        assert len(surviving_claims) == 0
        assert refined_answer == "Not found in available sources."


# ---------------------------------------------------------------------------
# 6. Regeneration & Single-Turn Re-Check
# ---------------------------------------------------------------------------

class TestClaimRegeneration:
    def test_unsupported_claim_regenerated_successfully(self):
        passage = "The algorithm operates with 50ms latency on edge hardware."
        bad_claim = "The algorithm operates with 10ms latency on edge hardware."

        # 1st call: split_into_atomic_claims (None -> fallback to sentence splitting)
        # 2nd call: regeneration -> returns factual grounded claim
        good_regen = "The algorithm operates with 50ms latency on edge hardware."
        llm = FakeLLM([None, good_regen])

        claims, refined = process_and_verify_claims(bad_claim, {"1": passage}, llm=llm)
        assert len(claims) == 1
        assert claims[0].label == "supported"
        assert "50ms" in claims[0].text

    def test_unsupported_claim_dropped_when_regeneration_fails(self):
        passage = "DNA storage encodes data into nucleotide sequences."
        hallucinated_claim = "Quantum computers store information in qubits."

        # LLM returns empty/NONE
        llm = FakeLLM(["NONE"])
        claims, refined = process_and_verify_claims(hallucinated_claim, {"1": passage}, llm=llm)
        assert len(claims) == 0
        assert refined == "Not found in available sources."


# ---------------------------------------------------------------------------
# 7. Acceptance Criterion: End-to-End Test Zero Unsupported Claims
# ---------------------------------------------------------------------------

class TestEndToEndZeroUnsupportedClaims:
    def test_end_to_end_zero_unsupported_claims_survive(self):
        passages = [
            {
                "chunk_id": "c1",
                "text": "FAISS delivers approximate nearest neighbor search with 95% recall.",
            },
            {
                "chunk_id": "c2",
                "text": "The experiment consumed 100 kilowatt-hours of electrical energy.",
            },
        ]

        # Multi-claim generated answer:
        # Claim 1 (valid paraphrase with 0.95 ratio): FAISS provides approximate nearest neighbor search with 0.95 recall.
        # Claim 2 (wrong number): The experiment consumed 500 kilowatt-hours of energy.
        # Claim 3 (hallucination): The algorithm was developed in collaboration with NASA and CERN.
        answer = (
            "FAISS provides approximate nearest neighbor search with 0.95 recall. "
            "The experiment consumed 500 kilowatt-hours of energy. "
            "The algorithm was developed in collaboration with NASA and CERN."
        )

        # Mock LLM to split claims, and for any regeneration attempt on bad claims, return NONE
        split_json = """
        {
            "claims": [
                {"text": "FAISS provides approximate nearest neighbor search with 0.95 recall.", "source_ids": ["c1"]},
                {"text": "The experiment consumed 500 kilowatt-hours of energy.", "source_ids": ["c2"]},
                {"text": "The algorithm was developed in collaboration with NASA and CERN.", "source_ids": ["c1", "c2"]}
            ]
        }
        """
        # 1st call: split_into_atomic_claims
        # 2nd call: regeneration for claim 2 -> returns NONE
        # 3rd call: regeneration for claim 3 -> returns NONE
        llm = FakeLLM([split_json, "NONE", "NONE"])

        response = build_answer_response(
            query="Tell me about FAISS performance and energy consumption.",
            answer=answer,
            passages=passages,
            llm=llm,
        )

        assert isinstance(response, AnswerResponse)
        # Verify that ONLY supported claims survive
        assert len(response.claims) == 1
        assert response.claims[0].label == "supported"
        assert "FAISS" in response.claims[0].text
        # Assert strictly ZERO unsupported or contradicted claims in the final answer
        unsupported = [c for c in response.claims if c.label != "supported"]
        assert len(unsupported) == 0, f"Expected zero unsupported claims, got: {unsupported}"

        # The summary reflects only the supported evidence
        assert "500 kilowatt-hours" not in response.summary
        assert "NASA" not in response.summary
        assert "FAISS" in response.summary
