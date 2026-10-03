import pytest

from app.rag.contradiction_finder import (
    ClaimRelation,
    ContradictionFinder,
)


@pytest.fixture
def finder():
    return ContradictionFinder()


def test_build_contradiction_prompt(finder):
    prompt = finder.build_contradiction_prompt(
        query="Does Method A improve accuracy?",
        evidence=[
            {
                "document": "paper_a.pdf",
                "page": 3,
                "chunk_id": "chunk_1",
                "text": "Method A improves accuracy by 12%.",
            },
            {
                "document": "paper_b.pdf",
                "page": 7,
                "chunk_id": "chunk_8",
                "text": "Method A does not improve accuracy.",
            },
        ],
    )

    assert "Does Method A improve accuracy?" in prompt
    assert "Method A improves accuracy by 12%." in prompt
    assert "Method A does not improve accuracy." in prompt
    assert "CONTRADICTS" in prompt


def test_parse_supported_relationship(finder):
    response = """
    {
        "claims": [
            {
                "claim": "Method A improves accuracy.",
                "evidence": "Method A improves accuracy by 12%.",
                "document": "paper_a.pdf",
                "page": 3,
                "chunk_id": "chunk_1"
            },
            {
                "claim": "Method B improves accuracy.",
                "evidence": "Method B improves accuracy by 10%.",
                "document": "paper_b.pdf",
                "page": 4,
                "chunk_id": "chunk_2"
            }
        ],
        "relationships": [
            {
                "claim_a": {
                    "claim": "Method A improves accuracy.",
                    "evidence": "Method A improves accuracy by 12%.",
                    "document": "paper_a.pdf",
                    "page": 3,
                    "chunk_id": "chunk_1"
                },
                "claim_b": {
                    "claim": "Method B improves accuracy.",
                    "evidence": "Method B improves accuracy by 10%.",
                    "document": "paper_b.pdf",
                    "page": 4,
                    "chunk_id": "chunk_2"
                },
                "relation": "SUPPORTS",
                "confidence": 0.82,
                "explanation": "Both claims report improved accuracy."
            }
        ],
        "contradictions_found": 0
    }
    """

    report = finder.parse_response(
        query="Compare the methods.",
        response_text=response,
    )

    assert len(report.claims) == 2
    assert len(report.relationships) == 1
    assert report.relationships[0].relation == ClaimRelation.SUPPORTS
    assert report.contradictions_found == 0


def test_parse_contradiction(finder):
    response = """
    {
        "claims": [
            {
                "claim": "Method A improves accuracy.",
                "evidence": "Method A improves accuracy by 12%.",
                "document": "paper_a.pdf",
                "page": 3,
                "chunk_id": "chunk_1"
            },
            {
                "claim": "Method A does not improve accuracy.",
                "evidence": "Method A does not improve accuracy.",
                "document": "paper_b.pdf",
                "page": 7,
                "chunk_id": "chunk_8"
            }
        ],
        "relationships": [
            {
                "claim_a": {
                    "claim": "Method A improves accuracy.",
                    "evidence": "Method A improves accuracy by 12%.",
                    "document": "paper_a.pdf",
                    "page": 3,
                    "chunk_id": "chunk_1"
                },
                "claim_b": {
                    "claim": "Method A does not improve accuracy.",
                    "evidence": "Method A does not improve accuracy.",
                    "document": "paper_b.pdf",
                    "page": 7,
                    "chunk_id": "chunk_8"
                },
                "relation": "CONTRADICTS",
                "confidence": 0.94,
                "explanation": "The claims make opposing statements."
            }
        ],
        "contradictions_found": 1
    }
    """

    report = finder.parse_response(
        query="Does Method A improve accuracy?",
        response_text=response,
    )

    assert report.contradictions_found == 1
    assert report.relationships[0].relation == ClaimRelation.CONTRADICTS
    assert report.relationships[0].confidence == 0.94
    assert report.relationships[0].claim_a.evidence
    assert report.relationships[0].claim_b.evidence


def test_parse_qualifies_relationship(finder):
    response = """
    {
        "claims": [
            {
                "claim": "Method A improves accuracy.",
                "evidence": "Method A improves accuracy.",
                "document": "paper_a.pdf",
                "page": 3,
                "chunk_id": "chunk_1"
            },
            {
                "claim": "Method A improves accuracy only on dataset X.",
                "evidence": "Method A improves accuracy only on dataset X.",
                "document": "paper_b.pdf",
                "page": 5,
                "chunk_id": "chunk_4"
            }
        ],
        "relationships": [
            {
                "claim_a": {
                    "claim": "Method A improves accuracy.",
                    "evidence": "Method A improves accuracy.",
                    "document": "paper_a.pdf",
                    "page": 3,
                    "chunk_id": "chunk_1"
                },
                "claim_b": {
                    "claim": "Method A improves accuracy only on dataset X.",
                    "evidence": "Method A improves accuracy only on dataset X.",
                    "document": "paper_b.pdf",
                    "page": 5,
                    "chunk_id": "chunk_4"
                },
                "relation": "QUALIFIES",
                "confidence": 0.91,
                "explanation": "The second claim adds a condition."
            }
        ],
        "contradictions_found": 0
    }
    """

    report = finder.parse_response(
        query="Compare Method A findings.",
        response_text=response,
    )

    assert report.relationships[0].relation == ClaimRelation.QUALIFIES
    assert report.contradictions_found == 0


