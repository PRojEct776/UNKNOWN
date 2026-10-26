"""M2: concept graph data-integrity tests."""
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.schemas import ConceptGraphResponse
from app.main import app
from app.services import smart_router_service as srs

DOC = "paper.pdf"

CHUNKS = [
    {"document": DOC, "chunk_id": "c1", "page": 2,
     "text": "The Transformer uses self-attention to model dependencies."},
    {"document": DOC, "chunk_id": "c2", "page": 3,
     "text": "We evaluate translation quality with BLEU. Dropout is applied."},
    {"document": DOC, "chunk_id": "c3",
     "text": "Beam search is used for decoding, as the authors said."},
]


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def __call__(self, prompt, temperature=0.0):
        self.calls += 1
        return self.payload if isinstance(self.payload, str) else json.dumps(self.payload)


class BoomLLM:
    def __call__(self, prompt, temperature=0.0):
        raise RuntimeError("LLM down")


def _nodes(*labels):
    return [{"id": f"n{i + 1}", "label": lab, "cluster": "Method"} for i, lab in enumerate(labels)]


@pytest.fixture
def env(monkeypatch, tmp_path):
    holder = {"chunks": CHUNKS}
    monkeypatch.setattr(srs, "get_document_chunks", lambda name: holder["chunks"])
    monkeypatch.setattr(srs, "CONCEPT_GRAPH_CACHE_DIR", tmp_path)
    return holder


def _run(payload, llm=None):
    llm = llm or FakeLLM(payload)
    return srs.extract_concept_graph(DOC, llm, None), llm


# ---------------- nodes ----------------

def test_unsupported_nodes_are_dropped(env):
    result, _ = _run({"nodes": _nodes("Transformer", "Quantum Flux"), "edges": []})
    assert [n["label"] for n in result["nodes"]] == ["Transformer"]
    assert result["extraction"]["dropped_nodes"] == 1
    assert result["extraction"]["method"] == "llm"


def test_scores_are_never_fabricated(env):
    nodes = [{"id": "n1", "label": "Transformer", "relevance": 0.95, "importance": 0.9}]
    result, _ = _run({"nodes": nodes, "edges": []})
    node = result["nodes"][0]
    assert node["relevance"] is None
    assert node["importance"] is None
    assert node["mention_count"] == 1  # measured: only chunk c1 contains it
    assert node["origin"] == "llm"


def test_label_matching_is_whole_word(env):
    # "ai" occurs inside "said" but is not a mention of the concept.
    result, _ = _run({"nodes": _nodes("ai", "Self-Attention"), "edges": []})
    assert [n["label"] for n in result["nodes"]] == ["Self-Attention"]


def test_duplicate_nodes_are_deduplicated(env):
    nodes = [
        {"id": "n1", "label": "Self-Attention"},
        {"id": "n2", "label": "self attention"},   # same label after normalisation
        {"id": "n1", "label": "Transformer"},      # duplicate id
    ]
    result, _ = _run({"nodes": nodes, "edges": []})
    assert [n["label"] for n in result["nodes"]] == ["Self-Attention"]
    assert result["extraction"]["dropped_nodes"] == 2


def test_unknown_page_stays_none_and_sources_stay_in_document(env):
    result, _ = _run({"nodes": _nodes("Transformer", "Beam search"), "edges": []})
    by_label = {n["label"]: n for n in result["nodes"]}
    assert by_label["Transformer"]["sources"][0]["page"] == 2
    assert by_label["Beam search"]["sources"][0]["page"] is None
    for node in result["nodes"]:
        assert all(s["document"] == DOC for s in node["sources"])


# ---------------- edges ----------------

def test_edges_require_both_concepts_in_one_chunk(env):
    edges = [
        # "uses" and Transformer share chunk c1, but BLEU is in c2: unsupported
        {"source": "n1", "target": "n3", "relation": "USES"},
        {"source": "n1", "target": "n99", "relation": "USES"},  # missing node
        {"source": "n1", "target": "n1", "relation": "USES"},   # self edge
        {"source": "n1", "target": "n2", "relation": "USES"},   # supported
    ]
    result, _ = _run({"nodes": _nodes("Transformer", "Self-Attention", "BLEU"), "edges": edges})
    assert [(e["source"], e["target"]) for e in result["edges"]] == [("n1", "n2")]
    assert result["extraction"]["dropped_edges"] == 3


def test_edge_evidence_status_reflects_evidence(env):
    edges = [
        {"source": "n1", "target": "n2", "relation": "USES"},       # word "uses" in c1
        {"source": "n1", "target": "n2", "relation": "OPTIMIZES"},  # word absent
    ]
    result, _ = _run({"nodes": _nodes("Transformer", "Self-Attention"), "edges": edges})
    status = {e["relation"]: e["evidence_status"] for e in result["edges"]}
    assert status == {"USES": "relation_term_present", "OPTIMIZES": "co_occurrence"}
    for edge in result["edges"]:
        assert edge["sources"] and edge["sources"][0]["chunk_id"] == "c1"


