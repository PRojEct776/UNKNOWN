"""
Tests for UNKNOWN Task P1-5:
1. Concept graph extraction drops unsupported nodes and ungrounded edges.
2. 'report.pdf mind map' runs only mindmap.
3. 'summery of X' routes to summary.
4. 'Run All' streams one event per feature.
5. Knowledge DNA and document DNA comparison.
6. Autocomplete for documents and features.
"""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.smart_router_service import (
    ALL_FEATURES,
    _verify_concept_in_chunks,
    _verify_relation_in_chunks,
    extract_concept_graph,
    extract_knowledge_dna_for_doc,
    compare_two_document_dna,
    detect_feature,
    fuzzy_match_documents,
    smart_route_query,
    autocomplete_smart_query,
    stream_run_all_features,
)


@pytest.fixture
def client():
    return TestClient(app)


# ===========================================================================
# 1. Concept Graph Grounding: Unsupported Nodes Dropped
# ===========================================================================

def test_unsupported_concept_node_is_dropped(tmp_path):
    """
    Test that hallucinated/unsupported nodes returned by LLM are strictly dropped,
    and edges connecting to dropped nodes are also pruned.
    """
    dummy_chunks = [
        {
            "chunk_id": "c1",
            "document": "quantum_test.pdf",
            "page": 1,
            "text": "Quantum computing utilizes superposition and entanglement for massive parallel state processing.",
        },
        {
            "chunk_id": "c2",
            "document": "quantum_test.pdf",
            "page": 2,
            "text": "Decoherence remains a primary limitation when scaling physical qubits.",
        },
    ]

    llm_mock_response = json.dumps({
        "nodes": [
            {"id": "n1", "label": "superposition", "cluster": "Theory", "relevance": 0.95, "importance": 0.9},
            {"id": "n2", "label": "entanglement", "cluster": "Theory", "relevance": 0.92, "importance": 0.88},
            {"id": "n3", "label": "qubits", "cluster": "Hardware", "relevance": 0.89, "importance": 0.85},
            {"id": "n4", "label": "Martian Warp Drive", "cluster": "SciFi", "relevance": 0.99, "importance": 0.99},  # Hallucinated!
        ],
        "edges": [
            {"source": "n1", "target": "n2", "relation": "COUPLED_WITH"},
            {"source": "n3", "target": "n4", "relation": "POWERS"},  # Connects to hallucinated node
        ],
    })

    def mock_llm(prompt: str, temp: float = 0.0) -> str:
        return llm_mock_response

    with patch("app.services.smart_router_service.get_document_chunks", return_value=dummy_chunks):
        with patch("app.services.smart_router_service.CONCEPT_GRAPH_CACHE_DIR", tmp_path):
            result = extract_concept_graph(
                document_name="quantum_test.pdf",
                llm_fn=mock_llm,
                retriever=MagicMock(),
            )

    kept_labels = [n["label"] for n in result["nodes"]]
    # Grounded nodes must be kept
    assert "superposition" in kept_labels
    assert "entanglement" in kept_labels
    assert "qubits" in kept_labels

    # Hallucinated / unsupported node MUST be dropped
    assert "Martian Warp Drive" not in kept_labels
    assert all(n["id"] != "n4" for n in result["nodes"])

    # Edges pointing to dropped node MUST be pruned
    assert len(result["edges"]) == 1
    assert result["edges"][0]["source"] == "n1"
    assert result["edges"][0]["target"] == "n2"
    assert result["edges"][0]["relation"] == "COUPLED_WITH"


# ===========================================================================
# 2. Smart Router: 'report.pdf mind map' runs ONLY mindmap
# ===========================================================================

def test_report_pdf_mind_map_runs_only_mindmap(client):
    """
    Query: 'report.pdf mind map'
    Must match document 'report.pdf', detect feature 'mindmap', and execute ONLY mindmap.
    """
    available_docs = ["report.pdf", "paper_attention.pdf", "deep_learning.pdf"]
    
    routing = smart_route_query(
        text="report.pdf mind map",
        available_docs=available_docs,
    )

    assert "report.pdf" in routing["matched_documents"]
    assert routing["detected_feature"] == "mindmap"
    assert routing["run_all"] is False

    # Test via API endpoint
    with patch("app.rag.utils.list_supported_documents") as mock_list_docs, patch(
        "app.rag.document_eligibility.get_user_authorized_documents",
        return_value={"report.pdf"},
    ):
        mock_file = MagicMock()
        mock_file.name = "report.pdf"
        mock_list_docs.return_value = [mock_file]

        with patch("app.services.smart_router_service.extract_concept_graph") as mock_mindmap:
            mock_mindmap.return_value = {
                "document": "report.pdf",
                "nodes": [{"id": "1", "label": "Neural Nets", "cluster": "AI", "relevance": 0.9, "importance": 0.8, "sources": []}],
                "edges": [],
                "from_cache": False,
            }

            resp = client.post("/smart-query", json={"text": "report.pdf mind map"})
            assert resp.status_code == 200
            data = resp.json()

            assert data["detected_feature"] == "mindmap"
            assert data["executed_feature"] == "mindmap"
            assert data["run_all"] is False
            assert "report.pdf" in data["matched_documents"]
            mock_mindmap.assert_called_once()


# ===========================================================================
# 3. Smart Router: 'summery of X' routes to summary
# ===========================================================================