def test_parse_unrelated_relationship(finder):
    response = """
    {
        "claims": [
            {
                "claim": "Method A improves accuracy.",
                "evidence": "Method A improves accuracy.",
                "document": "paper_a.pdf",
                "page": 3,
                "chunk_id": "chunk_1"
            },
            {
                "claim": "The dataset contains 500 samples.",
                "evidence": "The dataset contains 500 samples.",
                "document": "paper_b.pdf",
                "page": 2,
                "chunk_id": "chunk_3"
            }
        ],
        "relationships": [
            {
                "claim_a": {
                    "claim": "Method A improves accuracy.",
                    "evidence": "Method A improves accuracy.",
                    "document": "paper_a.pdf",
                    "page": 3,
                    "chunk_id": "chunk_1"
                },
                "claim_b": {
                    "claim": "The dataset contains 500 samples.",
                    "evidence": "The dataset contains 500 samples.",
                    "document": "paper_b.pdf",
                    "page": 2,
                    "chunk_id": "chunk_3"
                },
                "relation": "UNRELATED",
                "confidence": 0.97,
                "explanation": "The claims address different subjects."
            }
        ],
        "contradictions_found": 0
    }
    """

    report = finder.parse_response(
        query="Analyze the evidence.",
        response_text=response,
    )

    assert report.relationships[0].relation == ClaimRelation.UNRELATED
    assert report.contradictions_found == 0


def test_parse_markdown_json(finder):
    response = """
    ```json
    {
        "claims": [],
        "relationships": [],
        "contradictions_found": 0
    }
    ```
    """

    report = finder.parse_response(
        query="Test query.",
        response_text=response,
    )

    assert report.claims == []
    assert report.relationships == []
    assert report.contradictions_found == 0


def test_invalid_relationship_raises_error(finder):
    response = """
    {
        "claims": [],
        "relationships": [
            {
                "claim_a": {
                    "claim": "A",
                    "evidence": "Evidence A.",
                    "document": "a.pdf",
                    "page": 1,
                    "chunk_id": "chunk_1"
                },
                "claim_b": {
                    "claim": "B",
                    "evidence": "Evidence B.",
                    "document": "b.pdf",
                    "page": 2,
                    "chunk_id": "chunk_2"
                },
                "relation": "MAGICALLY_CONTRADICTS",
                "confidence": 0.9,
                "explanation": "Invalid relationship."
            }
        ],
        "contradictions_found": 0
    }
    """

    with pytest.raises(ValueError, match="Invalid claim relationship"):
        finder.parse_response(
            query="Test query.",
            response_text=response,
        )


def test_invalid_json_raises_error(finder):
    with pytest.raises(
        ValueError,
        match="invalid contradiction analysis JSON",
    ):
        finder.parse_response(
            query="Test query.",
            response_text="This is not JSON.",
        )


def test_contradiction_count_is_calculated_from_relationships(finder):
    response = """
    {
        "claims": [],
        "relationships": [
            {
                "claim_a": {
                    "claim": "A",
                    "evidence": "Evidence A.",
                    "document": "a.pdf",
                    "page": 1,
                    "chunk_id": "chunk_1"
                },
                "claim_b": {
                    "claim": "B",
                    "evidence": "Evidence B.",
                    "document": "b.pdf",
                    "page": 2,
                    "chunk_id": "chunk_2"
                },
                "relation": "CONTRADICTS",
                "confidence": 0.9,
                "explanation": "Conflict."
            },
            {
                "claim_a": {
                    "claim": "C",
                    "evidence": "Evidence C.",
                    "document": "c.pdf",
                    "page": 1,
                    "chunk_id": "chunk_3"
                },
                "claim_b": {
                    "claim": "D",
                    "evidence": "Evidence D.",
                    "document": "d.pdf",
                    "page": 2,
                    "chunk_id": "chunk_4"
                },
                "relation": "QUALIFIES",
                "confidence": 0.8,
                "explanation": "Qualification."
            }
        ],
        "contradictions_found": 999
    }
    """

    report = finder.parse_response(
        query="Test query.",
        response_text=response,
    )

    assert report.contradictions_found == 1
