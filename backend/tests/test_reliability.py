"""
Tests for Source Reliability and Conflict Detection (Task A6)

Acceptance Criteria:
- retracted source weight is 0
- two contradicting fixtures yield one Conflict with both sides
- weights deterministic
- warnings on retracted or preprint sources
"""

from __future__ import annotations

import math
import pytest

from app.api.schemas import Conflict
from app.rag.reliability import (
    compute_reliability,
    compute_reliability_breakdown,
    detect_conflicts,
    get_source_warnings,
    get_venue_quality,
    is_preprint_source,
    is_retracted_source,
)


# ---------------------------------------------------------------------------
# 1. Acceptance Criterion: Retracted source weight is 0
# ---------------------------------------------------------------------------

class TestRetractedSourceWeightZero:
    def test_retracted_flag_is_retracted(self):
        source = {
            "title": "Fabricated Cancer Research",
            "venue": "Nature",  # Top tier venue
            "year": 2025,       # Very recent
            "cites": 500,       # Highly cited
            "is_retracted": True,
        }
        weight = compute_reliability(source)
        assert weight == 0.0

    def test_retracted_flag_retracted_attribute(self):
        source = {
            "title": "Questionable Study",
            "venue": "Science",
            "year": 2024,
            "cites": 100,
            "retracted": True,
        }
        weight = compute_reliability(source)
        assert weight == 0.0

    def test_retracted_status_string(self):
        source = {
            "title": "Disputed Paper",
            "venue": "The Lancet",
            "year": 2023,
            "status": "Retracted",
        }
        weight = compute_reliability(source)
        assert weight == 0.0

    def test_nested_metadata_retracted(self):
        source = {
            "title": "Retracted in Metadata",
            "metadata": {"is_retracted": True},
        }
        weight = compute_reliability(source)
        assert weight == 0.0


# ---------------------------------------------------------------------------
# 2. Acceptance Criterion: Weights are deterministic & formula adheres to spec
# ---------------------------------------------------------------------------

class TestReliabilityDeterminismAndFormula:
    def test_weights_deterministic(self):
        source = {
            "title": "Attention Is All You Need",
            "venue": "NeurIPS",
            "year": 2017,
            "cites": 50000,
            "is_retracted": False,
        }
        weights = [compute_reliability(source) for _ in range(20)]
        assert len(set(weights)) == 1, "Expected identical weight across repeated runs"
        assert weights[0] > 0.0

    def test_formula_alpha_beta_gamma(self):
        # Manually compute with known values:
        # Nature -> V = 1.00
        # year 2026 -> age 0 -> R = exp(0) = 1.00
        # cites 1000 with cites_max 1000 -> C = log(1001)/log(1001) = 1.00
        # alpha=0.4, beta=0.3, gamma=0.3 -> w = 0.4*1.0 + 0.3*1.0 + 0.3*1.0 = 1.00
        source = {
            "venue": "Nature",
            "year": 2026,
            "cites": 1000,
        }
        w = compute_reliability(source, alpha=0.4, beta=0.3, gamma=0.3, cites_max=1000.0)
        assert w == pytest.approx(1.00, abs=1e-3)

    def test_preprint_venue_score_is_lower(self):
        preprint_source = {
            "venue": "arXiv",
            "year": 2024,
            "cites": 10,
        }
        top_journal_source = {
            "venue": "Nature",
            "year": 2024,
            "cites": 10,
        }
        w_prep = compute_reliability(preprint_source)
        w_top = compute_reliability(top_journal_source)
        assert w_prep < w_top

    def test_older_paper_recency_decay(self):
        new_source = {"venue": "IEEE", "year": 2025, "cites": 50}
        old_source = {"venue": "IEEE", "year": 2005, "cites": 50}
        w_new = compute_reliability(new_source)
        w_old = compute_reliability(old_source)
        assert w_old < w_new


# ---------------------------------------------------------------------------
# 3. Warnings on Retracted or Preprint Sources
# ---------------------------------------------------------------------------

class TestSourceWarnings:
    def test_retracted_warning(self):
        source = {
            "title": "Fraudulent Vaccines Study",
            "is_retracted": True,
        }
        warnings = get_source_warnings(source)
        assert any("RETRACTED" in w for w in warnings)

    def test_preprint_warning_arxiv(self):
        source = {
            "title": "Early Architecture Draft",
            "venue": "arXiv:2301.00000",
        }
        warnings = get_source_warnings(source)
        assert any("PREPRINT" in w for w in warnings)

    def test_preprint_warning_biorxiv(self):
        source = {
            "title": "Preliminary Gene Analysis",
            "venue": "bioRxiv",
        }
        warnings = get_source_warnings(source)
        assert any("PREPRINT" in w for w in warnings)

    def test_peer_reviewed_no_warning(self):
        source = {
            "title": "Deep Residual Learning for Image Recognition",
            "venue": "CVPR",
            "is_retracted": False,
        }
        warnings = get_source_warnings(source)
        assert warnings == []


# ---------------------------------------------------------------------------
# 4. Acceptance Criterion: Two contradicting fixtures yield one Conflict with both sides
# ---------------------------------------------------------------------------

class TestConflictDetection:
    def test_two_contradicting_fixtures_yield_one_conflict_with_both_sides(self):
        fixture_a = {
            "text": "The drug treatment demonstrated positive therapeutic efficacy and cured 90% of patients.",
            "source_ids": ["doc_1"],
            "metadata": {"year": 2024, "dataset": "Cohort A", "method": "Randomized Trial"},
        }
        fixture_b = {
            "text": "The drug treatment demonstrated negative therapeutic efficacy and failed across all patient trials.",
            "source_ids": ["doc_2"],
            "metadata": {"year": 2020, "dataset": "Cohort B", "method": "Observational Study"},
        }

        conflicts = detect_conflicts(
            claims=[fixture_a, fixture_b],
            topic="Drug Treatment Efficacy",
        )

        # Strictly ONE Conflict detected (no duplicate reverse pairs)
        assert len(conflicts) == 1
        c = conflicts[0]
        assert isinstance(c, Conflict)
        assert c.topic == "Drug Treatment Efficacy"

        # Contains both sides
        sides = {c.side_a, c.side_b}
        assert fixture_a["text"] in sides
        assert fixture_b["text"] in sides

        # Likely reason deduced from year, dataset, and method metadata
        assert c.likely_reason is not None
        assert "2024" in c.likely_reason or "Temporal" in c.likely_reason
        assert "Cohort" in c.likely_reason or "Observational" in c.likely_reason

    def test_non_contradicting_claims_yield_no_conflicts(self):
        claim_1 = {
            "text": "The transformer model achieved state-of-the-art results on language translation.",
            "source_ids": ["doc_1"],
        }
        claim_2 = {
            "text": "The architecture showed strong performance across several multilingual translation tasks.",
            "source_ids": ["doc_2"],
        }

        conflicts = detect_conflicts([claim_1, claim_2], topic="Translation Performance")
        assert len(conflicts) == 0

    def test_breakdown_contains_all_metrics_and_warnings(self):
        source = {
            "title": "Draft Preprint",
            "venue": "medRxiv",
            "year": 2022,
            "cites": 15,
        }
        b = compute_reliability_breakdown(source)
        assert "reliability" in b
        assert "V" in b
        assert "R" in b
        assert "C" in b
        assert b["is_preprint"] is True
        assert len(b["warnings"]) > 0
        assert any("PREPRINT" in w for w in b["warnings"])
