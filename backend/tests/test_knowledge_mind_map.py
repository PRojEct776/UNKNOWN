from app.rag.knowledge_mind_map import (
    KnowledgeMindMapEngine,
    NodeType,
)


def sample_response():
    return """
    {
      "query": "RAG evaluation",
      "research_area": "Retrieval-augmented generation evaluation",
      "nodes": [
        {
          "id": "rag",
          "label": "RAG",
          "type": "TOPIC",
          "description": "Retrieval-augmented generation research.",
          "evidence": [
            "The paper evaluates a RAG system."
          ],
          "confidence": 0.95,
          "document": "sample_ieee.pdf",
          "page": 2,
          "chunk_id": "chunk_002"
        },
        {
          "id": "bm25",
          "label": "BM25",
          "type": "METHOD",
          "description": "BM25 is used for lexical retrieval.",
          "evidence": [
            "The system uses BM25 for lexical retrieval."
          ],
          "confidence": 0.94,
          "document": "sample_ieee.pdf",
          "page": 4,
          "chunk_id": "chunk_004"
        },
        {
          "id": "retrieval",
          "label": "Hybrid Retrieval",
          "type": "CONCEPT",
          "description": "The system combines retrieval approaches.",
          "evidence": [
            "The system combines BM25 with semantic retrieval."
          ],
          "confidence": 0.91,
          "document": "sample_ieee.pdf",
          "page": 5,
          "chunk_id": "chunk_005"
        }
      ],
      "edges": [
        {
          "source": "bm25",
          "target": "retrieval",
          "relationship": "PART_OF",
          "evidence": "BM25 is used as part of the hybrid retrieval system.",
          "confidence": 0.89
        },
        {
          "source": "retrieval",
          "target": "rag",
          "relationship": "SUPPORTS",
          "evidence": "The hybrid retrieval system is used by the RAG system.",
          "confidence": 0.86
        }
      ],
      "sources": [
        {
          "document": "sample_ieee.pdf",
          "page": 2,
          "chunk_id": "chunk_002"
        },
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
    engine = KnowledgeMindMapEngine()

    report = engine.parse_response(
        query="RAG evaluation",
        response_text=sample_response(),
    )

    assert report.query == "RAG evaluation"
    assert len(report.nodes) == 3
    assert len(report.edges) == 2
    assert len(report.sources) == 3


def test_node_types():
    engine = KnowledgeMindMapEngine()

    report = engine.parse_response(
        query="RAG evaluation",
        response_text=sample_response(),
    )

    assert report.nodes[0].type == NodeType.TOPIC
    assert report.nodes[1].type == NodeType.METHOD
    assert report.nodes[2].type == NodeType.CONCEPT


def test_node_traceability():
    engine = KnowledgeMindMapEngine()

    report = engine.parse_response(
        query="RAG evaluation",
        response_text=sample_response(),
    )

    node = report.nodes[1]

    assert node.document == "sample_ieee.pdf"
    assert node.page == 4
    assert node.chunk_id == "chunk_004"
    assert node.evidence


def test_edges_reference_existing_nodes():
    engine = KnowledgeMindMapEngine()

    report = engine.parse_response(
        query="RAG evaluation",
        response_text=sample_response(),
    )

    node_ids = {node.id for node in report.nodes}

    for edge in report.edges:
        assert edge.source in node_ids
        assert edge.target in node_ids


def test_unknown_edge_node_is_rejected():
    engine = KnowledgeMindMapEngine()

    response = """
    {
      "query": "Test",
      "research_area": "Test",
      "nodes": [
        {
          "id": "node_a",
          "label": "A",
          "type": "CONCEPT",
          "description": "A",
          "evidence": ["Evidence A"],
          "confidence": 0.9
        }
      ],
      "edges": [
        {
          "source": "node_a",
          "target": "missing_node",
          "relationship": "RELATES_TO",
          "evidence": "Evidence",
          "confidence": 0.8
        }
      ]
    }
    """

    try:
        engine.parse_response(
            query="Test",
            response_text=response,
        )
        assert False, "Expected ValueError"
    except ValueError as error:
        assert "unknown target node" in str(error)


def test_json_fence():
    engine = KnowledgeMindMapEngine()

    response = "```json\n" + sample_response() + "\n```"

    report = engine.parse_response(
        query="RAG evaluation",
        response_text=response,
    )

    assert report.nodes
    assert report.edges


def test_invalid_json():
    engine = KnowledgeMindMapEngine()

    try:
        engine.parse_response(
            query="RAG evaluation",
            response_text="not valid json",
        )
        assert False, "Expected ValueError"
    except ValueError as error:
        assert "invalid JSON" in str(error)


def test_hierarchical_mind_map_structure_and_edges():
    """Verify hierarchical mind map populates parent-child relationships and edges."""
    engine = KnowledgeMindMapEngine()
    json_data = """
    {
      "query": "DNA Storage Architecture",
      "research_area": "DNA Storage Systems",
      "nodes": [
        {
          "id": "root",
          "label": "DNA Storage Systems",
          "type": "TOPIC",
          "description": "Central topic on molecular DNA data storage.",
          "confidence": 1.0
        },
        {
          "id": "branch_encoding",
          "label": "Codec Architecture",
          "type": "METHOD",
          "description": "Encoding algorithms for binary to nucleotide mapping.",
          "document": "paper_a.pdf",
          "page": 2,
          "chunk_id": "chunk_01",
          "evidence": ["Fountain codes map data to droplets."],
          "confidence": 0.95
        },
        {
          "id": "sub_fountain",
          "label": "Fountain Coding",
          "type": "FINDING",
          "description": "Robust reconstruction with low error rates.",
          "document": "paper_a.pdf",
          "page": 3,
          "chunk_id": "chunk_02",
          "evidence": ["Reconstruction achieved with 1.05 overhead."],
          "confidence": 0.92
        }
      ],
      "edges": [
        {
          "source": "root",
          "target": "branch_encoding",
          "relationship": "USES",
          "evidence": "DNA storage relies on encoding architecture.",
          "confidence": 0.95
        },
        {
          "source": "branch_encoding",
          "target": "sub_fountain",
          "relationship": "DETAILS",
          "evidence": "Encoding employs fountain codes.",
          "confidence": 0.92
        }
      ],
      "sources": [
        {"document": "paper_a.pdf", "page": 2, "chunk_id": "chunk_01"},
        {"document": "paper_a.pdf", "page": 3, "chunk_id": "chunk_02"}
      ]
    }
    """
    report = engine.parse_response(query="DNA Storage Architecture", response_text=json_data)

    assert report.query == "DNA Storage Architecture"
    assert len(report.nodes) == 3
    assert len(report.edges) == 2
    
    # Check hierarchy populated
    node_map = {n.id: n for n in report.nodes}
    assert node_map["branch_encoding"].parent_id == "root"
    assert "branch_encoding" in node_map["root"].children
    assert node_map["sub_fountain"].parent_id == "branch_encoding"
    assert "sub_fountain" in node_map["branch_encoding"].children


def test_no_llm_mind_map_fallback_generation():
    """Verify deterministic no-LLM fallback produces valid hierarchical mind map from chunks."""
    engine = KnowledgeMindMapEngine()
    evidence = [
        {
            "chunk_id": "c1",
            "document": "Doc_A.pdf",
            "page": 2,
            "text": "The synthesis and chemical assembly methodology utilizes enzymatic oligo fabrication.",
        },
        {
            "chunk_id": "c2",
            "document": "Doc_B.pdf",
            "page": 5,
            "text": "Experimental findings indicate physical storage density reaching 2.1 petabytes per gram with high throughput.",
        },
        {
            "chunk_id": "c3",
            "document": "Doc_B.pdf",
            "page": 6,
            "text": "A notable limitation is the high error rate and slow read latency during high-depth sequencing.",
        },
    ]

    report = engine.build_no_llm_mind_map(
        query="DNA synthesis and density",
        evidence=evidence,
        document_names=["Doc_A.pdf", "Doc_B.pdf"],
    )

    assert report.partial is True
    assert report.notice is not None
    assert "Limited mind map" in report.notice
    assert len(report.nodes) >= 3  # Root + at least 2 branches
    assert len(report.edges) >= 2

    # Root is TOPIC
    assert report.nodes[0].id == "root"
    assert report.nodes[0].type == NodeType.TOPIC

    # Non-root nodes have valid parent_id
    node_ids = {n.id for n in report.nodes}
    for n in report.nodes[1:]:
        assert n.parent_id in node_ids
        assert n.document in ["Doc_A.pdf", "Doc_B.pdf"]
        assert n.chunk_id != ""

    # All edges reference valid nodes
    for edge in report.edges:
        assert edge.source in node_ids
        assert edge.target in node_ids


def test_mind_map_document_attribution_and_citations():
    """Verify nodes preserve exact document, page, and chunk_id citations."""
    engine = KnowledgeMindMapEngine()
    evidence = [
        {
            "chunk_id": "chunk_xyz_99",
            "document": "Precision_Medicine_2025.pdf",
            "page": 14,
            "text": "Experimental findings showed high accuracy neural network classification of multi-omic data with superior performance.",
        }
    ]

    report = engine.build_no_llm_mind_map(
        query="Precision medicine neural network",
        evidence=evidence,
    )

    finding_node = next((n for n in report.nodes if n.chunk_id == "chunk_xyz_99"), None)
    assert finding_node is not None
    assert finding_node.document == "Precision_Medicine_2025.pdf"
    assert finding_node.page == 14
    assert finding_node.chunk_id == "chunk_xyz_99"
    assert "Experimental findings" in finding_node.evidence[0]


def test_mind_map_multiple_selected_documents():
    """Verify mind map incorporates evidence across multiple selected documents."""
    engine = KnowledgeMindMapEngine()
    evidence = [
        {
            "chunk_id": "c1",
            "document": "Doc_1.pdf",
            "page": 1,
            "text": "System architecture uses distributed microservices for indexing.",
        },
        {
            "chunk_id": "c2",
            "document": "Doc_2.pdf",
            "page": 3,
            "text": "Experimental findings demonstrate 99.8% precision across test queries.",
        },
    ]

    report = engine.build_no_llm_mind_map(
        query="Distributed indexing",
        evidence=evidence,
        document_names=["Doc_1.pdf", "Doc_2.pdf"],
    )

    docs_in_nodes = {n.document for n in report.nodes if n.document}
    assert "Doc_1.pdf" in docs_in_nodes
    assert "Doc_2.pdf" in docs_in_nodes
    assert len(report.sources) == 2


def test_mind_map_empty_retrieval():
    """Verify empty retrieval returns clear insufficient evidence notice without failing."""
    from unittest.mock import patch
    from app.main import rag_service

    with patch.object(rag_service, "_search", return_value=[]):
        report = rag_service.generate_knowledge_mind_map(
            query="Completely nonexistent topic xyz999",
            document_names=["fake.pdf"],
        )

        assert report.nodes == []
        assert report.edges == []
        assert "Insufficient evidence" in (report.notice or "")


def test_mind_map_llm_provider_failure_fallback():
    """Verify LLM failure seamlessly falls back to no-LLM partial mind map."""
    from unittest.mock import patch
    from app.main import rag_service
    from app.llm.base_provider import BaseProvider, LLMResponse, ErrorKind
    from app.llm.orchestrator import LLMOrchestrator

    class FailingProvider(BaseProvider):
        provider_name = "failing"
        def __init__(self):
            super().__init__("failing-m")

        def generate_structured(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
            return LLMResponse(
                answer="",
                provider="failing",
                model="failing-m",
                latency_ms=50.0,
                success=False,
                error="Rate limit exceeded (TPM quota)",
                error_kind=ErrorKind.RATE_LIMIT,
            )

        def _call(self, prompt: str, system: str | None = None) -> str:
            return ""

    sample_chunks = [
        {
            "chunk_id": "c1",
            "document": "Bio_A.pdf",
            "page": 2,
            "text": "Methodology uses CRISPR Cas9 gene editing for sequence modification.",
        },
        {
            "chunk_id": "c2",
            "document": "Bio_B.pdf",
            "page": 4,
            "text": "Experimental findings showed 85% insertion efficiency under optimal conditions.",
        },
    ]

    orig_llm = rag_service.llm
    try:
        rag_service.llm = LLMOrchestrator(providers=[FailingProvider()])
        with patch.object(rag_service, "_search", return_value=sample_chunks):
            report = rag_service.generate_knowledge_mind_map(
                query="CRISPR gene editing",
                document_names=["Bio_A.pdf", "Bio_B.pdf"],
            )

            assert report.partial is True
            assert report.notice is not None
            assert "Limited mind map" in report.notice
            assert len(report.nodes) >= 2
            assert len(report.edges) >= 1
    finally:
        rag_service.llm = orig_llm


def test_mind_map_malformed_response_fallback():
    """Verify malformed JSON response triggers clean fallback to no-LLM mind map."""
    from unittest.mock import patch
    from app.main import rag_service
    from app.llm.base_provider import BaseProvider, LLMResponse
    from app.llm.orchestrator import LLMOrchestrator

    class BrokenJsonProvider(BaseProvider):
        provider_name = "broken"
        def __init__(self):
            super().__init__("broken-m")

        def generate_structured(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
            return LLMResponse(
                answer='{"nodes": [{"id": "incomplete',
                provider="broken",
                model="broken-m",
                latency_ms=50.0,
                success=True,
            )

        def _call(self, prompt: str, system: str | None = None) -> str:
            return ""

    sample_chunks = [
        {
            "chunk_id": "c1",
            "document": "NLP_A.pdf",
            "page": 1,
            "text": "Transformer architecture uses multi-head self-attention mechanisms for language modeling.",
        }
    ]

    orig_llm = rag_service.llm
    try:
        rag_service.llm = LLMOrchestrator(providers=[BrokenJsonProvider()])
        with patch.object(rag_service, "_search", return_value=sample_chunks):
            report = rag_service.generate_knowledge_mind_map(
                query="Transformer attention",
            )

            assert report.partial is True
            assert report.notice is not None
            assert len(report.nodes) >= 2
    finally:
        rag_service.llm = orig_llm


def test_mind_map_api_endpoint_and_aliases():
    """Verify /knowledge-mind-map, /mind-map, and /mindmap endpoints return HTTP 200 with partial flag."""
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    from app.main import app, rag_service
    from app.llm.base_provider import BaseProvider, LLMResponse, ErrorKind
    from app.llm.orchestrator import LLMOrchestrator

    class DownProvider(BaseProvider):
        provider_name = "down"
        def __init__(self):
            super().__init__("down-m")
        def generate_structured(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
            return LLMResponse(answer="", provider="down", model="down-m", latency_ms=10.0, success=False, error="Quota", error_kind=ErrorKind.FATAL)
        def _call(self, prompt: str, system: str | None = None) -> str:
            return ""

    sample_chunks = [
        {
            "chunk_id": "c100",
            "document": "TestDoc.pdf",
            "page": 1,
            "text": "Methodology uses dense vector embeddings and approximate nearest neighbor search.",
        }
    ]

    client = TestClient(app)
    orig_llm = rag_service.llm
    try:
        rag_service.llm = LLMOrchestrator(providers=[DownProvider()])
        with patch.object(rag_service, "_search", return_value=sample_chunks):
            for endpoint in ["/knowledge-mind-map", "/mind-map", "/mindmap"]:
                resp = client.post(endpoint, json={"query": "Vector search indexing"})
                assert resp.status_code == 200, f"Endpoint {endpoint} returned status {resp.status_code}"
                data = resp.json()
                assert "nodes" in data
                assert "edges" in data
                assert "sources" in data
                assert data.get("partial") is True
                assert data.get("notice") is not None
    finally:
        rag_service.llm = orig_llm


def test_frontend_mindmap_ui_contract_and_interactions():
    """Verify frontend mindmap component exposes all required interaction testids."""
    from pathlib import Path

    kmm_path = Path("frontend/src/components/visualization/KnowledgeMindMap.tsx")
    assert kmm_path.exists()
    content = kmm_path.read_text(encoding="utf-8")

    assert 'data-testid="mindmap-container"' in content
    assert 'data-testid="mindmap-fit-screen"' in content
    assert 'data-testid="mindmap-zoom-in"' in content
    assert 'data-testid="mindmap-zoom-out"' in content
    assert 'data-testid="mindmap-zoom-reset"' in content
    assert 'data-testid="mindmap-expand-all"' in content
    assert 'data-testid="mindmap-collapse-all"' in content
    assert 'data-testid="mindmap-inspector"' in content
    assert 'data-testid="mindmap-export-svg"' in content
    assert 'data-testid="mindmap-export-png"' in content
    assert 'data-testid="mindmap-export-json"' in content


def test_mind_map_clean_central_topic_extraction():
    """Verify central topic is short, clean and descriptive, never the raw query prompt."""
    from app.rag.knowledge_mind_map import extract_clean_topic, KnowledgeMindMapEngine

    engine = KnowledgeMindMapEngine()

    query1 = "Create a mind map of DNA data storage covering encoding methods, DNA synthesis and preservation"
    clean1 = extract_clean_topic(query1)
    assert clean1 == "DNA Data Storage"

    query2 = "Generate a mind map for CRISPR-Cas9 genome editing mechanisms focusing on double strand breaks"
    clean2 = extract_clean_topic(query2)
    assert "CRISPR-Cas9" in clean2
    assert "Generate a mind map" not in clean2
    assert "focusing on" not in clean2

    evidence = [
        {
            "chunk_id": "c1",
            "document": "Nature_DNA.pdf",
            "page": 1,
            "text": "DNA data storage encodes digital bitstreams into synthetic biological oligonucleotides using quaternary nucleotide mapping.",
        }
    ]
    mindmap = engine.build_no_llm_mind_map(query=query1, evidence=evidence)
    root_node = next(n for n in mindmap.nodes if n.id == "root")
    assert root_node.label == "DNA Data Storage"
    assert "Create a mind map" not in root_node.label


def test_mind_map_meaningful_leaf_nodes_and_no_raw_truncation():
    """Verify leaf nodes have meaningful titles without incomplete sentences or trailing ellipsis."""
    from app.rag.knowledge_mind_map import KnowledgeMindMapEngine

    engine = KnowledgeMindMapEngine()
    query = "DNA data storage"
    evidence = [
        {
            "chunk_id": "c1",
            "document": "DNA_Paper.pdf",
            "page": 2,
            "text": "A 4 kB file is converted into DNA oligonucleotides using a base-3 mapping scheme with zero loss.",
        },
        {
            "chunk_id": "c2",
            "document": "DNA_Paper.pdf",
            "page": 3,
            "text": "The results describe how phosphoramidite chemical synthesis introduces insertion and deletion errors during oligo assembly.",
        },
        {
            "chunk_id": "c3",
            "document": "DNA_Paper.pdf",
            "page": 5,
            "text": "Here, dry DNA storage in silica encapsulation improves long-term stability across ambient temperatures for centuries.",
        },
    ]

    mindmap = engine.build_no_llm_mind_map(query=query, evidence=evidence)
    leaf_nodes = [n for n in mindmap.nodes if n.id != "root" and n.parent_id != "root"]
    assert len(leaf_nodes) >= 2

    for node in leaf_nodes:
        # Must not end in trailing ellipsis
        assert not node.label.endswith("...")
        assert not node.label.endswith("…")
        # Must not be raw sentence beginning
        assert node.label != "A 4 kB file is..."
        assert node.label != "The results desc..."
        assert node.label != "Here, a neutral..."
        # Must have complete description sentence
        assert len(node.description) > 20
        # Must have valid citations
        assert node.document == "DNA_Paper.pdf"
        assert node.chunk_id != ""
        assert len(node.evidence) > 0


def test_mind_map_domain_specific_branches_and_multiple_documents():
    """Verify domain categories replace generic ones and multiple documents contribute evidence."""
    from app.rag.knowledge_mind_map import KnowledgeMindMapEngine

    engine = KnowledgeMindMapEngine()
    query = "DNA data storage synthesis and error correction"
    evidence = [
        {
            "chunk_id": "docA_c1",
            "document": "Doc_A_Encoding.pdf",
            "page": 1,
            "text": "Binary-to-DNA conversion algorithms apply Reed-Solomon error-correcting codes to guarantee data integrity.",
        },
        {
            "chunk_id": "docB_c1",
            "document": "Doc_B_Synthesis.pdf",
            "page": 4,
            "text": "Phosphoramidite chemical synthesis physically fabricates de novo oligonucleotides with high single-base fidelity.",
        },
        {
            "chunk_id": "docB_c2",
            "document": "Doc_B_Synthesis.pdf",
            "page": 7,
            "text": "Ultra-high storage density reaches petabytes per gram of biological material with zero power maintenance.",
        },
    ]

    mindmap = engine.build_no_llm_mind_map(query=query, evidence=evidence)
    branch_labels = [n.label for n in mindmap.nodes if n.parent_id == "root"]

    # Verify domain-specific categories exist
    assert any("Encoding" in b or "Synthesis" in b or "Advantages" in b or "Reliability" in b for b in branch_labels)

    # Verify multiple documents are cited in the graph nodes
    cited_docs = {n.document for n in mindmap.nodes if n.document}
    assert "Doc_A_Encoding.pdf" in cited_docs
    assert "Doc_B_Synthesis.pdf" in cited_docs
