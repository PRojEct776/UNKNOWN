from app.rag.knowledge_dna import (
    KnowledgeDNA,
    KnowledgeSignalType,
)


def sample_response():
    return """
    {
      "query": "RAG evaluation",
      "research_area": "Evaluation of retrieval-augmented generation systems",
      "core_topics": [
        "RAG evaluation",
        "retrieval performance"
      ],
      "key_concepts": [
        "hybrid retrieval",
        "recall"
      ],
      "methods": [
        "BM25",
        "FAISS"
      ],
      "findings": [
        "Hybrid retrieval improved retrieval performance."
      ],
      "limitations": [
        "Evaluation was limited to one dataset."
      ],
      "themes": [
        "retrieval quality"
      ],
      "signals": [
        {
          "type": "METHOD",
          "name": "BM25",
          "description": "BM25 was used as a retrieval method.",
          "evidence": [
            "The study uses BM25 for lexical retrieval."
          ],
          "confidence": 0.94,
          "document": "sample_ieee.pdf",
          "page": 4,
          "chunk_id": "chunk_004"
        },
        {
          "type": "FINDING",
          "name": "Improved retrieval",
          "description": "The study reports improved retrieval performance.",
          "evidence": [
            "Hybrid retrieval improved retrieval performance."
          ],
          "confidence": 0.91,
          "document": "sample_ieee.pdf",
          "page": 5,
          "chunk_id": "chunk_005"
        }
      ],
      "relationships": [
        {
          "source": "BM25",
          "target": "hybrid retrieval",
          "relationship": "contributes to",
          "evidence": "BM25 is used as part of the hybrid retrieval method.",
          "confidence": 0.87
        }
      ],
      "sources": [
        {
          "document": "sample_ieee.pdf",
          "page": 4,
          "chunk_id": "chunk_004"
        },
        {
          "document": "sample_ieee.pdf",
          "page": 5,
          "chunk_id": "chunk_005"
        }
      ]
    }
    """


def test_parse_response():
    engine = KnowledgeDNA()

    report = engine.parse_response(
        query="RAG evaluation",
        response_text=sample_response(),
    )

    assert report.query == "RAG evaluation"
    assert len(report.core_topics) == 2
    assert len(report.key_concepts) == 2
    assert len(report.methods) == 2
    assert len(report.findings) == 1
    assert len(report.limitations) == 1
    assert len(report.signals) == 2
    assert len(report.relationships) == 1
    assert len(report.sources) == 2


def test_signal_type():
    engine = KnowledgeDNA()

    report = engine.parse_response(
        query="RAG evaluation",
        response_text=sample_response(),
    )

    assert report.signals[0].type == KnowledgeSignalType.METHOD
    assert report.signals[1].type == KnowledgeSignalType.FINDING


def test_signal_traceability():
    engine = KnowledgeDNA()

    report = engine.parse_response(
        query="RAG evaluation",
        response_text=sample_response(),
    )

    signal = report.signals[0]

    assert signal.document == "sample_ieee.pdf"
    assert signal.page == 4
    assert signal.chunk_id == "chunk_004"
    assert signal.evidence


def test_relationship():
    engine = KnowledgeDNA()

    report = engine.parse_response(
        query="RAG evaluation",
        response_text=sample_response(),
    )

    relationship = report.relationships[0]

    assert relationship.source == "BM25"
    assert relationship.target == "hybrid retrieval"
    assert relationship.relationship == "contributes to"
    assert relationship.confidence == 0.87


def test_json_fence():
    engine = KnowledgeDNA()

    response = "```json\n" + sample_response() + "\n```"

    report = engine.parse_response(
        query="RAG evaluation",
        response_text=response,
    )

    assert report.research_area
    assert report.signals


def test_invalid_json():
    engine = KnowledgeDNA()

    try:
        engine.parse_response(
            query="RAG evaluation",
            response_text="not valid json",
        )
        assert False, "Expected ValueError"
    except ValueError as error:
        assert "invalid JSON" in str(error)