# ---------------- fallback and cache ----------------

def test_fallback_is_labelled_edgeless_and_not_cached(env, tmp_path):
    result, _ = _run(None, llm=BoomLLM())
    assert result["extraction"]["method"] == "heuristic_fallback"
    assert result["edges"] == []
    assert len(result["nodes"]) > 0
    assert all(n["origin"] == "heuristic" for n in result["nodes"])
    assert all(n["relevance"] is None and n["importance"] is None for n in result["nodes"])
    assert list(tmp_path.glob("*_graph.json")) == []


def test_cache_hit_then_content_change_regenerates(env, tmp_path):
    llm = FakeLLM({"nodes": _nodes("Transformer"), "edges": []})
    first = srs.extract_concept_graph(DOC, llm, None)
    assert first["from_cache"] is False
    assert (tmp_path / "paper_graph.json").exists()

    second = srs.extract_concept_graph(DOC, llm, None)
    assert second["from_cache"] is True
    assert llm.calls == 1

    changed = [dict(c) for c in CHUNKS]
    changed[0]["text"] = "The Transformer uses attention to model dependencies."
    env["chunks"] = changed
    third = srs.extract_concept_graph(DOC, llm, None)
    assert third["from_cache"] is False
    assert llm.calls == 2


def test_cache_with_old_schema_version_is_ignored(env, tmp_path):
    stale = {
        "document": DOC,
        "nodes": [{"id": "x", "label": "STALE"}],
        "edges": [],
        "schema_version": 1,
        "content_hash": srs._chunks_fingerprint(CHUNKS),
    }
    (tmp_path / "paper_graph.json").write_text(json.dumps(stale), encoding="utf-8")
    llm = FakeLLM({"nodes": _nodes("Transformer"), "edges": []})
    result = srs.extract_concept_graph(DOC, llm, None)
    assert result["from_cache"] is False
    assert [n["label"] for n in result["nodes"]] == ["Transformer"]
    assert llm.calls == 1


# ---------------- honest empty states ----------------

def test_empty_state_when_document_has_no_indexed_content(env):
    env["chunks"] = []
    result, llm = _run({"nodes": _nodes("Transformer"), "edges": []})
    assert result["status"] == "empty"
    assert result["empty_reason"] == "no_indexed_content"
    assert result["nodes"] == [] and result["edges"] == []
    assert llm.calls == 0


def test_empty_state_when_no_concept_is_grounded(env):
    result, _ = _run({"nodes": _nodes("Quantum Flux"), "edges": []})
    assert result["status"] == "empty"
    assert result["empty_reason"] == "no_grounded_concepts"
    assert result["nodes"] == []


def test_real_output_validates_against_response_model(env):
    edges = [{"source": "n1", "target": "n2", "relation": "USES"}]
    result, _ = _run({"nodes": _nodes("Transformer", "Self-Attention"), "edges": edges})
    response = ConceptGraphResponse(**result)
    assert response.status == "ok" and response.empty_reason is None
    assert response.nodes[0].relevance is None
    assert response.edges[0].evidence_status == "relation_term_present"
    assert response.extraction.chunks_total == 3


# ---------------- route authorization ----------------

client = TestClient(app)
AUTH_TARGET = "app.rag.document_eligibility.get_user_authorized_documents"
EXTRACT_TARGET = "app.services.smart_router_service.extract_concept_graph"


@pytest.fixture
def fake_workspace(monkeypatch):
    monkeypatch.setattr(
        "app.main.resolve_authenticated_workspace",
        lambda *args, **kwargs: ("test-user", None),
    )


@pytest.mark.parametrize(
    "url",
    ["/documents/not_mine.pdf/concept-graph", "/concept-graph/not_mine.pdf"],
)
def test_route_unauthorized_document_returns_404(fake_workspace, url):
    with patch(AUTH_TARGET, return_value=set()), patch(EXTRACT_TARGET) as extract:
        response = client.get(url)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
    extract.assert_not_called()


def test_route_authorized_document_returns_graph_payload(fake_workspace):
    payload = srs._empty_graph(DOC, "no_indexed_content")
    with patch(AUTH_TARGET, return_value={DOC}), patch(EXTRACT_TARGET, return_value=payload) as extract:
        response = client.get(f"/documents/{DOC}/concept-graph")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "empty"
    assert body["empty_reason"] == "no_indexed_content"
    extract.assert_called_once()