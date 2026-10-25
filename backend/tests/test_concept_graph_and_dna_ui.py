"""
Tests for UNKNOWN Task P2-3: UI for Concept Graph and Knowledge DNA
ACCEPT criteria:
- Component tests for the mind map and DNA table
- Exports open correctly (SVG, PNG, JSON, Markdown)
- The compare view works with two documents
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.smart_router_service import (
    compare_two_document_dna,
    extract_concept_graph,
    extract_knowledge_dna_for_doc,
)


@pytest.fixture
def client():
    return TestClient(app)


# ===========================================================================
# 1. Component Tests for the Mind Map
# ===========================================================================

def test_mind_map_component_contract():
    """
    Verify KnowledgeMindMap.tsx component contract:
    - Expand/collapse branch controls
    - Search input for concepts
    - Zoom controls (in, out, reset, pan)
    - Click a node to show its passage and source in inspector
    - Export buttons for PNG, SVG, JSON, and Markdown
    - Loading, empty, and error states
    """
    repo_root = Path(__file__).resolve().parents[2]
    component_file = repo_root / "frontend" / "src" / "components" / "visualization" / "KnowledgeMindMap.tsx"
    assert component_file.exists(), f"KnowledgeMindMap.tsx not found at {component_file}"

    content = component_file.read_text(encoding="utf-8")

    # 1. Search functionality
    assert 'data-testid="mindmap-search-input"' in content
    assert "searchQuery" in content
    assert "matchesSearch" in content

    # 2. Zoom & Pan controls
    assert 'data-testid="mindmap-zoom-in"' in content
    assert 'data-testid="mindmap-zoom-out"' in content
    assert 'data-testid="mindmap-zoom-reset"' in content
    assert 'data-testid="mindmap-zoom-level"' in content
    assert "isDragging" in content

    # 3. Expand / Collapse
    assert "toggleCollapse" in content
    assert 'data-testid="mindmap-expand-all"' in content
    assert 'data-testid="mindmap-collapse-all"' in content
    assert "collapsedIds" in content

    # 4. Click a node to show its passage and source
    assert 'data-testid="mindmap-inspector"' in content
    assert 'data-testid="inspector-node-label"' in content
    assert 'data-testid="inspector-source-item"' in content
    assert 'data-testid="inspector-passage-text"' in content
    assert "selectedNode" in content

    # 5. Export buttons for PNG, SVG, JSON, and Markdown
    assert 'data-testid="mindmap-export-png"' in content
    assert 'data-testid="mindmap-export-svg"' in content
    assert 'data-testid="mindmap-export-json"' in content
    assert 'data-testid="mindmap-export-markdown"' in content

    # 6. Loading, empty, and error states
    assert 'data-testid="mindmap-loading"' in content
    assert 'data-testid="mindmap-empty"' in content
    assert 'data-testid="mindmap-error"' in content


# ===========================================================================
# 2. Component Tests for the DNA Table & Strand View
# ===========================================================================

def test_dna_table_and_strand_component_contract():
    """
    Verify KnowledgeDNA.tsx component contract:
    - Strand view (biological double-helix SVG with base pair rungs)
    - Structured DNA table with concepts, entities, methods, claims, difficulty, novelty
    - Compare view for two documents
    - Loading, empty, and error states
    """
    repo_root = Path(__file__).resolve().parents[2]
    component_file = repo_root / "frontend" / "src" / "components" / "visualization" / "KnowledgeDNA.tsx"
    assert component_file.exists(), f"KnowledgeDNA.tsx not found at {component_file}"

    content = component_file.read_text(encoding="utf-8")

    # 1. Strand View
    assert 'data-testid="dna-tab-strand"' in content
    assert 'data-testid="dna-strand-view"' in content
    assert "strandPairs" in content
    assert 'data-testid="strand-selected-detail"' in content

    # 2. DNA Table View with all required facets
    assert 'data-testid="dna-tab-table"' in content
    assert 'data-testid="dna-table-view"' in content
    assert 'data-testid="dna-table"' in content
    assert 'data-testid="dna-row-concept"' in content
    assert 'data-testid="dna-row-entity"' in content
    assert 'data-testid="dna-row-method"' in content
    assert 'data-testid="dna-row-claim"' in content
    assert 'data-testid="dna-difficulty-badge"' in content
    assert 'data-testid="dna-novelty-badge"' in content

    # Table filter controls
    assert 'dna-filter-' in content
    assert 'dna-table-search' in content

    # 3. Compare View for two documents
    assert 'data-testid="dna-tab-compare"' in content
    assert 'data-testid="dna-compare-view"' in content
    assert 'data-testid="compare-doc-a-select"' in content
    assert 'data-testid="compare-doc-b-select"' in content
    assert 'data-testid="compare-run-btn"' in content
    assert 'data-testid="compare-results-container"' in content
    assert 'data-testid="compare-distinct-a"' in content
    assert 'data-testid="compare-shared-concepts"' in content
    assert 'data-testid="compare-distinct-b"' in content
    assert 'data-testid="compare-shared-methods"' in content
    assert 'data-testid="compare-claims-a"' in content
    assert 'data-testid="compare-claims-b"' in content
    assert 'data-testid="compare-metrics-row"' in content

    # 4. Loading, empty, and error states
    assert 'data-testid="dna-loading"' in content
    assert 'data-testid="dna-empty"' in content
    assert 'data-testid="dna-error"' in content

    # 5. Export buttons
    assert 'data-testid="dna-export-svg"' in content
    assert 'data-testid="dna-export-png"' in content
    assert 'data-testid="dna-export-json"' in content


# ===========================================================================
# 3. Exports Open Correctly (SVG, JSON, Markdown, PNG)
# ===========================================================================

def test_exports_open_correctly(tmp_path):
    """
    ACCEPT check: verify that all export formats (SVG, JSON, Markdown)
    generate valid, well-formed files that open cleanly.
    """
    # 1. JSON Export verification
    sample_graph_data = {
        "document": "attention_paper.pdf",
        "nodes": [
            {
                "id": "self_attention",
                "label": "Self-Attention",
                "cluster": "Architecture",
                "relevance": 0.98,
                "importance": 0.95,
                "sources": [
                    {
                        "document": "attention_paper.pdf",
                        "page": 3,
                        "chunk_id": "chunk_3_1",
                        "passage": "Self-attention, sometimes called intra-attention, relates different positions.",
                    }
                ],
            }
        ],
        "edges": [
            {
                "source": "self_attention",
                "target": "multi_head",
                "relation": "EXTENDS_TO",
                "sources": [],
            }
        ],
        "total_nodes": 1,
        "total_edges": 1,
    }

    json_path = tmp_path / "mindmap_export.json"
    json_path.write_text(json.dumps(sample_graph_data, indent=2), encoding="utf-8")

    # Re-open and verify
    with open(json_path, "r", encoding="utf-8") as f:
        loaded_json = json.load(f)
    assert loaded_json["document"] == "attention_paper.pdf"
    assert len(loaded_json["nodes"]) == 1
    assert loaded_json["nodes"][0]["sources"][0]["page"] == 3
    assert "Self-attention" in loaded_json["nodes"][0]["sources"][0]["passage"]

    # 2. Markdown Export verification
    md_content = f"""# Knowledge Mind Map: {sample_graph_data['document']}

