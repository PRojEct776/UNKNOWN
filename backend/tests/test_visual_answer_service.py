import pytest

from app.llm.base_provider import LLMResponse
from app.services.rag_service import RAGService


class FakeFailedLLM:
    def generate_structured(self, prompt, system=None):
        return LLMResponse(
            answer="not valid JSON",
            provider="fake",
            model="test",
            latency_ms=0.0,
            success=True,
        )


def test_visual_answer_raises_when_repair_is_invalid(monkeypatch):
    service = RAGService()
    service.llm = FakeFailedLLM()
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

    with pytest.raises(ValueError, match="remained invalid after one repair attempt"):
        service.generate_visual_answer("Explain SAC-RAG")



def test_visual_answer_returns_valid_repaired_response(monkeypatch):
    service = RAGService()
    valid_response = """{
        "visual_type": "FLOWCHART",
        "title": "SAC-RAG",
        "description": "SAC-RAG uses context compression.",
        "data": [],
        "elements": [{
            "id": "step_1",
            "label": "Context Compression",
            "evidence": "SAC-RAG uses context compression."
        }],
        "edges": [],
        "sources": [{
            "document": "paper.pdf",
            "page": 1,
            "chunk_id": "chunk_1"
        }]
    }"""

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
    service.llm = fake_llm
    monkeypatch.setattr(
        service.retriever,
        "search",
        lambda query, top_k=5: [{
            "document": "paper.pdf",
            "page": 1,
            "chunk_id": "chunk_1",
            "text": "SAC-RAG uses context compression.",
        }],
    )

    result = service.generate_visual_answer("Explain SAC-RAG")

    assert result.visual_type.value == "FLOWCHART"
    assert len(result.elements) == 1
    assert result.elements[0].evidence == "SAC-RAG uses context compression."
    assert fake_llm.calls == 2
