from dataclasses import dataclass

from _pytest.monkeypatch import MonkeyPatch

from app.rag.visual_answer import (
    VisualAnswerEngine,
    VisualType,
)

try:
    from app.rag.service import RAGService  # pyright: ignore[reportMissingImports]
except ImportError:  # pragma: no cover
    try:
        from app.services.rag_service import RAGService
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("RAGService import failed") from exc

try:
    from app.models.llm import LLMResponse  # pyright: ignore[reportMissingImports]
except ImportError:  # pragma: no cover
    try:
        from app.llm import LLMResponse  # type: ignore
    except ImportError:  # pragma: no cover

        @dataclass
        class LLMResponse:
            answer: str
            provider: str
            model: str
            latency_ms: float
            success: bool


def test_parse_table_visual():
    response = """
    {
        "visual_type": "TABLE",
        "title": "Retrieval Comparison",
        "description": "Comparison supported by the evidence.",
        "data": [
            {
                "label": "BM25",
                "value": "Lexical retrieval",
                "evidence": "BM25 uses lexical matching.",
                "document": "paper_a.pdf",
                "page": 2,
                "chunk_id": "chunk_1"
            },
            {
                "label": "FAISS",
                "value": "Vector retrieval",
                "evidence": "FAISS performs vector similarity search.",
                "document": "paper_b.pdf",
                "page": 4,
                "chunk_id": "chunk_2"
            }
        ],
        "elements": [],
        "edges": [],
        "sources": []
    }
    """

    result = VisualAnswerEngine().parse_response(
        "Compare BM25 and FAISS",
        response,
    )

    assert result.visual_type == VisualType.TABLE
    assert len(result.data) == 2
    assert result.data[0].label == "BM25"


def test_parse_bar_chart():
    response = """
    {
        "visual_type": "BAR_CHART",
        "title": "Accuracy Comparison",
        "description": "Reported accuracy values.",
        "data": [
            {
                "label": "Method A",
                "value": "92",
                "unit": "%",
                "evidence": "Method A achieved 92% accuracy.",
                "document": "paper.pdf",
                "page": 5,
                "chunk_id": "chunk_5"
            }
        ],
        "elements": [],
        "edges": [],
        "sources": []
    }
    """

    result = VisualAnswerEngine().parse_response(
        "Compare accuracy",
        response,
    )

    assert result.visual_type == VisualType.BAR_CHART
    assert result.data[0].value == "92"
    assert result.data[0].unit == "%"


def test_parse_concept_map():
    response = """
    {
        "visual_type": "CONCEPT_MAP",
        "title": "RAG Concepts",
        "description": "Concept relationships from the evidence.",
        "data": [],
        "elements": [
            {
                "id": "retrieval",
                "label": "Retrieval",
                "description": "Retrieval component.",
                "evidence": "The system retrieves relevant documents."
            },
            {
                "id": "generation",
                "label": "Generation",
                "description": "Generation component.",
                "evidence": "The system generates an answer from context."
            }
        ],
        "edges": [
            {
                "source": "retrieval",
                "target": "generation",
                "relationship": "feeds",
                "evidence": "Retrieved context is used for generation.",
                "confidence": 0.9
            }
        ],
        "sources": []
    }
    """

    result = VisualAnswerEngine().parse_response(
        "Explain the RAG pipeline",
        response,
    )

    assert result.visual_type == VisualType.CONCEPT_MAP
    assert len(result.elements) == 2
    assert len(result.edges) == 1


def test_parse_markdown_json():
    response = """
    ```json
    {
        "visual_type": "NONE",
        "title": "No Visual",
        "description": "The evidence does not support a visual.",
        "data": [],
        "elements": [],
        "edges": [],
        "sources": []
    }
    ```
    """

    result = VisualAnswerEngine().parse_response(
        "What is this?",
        response,
    )

    assert result.visual_type == VisualType.NONE


def test_invalid_json_rejected():
    try:
        VisualAnswerEngine().parse_response(
            "test",
            "not valid json",
        )
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_unknown_edge_rejected():
    response = """
    {
        "visual_type": "FLOWCHART",
        "title": "Invalid Flow",
        "description": "Invalid edge.",
        "data": [],
        "elements": [
            {
                "id": "step_a",
                "label": "Step A",
                "description": "",
                "evidence": "Step A exists."
            }
        ],
        "edges": [
            {
                "source": "step_a",
                "target": "missing",
                "relationship": "leads_to",
                "evidence": "Unsupported relationship.",
                "confidence": 0.8
            }
        ],
        "sources": []
    }
    """

    try:
        VisualAnswerEngine().parse_response(
            "test",
            response,
        )
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_build_prompt_contains_grounding_rules():
    prompt = VisualAnswerEngine().build_prompt(
        "Compare two methods",
        "Method A achieved 90% accuracy.",
    )

    assert "Never invent values" in prompt
    assert "ONLY" in prompt
    assert "supplied evidence" in prompt
    assert "BAR_CHART" in prompt
    assert "TABLE" in prompt


def test_visual_answer_returns_valid_repaired_response(monkeypatch: MonkeyPatch):
    service = RAGService()

    valid_response = """
    {
        "visual_type": "FLOWCHART",
        "title": "SAC-RAG",
        "description": "SAC-RAG uses context compression.",
        "data": [],
        "elements": [
            {
                "id": "step_1",
                "label": "Context Compression",
                "evidence": "SAC-RAG uses context compression."
            }
        ],
        "edges": [],
        "sources": [
            {
                "document": "paper.pdf",
                "page": 1,
                "chunk_id": "chunk_1"
            }
        ]
    }
    """

    class FakeRepairLLM:
        def __init__(self):
            self.calls = 0

        def generate_structured(self, prompt, system=None):
            self.calls += 1
            return LLMResponse(
                answer="not valid JSON" if self.calls == 1 else valid_response,
                provider="fake",
                model="test",
                latency_ms=0.0,
                success=True,
            )

    fake_llm = FakeRepairLLM()
    service.llm = fake_llm  # type: ignore

    monkeypatch.setattr(
        service.retriever,
        "search",
        lambda query, top_k=5: [
            {
                "document": "paper.pdf",
                "page": 1,
                "chunk_id": "chunk_1",
                "text": "SAC-RAG uses context compression.",
            }
        ],
    )

    result = service.generate_visual_answer("Explain SAC-RAG")

    assert result.visual_type.value == "FLOWCHART"
    assert len(result.elements) == 1
    assert result.elements[0].evidence == ("SAC-RAG uses context compression.")
    assert fake_llm.calls == 2
