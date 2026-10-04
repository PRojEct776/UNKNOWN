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