def test_summery_of_x_routes_to_summary(client):
    """
    Typo query: 'summery of X'
    Must match synonym map / fuzzy classifier for 'summary'.
    """
    feature = detect_feature("summery of X")
    assert feature == "summary"

    routing = smart_route_query(
        text="summery of X",
        available_docs=["sample_x.pdf"],
    )
    assert routing["detected_feature"] == "summary"

    with patch("app.rag.utils.list_supported_documents") as mock_list_docs, patch(
        "app.rag.document_eligibility.get_user_authorized_documents",
        return_value={"sample_x.pdf"},
    ):
        mock_file = MagicMock()
        mock_file.name = "sample_x.pdf"
        mock_list_docs.return_value = [mock_file]

        with patch("app.services.overview_service.generate_document_overview") as mock_summary:
            mock_summary.return_value = {
                "document_name": "sample_x.pdf",
                "title": "Document X",
                "summary_sentences": [],
            }

            resp = client.post("/smart-query", json={"text": "summery of X", "document_ids": ["sample_x.pdf"]})
            assert resp.status_code == 200
            data = resp.json()
            assert data["detected_feature"] == "summary"
            assert data["executed_feature"] == "summary"


# ===========================================================================
# 4. 'Run All' streams one event per feature
# ===========================================================================

def test_run_all_streams_one_event_per_feature():
    """
    'Run All' query streams progress events for all features.
    Yields start and completion events per feature in ALL_FEATURES.
    """
    async def _collect():
        events = []
        async for item in stream_run_all_features(
            query="What are the main mechanisms?",
            document_names=["report.pdf"],
            rag_service=MagicMock(),
        ):
            events.append(item)
        return events

    events = asyncio.run(_collect())

    # Convert SSE lines into parsed event payloads
    parsed_events = []
    for line in events:
        if line.startswith("data: "):
            parsed_events.append(json.loads(line[6:].strip()))

    event_types = [e.get("event") for e in parsed_events]
    assert "run_all_start" in event_types
    assert "run_all_complete" in event_types

    # Verify that each feature in ALL_FEATURES has events
    completed_features = [
        e.get("feature") for e in parsed_events if e.get("event") == "feature_complete"
    ]
    for feat in ALL_FEATURES:
        assert feat in completed_features, f"Missing progress event for feature: {feat}"

    assert len(completed_features) == len(ALL_FEATURES)


def test_run_all_streaming_endpoint(client):
    """
    Test POST /smart-query with 'Run All' returns streaming SSE response.
    """
    with patch("app.rag.utils.list_supported_documents", return_value=[]):
        resp = client.post("/smart-query", json={"text": "Run All", "stream": True})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body_text = resp.text
        assert "run_all_start" in body_text
        for feat in ALL_FEATURES:
            assert feat in body_text
        assert "run_all_complete" in body_text


# ===========================================================================
# 5. Knowledge DNA and DNA Comparison Endpoints
# ===========================================================================

def test_extract_knowledge_dna_and_compare(tmp_path):
    """
    Verify DNA extraction and compare endpoint for two documents.
    """
    chunks_a = [{"chunk_id": "a1", "document": "doc_a.pdf", "page": 1, "text": "Transformer self-attention improves translation."}]
    chunks_b = [{"chunk_id": "b1", "document": "doc_b.pdf", "page": 1, "text": "Convolutional networks with self-attention for vision."}]

    dna_json_a = json.dumps({
        "concepts": ["Self-Attention", "Transformers"],
        "entities": [{"name": "BERT", "category": "Model", "frequency": 2}],
        "methods": ["Scaled Dot-Product", "Backpropagation"],
        "claims": ["Attention replaces recurrence"],
        "difficulty": "Advanced",
        "novelty": "High",
        "summary": "Attention mechanisms in NLP",
    })

    dna_json_b = json.dumps({
        "concepts": ["Self-Attention", "CNNs"],
        "entities": [{"name": "ResNet", "category": "Model", "frequency": 3}],
        "methods": ["Backpropagation", "Kernel Filtering"],
        "claims": ["Vision benefits from hybrid architectures"],
        "difficulty": "Intermediate",
        "novelty": "Medium",
        "summary": "Vision transformers and CNNs",
    })

    def mock_llm(prompt: str, temp: float = 0.0) -> str:
        if "doc_a" in prompt:
            return dna_json_a
        return dna_json_b

    with patch("app.services.smart_router_service.get_document_chunks") as mock_chunks:
        mock_chunks.side_effect = lambda doc: chunks_a if "doc_a" in doc else chunks_b
        with patch("app.services.smart_router_service.DNA_CACHE_DIR", tmp_path):
            dna_a = extract_knowledge_dna_for_doc("doc_a.pdf", mock_llm, MagicMock())
            dna_b = extract_knowledge_dna_for_doc("doc_b.pdf", mock_llm, MagicMock())

            comparison = compare_two_document_dna("doc_a.pdf", "doc_b.pdf", mock_llm, MagicMock())

            assert "Self-Attention" in comparison["shared_concepts"]
            assert "Scaled Dot-Product" not in comparison["shared_methods"]
            assert "Backpropagation" in comparison["shared_methods"]
            assert comparison["document_a"] == "doc_a.pdf"
            assert comparison["document_b"] == "doc_b.pdf"


# ===========================================================================
# 6. Autocomplete Endpoint
# ===========================================================================

def test_smart_query_autocomplete():
    """Verify autocomplete for documents and features."""
    docs = ["quantum_supremacy.pdf", "deep_rl_report.pdf"]
    
    # Feature prefix
    res_feat = autocomplete_smart_query("mind", docs)
    features = [f["feature"] for f in res_feat["features"]]
    assert "mindmap" in features

    # Document prefix
    res_doc = autocomplete_smart_query("quantum", docs)
    doc_names = [d["name"] for d in res_doc["documents"]]
    assert "quantum_supremacy.pdf" in doc_names
