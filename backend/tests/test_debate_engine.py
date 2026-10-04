from app.rag.debate_engine import (
    DebateEngine,
    DebateSide,
)


def sample_response():
    return """
    {
      "query": "Does hybrid retrieval improve RAG performance?",
      "topic": "Hybrid retrieval for RAG",
      "position_a": "Hybrid retrieval improves RAG performance",
      "position_b": "Hybrid retrieval does not necessarily improve RAG performance",
      "arguments": [
        {
          "side": "POSITION_A",
          "argument": "The supplied study reports improved retrieval performance.",
          "evidence": [
            "The study reports improved retrieval performance."
          ],
          "confidence": 0.91,
          "document": "sample_ieee.pdf",
          "page": 5,
          "chunk_id": "chunk_005"
        },
        {
          "side": "POSITION_B",
          "argument": "The evaluation was limited to one dataset.",
          "evidence": [
            "Evaluation was limited to one dataset."
          ],
          "confidence": 0.84,
          "document": "sample_ieee.pdf",
          "page": 6,
          "chunk_id": "chunk_006"
        }
      ],
      "rebuttals": [
        {
          "side": "POSITION_A",
          "target_argument": "The evaluation was limited to one dataset.",
          "rebuttal": "The supplied evidence reports improved retrieval performance despite the evaluation limitation.",
          "evidence": [
            "The study reports improved retrieval performance."
          ],
          "confidence": 0.78
        }
      ],
      "final_verdict": "The evidence supports improved retrieval performance, but the limited evaluation dataset reduces the strength of the conclusion.",
      "verdict_confidence": 0.88,
      "sources": [
        {
          "document": "sample_ieee.pdf",
          "page": 5,
          "chunk_id": "chunk_005"
        },
        {
          "document": "sample_ieee.pdf",
          "page": 6,
          "chunk_id": "chunk_006"
        }
      ]
    }
    """


def test_parse_response():
    engine = DebateEngine()

    report = engine.parse_response(
        query="Does hybrid retrieval improve RAG performance?",
        position_a="Hybrid retrieval improves RAG performance",
        position_b="Hybrid retrieval does not necessarily improve RAG performance",
        response_text=sample_response(),
    )

    assert report.query == "Does hybrid retrieval improve RAG performance?"
    assert len(report.arguments) == 2
    assert len(report.rebuttals) == 1
    assert report.verdict_confidence == 0.88
    assert len(report.sources) == 2


def test_argument_sides():
    engine = DebateEngine()

    report = engine.parse_response(
        query="Test debate",
        position_a="A",
        position_b="B",
        response_text=sample_response(),
    )

    assert report.arguments[0].side == DebateSide.POSITION_A
    assert report.arguments[1].side == DebateSide.POSITION_B


def test_json_fence_is_supported():
    engine = DebateEngine()

    response = "```json\n" + sample_response() + "\n```"

    report = engine.parse_response(
        query="Test debate",
        position_a="A",
        position_b="B",
        response_text=response,
    )

    assert report.final_verdict
    assert report.verdict_confidence == 0.88


def test_invalid_json():
    engine = DebateEngine()

    try:
        engine.parse_response(
            query="Test",
            position_a="A",
            position_b="B",
            response_text="not valid json",
        )
        assert False, "Expected ValueError"
    except ValueError as error:
        assert "invalid JSON" in str(error)


def test_empty_response():
    engine = DebateEngine()

    try:
        engine.parse_response(
            query="Test",
            position_a="A",
            position_b="B",
            response_text="",
        )
        assert False, "Expected ValueError"
    except ValueError as error:
        assert "empty response" in str(error)