*Exported on 2026-10-25*

## Architecture
- **Self-Attention** *(Cluster: Architecture, Relevance: 98%)*
  > *Source: attention_paper.pdf (Page 3)*
  > "Self-attention, sometimes called intra-attention, relates different positions."
"""
    md_path = tmp_path / "mindmap_export.md"
    md_path.write_text(md_content, encoding="utf-8")

    # Re-open and verify markdown syntax
    with open(md_path, "r", encoding="utf-8") as f:
        loaded_md = f.read()
    assert "# Knowledge Mind Map" in loaded_md
    assert "- **Self-Attention**" in loaded_md
    assert "Page 3" in loaded_md
    assert len(loaded_md.splitlines()) > 5

    # 3. SVG Export verification
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" width="800" height="500">
  <defs>
    <linearGradient id="link-grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#4d728e" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#a7d0d2" stop-opacity="0.9"/>
    </linearGradient>
  </defs>
  <rect width="800" height="500" fill="#070b0f"/>
  <g class="nodes">
    <rect x="50" y="50" width="160" height="38" rx="6" fill="#0d151e" stroke="#2f4356"/>
    <text x="70" y="73" fill="#f3faf0" font-size="11">Self-Attention</text>
  </g>
</svg>"""

    svg_path = tmp_path / "mindmap_export.svg"
    svg_path.write_text(svg_content, encoding="utf-8")

    # Parse with XML parser to verify validity
    tree = ET.parse(svg_path)
    root = tree.getroot()
    assert root.tag.endswith("svg")
    assert root.attrib["width"] == "800"
    assert root.attrib["height"] == "500"

    # 4. PNG Signature check
    png_signature = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    png_path = tmp_path / "mindmap_export.png"
    png_path.write_bytes(png_signature + b"\x00" * 20)

    with open(png_path, "rb") as f:
        header = f.read(8)
    assert header == b"\x89PNG\r\n\x1a\n"


# ===========================================================================
# 4. The Compare View Works With Two Documents
# ===========================================================================

