"""
Milestone 1 / Step 3 tests: Document IQ transparency (M1-11).

These tests only import app.rag.scoring, so they run fast and need no server, LLM or indexes.
"""

from app.rag.scoring import calculate_document_iq

_COMPONENTS = (
    "extraction",
    "chunk_coverage",
    "embedding",
    "ocr_text_quality",
    "metadata_completeness",
)


def _full_metadata(**overrides):
    base = {
        "document": "paper.pdf",
        "title": "Paper",
        "pages": 10,
        "chunks": 20,
        "text_length": 5000,
        "embedding_status": True,
        "embedding_status_detail": "verified",
        "metadata_completeness": 1.0,
        "ocr_required": False,
        "ocr_quality": 1.0,
        "ocr_basis": "page_text_coverage",
    }
    base.update(overrides)
    return base


def test_fully_measured_document_scores_100_with_nothing_assumed():
    iq = calculate_document_iq(_full_metadata())

    assert iq["iq_score"] == 100.0
    assert iq["grade"] == "A+"
    assert iq["score_basis"]["measured"] == list(_COMPONENTS)
    assert iq["score_basis"]["assumed"] == []
    assert iq["score_basis"]["unavailable"] == []
    assert iq["points_without_direct_measurement"] == 0.0


def test_formula_and_weights_are_unchanged():
    # Same inputs as the original formula: 12.5 + 10 + 0 + 10 + 7.5 = 40
    iq = calculate_document_iq(
        {
            "pages": 2,
            "chunks": 2,
            "text_length": 2500,
            "embedding_status": False,
            "embedding_status_detail": "missing",
            "metadata_completeness": 0.5,
            "ocr_required": True,
            "ocr_quality": 0.5,
        }
    )
    assert iq["metrics"] == {
        "extraction_score": 12.5,
        "chunk_score": 10.0,
        "embedding_score": 0,
        "ocr_score": 10.0,
        "metadata_score": 7.5,
    }
    assert iq["iq_score"] == 40.0
    assert iq["grade"] == "D"
    assert iq["health"] == "Poor"


def test_displayed_component_scores_add_up_to_the_returned_score():
    for metadata in (
        _full_metadata(),
        _full_metadata(text_length=1234, chunks=7, metadata_completeness=0.71),
        {},
    ):
        iq = calculate_document_iq(metadata)
        total = sum(iq["components"][name]["score"] for name in _COMPONENTS)
        assert abs(total - iq["iq_score"]) < 0.02, (total, iq["iq_score"])
        # The legacy metrics block must agree with the new component breakdown
        assert iq["metrics"]["extraction_score"] == iq["components"]["extraction"]["score"]
        assert iq["metrics"]["chunk_score"] == iq["components"]["chunk_coverage"]["score"]
        assert iq["metrics"]["ocr_score"] == iq["components"]["ocr_text_quality"]["score"]
        assert iq["metrics"]["metadata_score"] == iq["components"]["metadata_completeness"]["score"]


def test_m1_11_incomplete_inputs_are_not_presented_as_measured():
    iq = calculate_document_iq({})

    # Formula result is unchanged: only the default OCR credit is awarded.
    assert iq["iq_score"] == 20.0

    basis = iq["score_basis"]
    assert basis["measured"] == []
    assert basis["assumed"] == ["ocr_text_quality"]
    assert set(basis["unavailable"]) == {
        "extraction",
        "chunk_coverage",
        "embedding",
        "metadata_completeness",
    }
    # All 20 points come from an assumption, and the report says so.
    assert iq["points_without_direct_measurement"] == 20.0
    assert iq["components"]["ocr_text_quality"]["basis"] == "assumed"
    assert "default" in iq["components"]["ocr_text_quality"]["note"]


def test_ocr_credit_is_assumed_when_no_page_data_was_available():
    iq = calculate_document_iq(_full_metadata(ocr_basis="assumed_no_page_data"))

    assert iq["components"]["ocr_text_quality"]["basis"] == "assumed"
    assert iq["points_without_direct_measurement"] == 20.0
    assert iq["iq_score"] == 100.0  # formula preserved; only the label changes


def test_ocr_measured_when_pages_were_inspected_and_some_were_empty():
    iq = calculate_document_iq(
        _full_metadata(ocr_required=True, ocr_quality=0.6, ocr_basis="page_text_coverage")
    )

    ocr = iq["components"]["ocr_text_quality"]
    assert ocr["basis"] == "measured"
    assert ocr["score"] == 12.0
    assert "proxy" in ocr["note"]


def test_legacy_metadata_without_ocr_basis_is_labelled_conservatively():
    legacy = _full_metadata()
    legacy.pop("ocr_basis")
    assert calculate_document_iq(legacy)["components"]["ocr_text_quality"]["basis"] == "assumed"

    legacy_required = _full_metadata(ocr_required=True, ocr_quality=0.5)
    legacy_required.pop("ocr_basis")
    assert calculate_document_iq(legacy_required)["components"]["ocr_text_quality"]["basis"] == "measured"


def test_embedding_basis_distinguishes_absent_from_unverifiable():
    verified = calculate_document_iq(_full_metadata())
    assert verified["components"]["embedding"]["basis"] == "measured"
    assert verified["components"]["embedding"]["score"] == 20

    # The check ran and found no index: a measured zero
    missing = calculate_document_iq(
        _full_metadata(embedding_status=False, embedding_status_detail="missing")
    )
    assert missing["components"]["embedding"]["basis"] == "measured"
    assert missing["components"]["embedding"]["score"] == 0

    # The check itself failed: the zero is "unavailable", not a measured result
    unverified = calculate_document_iq(
        _full_metadata(embedding_status=False, embedding_status_detail="unverified")
    )
    assert unverified["components"]["embedding"]["basis"] == "unavailable"
    assert unverified["components"]["embedding"]["score"] == 0
    assert "embedding" in unverified["score_basis"]["unavailable"]


def test_every_component_explains_how_it_is_calculated():
    iq = calculate_document_iq(_full_metadata())

    for name in _COMPONENTS:
        comp = iq["components"][name]
        assert comp["how_calculated"], name
        assert comp["max_score"] > 0
        assert comp["basis"] in ("measured", "assumed", "unavailable")
        assert isinstance(comp["inputs"], dict)

    # The limits of what is measured are stated, not hidden
    assert "authors" in iq["components"]["metadata_completeness"]["note"]
    assert "proxy" in iq["components"]["ocr_text_quality"]["how_calculated"] or (
        "proxy" in (iq["components"]["ocr_text_quality"]["note"] or "")
    )


def test_pipeline_block_keeps_old_keys_and_adds_new_ones():
    pipeline = calculate_document_iq(_full_metadata())["pipeline"]

    for key in ("pages", "chunks", "text_length", "chunk_density", "embedding_status", "metadata_completeness"):
        assert key in pipeline
    for key in ("embedding_status_detail", "ocr_required", "ocr_quality", "ocr_basis"):
        assert key in pipeline