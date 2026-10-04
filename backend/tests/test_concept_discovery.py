import json

from app.llm.base_provider import LLMResponse
from app.rag.concept_discovery import (
    ConceptDiscoveryEngine,
    ConceptDiscoveryResult,
)
from app.services.rag_service import RAGService


def test_concept_discovery_parser():
    engine = ConceptDiscoveryEngine()

    response = json.dumps(
        {
            "description": (
                "A search method that finds documents using keywords "
                "and how often terms occur"
            ),
            "concept": "BM25",
            "confidence": 0.94,
            "explanation": (
                "The evidence supports BM25 as a keyword-based "
                "sparse retrieval method using term statistics."
            ),
            "evidence": [
                "BM25 is a sparse retrieval method based on "
                "term matching and term statistics."
            ],
            "source_chunk_ids": ["chunk_9"],
        }
    )

    result = engine.parse_response(
        description=(
            "A search method that finds documents using keywords "
            "and how often terms occur"
        ),
        response_text=response,
    )

    assert isinstance(result, ConceptDiscoveryResult)
    assert result.concept == "BM25"
    assert result.confidence == 0.94
    assert result.source_chunk_ids == ["chunk_9"]


def test_concept_discovery_insufficient_evidence():
    engine = ConceptDiscoveryEngine()

    response = json.dumps(
        {
            "description": "Some completely unsupported concept",
            "concept": None,
            "confidence": 0.0,
            "explanation": "The supplied evidence is insufficient.",
            "evidence": [],
            "source_chunk_ids": [],
        }
    )

    result = engine.parse_response(
        description="Some completely unsupported concept",
        response_text=response,
    )

    assert result.concept is None
    assert result.confidence == 0.0
    assert result.source_chunk_ids == []


class FakeConceptLLM:
    def generate_structured(self, prompt):
        return LLMResponse(
            answer=json.dumps(
                {
                    "description": (
                        "A search method that finds documents using "
                        "keywords and how often terms occur"
                    ),
                    "concept": "BM25",
                    "confidence": 0.94,
                    "explanation": (
                        "The retrieved evidence supports BM25."
                    ),
                    "evidence": [
                        "BM25 is a sparse retrieval method."
                    ],
                    "source_chunk_ids": ["chunk_9"],
                }
            ),
            provider="fake",
            model="test",
            latency_ms=0.0,
            success=True,
        )


def test_rag_service_concept_discovery_integration():
    service = RAGService()
    service.llm = FakeConceptLLM()

    description = (
        "A search method that finds documents using keywords "
        "and how often terms occur"
    )

    result = service.discover_concept(description)

    assert isinstance(result, ConceptDiscoveryResult)
    assert result.concept == "BM25"
    assert result.confidence > 0.9
    assert result.source_chunk_ids