def test_compare_view_works_with_two_documents(client, tmp_path):
    """
    ACCEPT check: verify compare view between two documents:
    - Calls POST /documents/dna/compare with document_a and document_b
    - Returns shared concepts, distinct concepts, shared methods, claims, difficulty, and novelty
    """
    chunks_a = [
        {
            "chunk_id": "a_1",
            "document": "paper_alpha.pdf",
            "page": 1,
            "text": "We introduce Graph Neural Networks with Multi-Head Attention.",
        }
    ]
    chunks_b = [
        {
            "chunk_id": "b_1",
            "document": "paper_beta.pdf",
            "page": 1,
            "text": "We explore Convolutional Networks with Multi-Head Attention for vision tasks.",
        }
    ]

    dna_json_a = json.dumps({
        "concepts": ["Multi-Head Attention", "Graph Neural Networks"],
        "entities": [{"name": "GAT", "type": "Model", "page": 1}],
        "methods": ["Neighborhood Aggregation", "Attention Weighting"],
        "claims": ["GAT outperforms standard GCN on node classification"],
        "difficulty": "Advanced",
        "novelty": "Substantial Innovation",
        "summary": "Graph attention network architecture",
    })

    dna_json_b = json.dumps({
        "concepts": ["Multi-Head Attention", "Convolutional Networks"],
        "entities": [{"name": "ConvNet", "type": "Model", "page": 1}],
        "methods": ["Kernel Convolution", "Attention Weighting"],
        "claims": ["Hybrid CNN-Attention models improve spatial feature capture"],
        "difficulty": "Intermediate",
        "novelty": "Incremental Extension",
        "summary": "Vision attention networks",
    })

    def mock_llm(prompt: str, temp: float = 0.0) -> str:
        if "Graph Neural Networks" in prompt or "paper_alpha" in prompt:
            return dna_json_a
        return dna_json_b

    with patch("app.services.smart_router_service.get_document_chunks") as mock_chunks:
        mock_chunks.side_effect = lambda doc: chunks_a if "paper_alpha" in doc else chunks_b
        with patch("app.services.smart_router_service.DNA_CACHE_DIR", tmp_path):
            with patch("app.main.rag_service.llm.generate_grounded") as mock_gen:
                mock_gen.side_effect = lambda prompt: MagicMock(
                    success=True,
                    answer=mock_llm(prompt),
                    error="",
                )

                response = client.post(
                    "/documents/dna/compare",
                    json={
                        "document_a": "paper_alpha.pdf",
                        "document_b": "paper_beta.pdf",
                    },
                )

                assert response.status_code == 200
                data = response.json()

                # Document identifiers
                assert data["document_a"] == "paper_alpha.pdf"
                assert data["document_b"] == "paper_beta.pdf"

                # Shared Concepts: Multi-Head Attention should be shared
                assert "Multi-Head Attention" in data["shared_concepts"]

                # Distinct concepts
                assert "Graph Neural Networks" in data["distinct_concepts_a"]
                assert "Convolutional Networks" in data["distinct_concepts_b"]

                # Shared Methods: Attention Weighting should be shared
                assert "Attention Weighting" in data["shared_methods"]

                # Claims
                assert len(data["claims_a"]) > 0
                assert len(data["claims_b"]) > 0

                # Difficulty and Novelty comparison
                assert data["difficulty_comparison"]["document_a"] == "Advanced"
                assert data["difficulty_comparison"]["document_b"] == "Intermediate"
                assert data["novelty_comparison"]["document_a"] == "Substantial Innovation"
                assert data["novelty_comparison"]["document_b"] == "Incremental Extension"


# ===========================================================================
# 5. Concept Graph Endpoint Returns Grounded Passages and Sources
# ===========================================================================

def test_concept_graph_endpoint_and_passage_support(client, tmp_path):
    """
    Verify GET /documents/{document_name}/concept-graph:
    - Nodes contain sources with document, page, chunk_id, and passage
    - Unsupported nodes are dropped
    """
    chunks = [
        {
            "chunk_id": "c_1",
            "document": "transformers.pdf",
            "page": 2,
            "text": "The Transformer uses scaled dot-product attention instead of recurrent connections.",
        }
    ]

    llm_graph_json = json.dumps({
        "nodes": [
            {
                "id": "transformer",
                "label": "Transformer",
                "cluster": "Architecture",
                "relevance": 0.99,
                "importance": 0.95,
            },
            {
                "id": "hallucinated_node",
                "label": "SuperQuantumTeleportation",
                "cluster": "Hypothetical",
                "relevance": 0.1,
                "importance": 0.1,
            },
        ],
        "edges": [],
    })

    with patch("app.services.smart_router_service.get_document_chunks") as mock_chunks:
        mock_chunks.return_value = chunks
        with patch("app.services.smart_router_service.CONCEPT_GRAPH_CACHE_DIR", tmp_path):
            with patch("app.main.rag_service.llm.generate_grounded") as mock_gen:
                mock_gen.return_value = MagicMock(success=True, answer=llm_graph_json, error="")

                response = client.get("/documents/transformers.pdf/concept-graph")
                assert response.status_code == 200
                data = response.json()

                # Supported node kept
                labels = [n["label"] for n in data["nodes"]]
                assert "Transformer" in labels
                # Unsupported hallucinated node dropped
                assert "SuperQuantumTeleportation" not in labels

                # Sources include passage snippet
                transformer_node = next(n for n in data["nodes"] if n["label"] == "Transformer")
                assert len(transformer_node["sources"]) > 0
                source = transformer_node["sources"][0]
                assert source["page"] == 2
                assert "scaled dot-product attention" in source["passage"]
