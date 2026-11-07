import json
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


# ==============================================================================
# COMPREHENSIVE KNOWLEDGE DNA TEST SUITE
# ==============================================================================

def sample_full_dna_response():
    return """
    {
      "query": "DNA Data Storage Archival Synthesis",
      "research_area": "DNA Data Storage",
      "objectives": [
        "Eliminate high synthesis error rates in long oligonucleotides",
        "Enable low-cost millennial archival data storage"
      ],
      "core_concepts": [
        "DNA Data Storage",
        "Phosphoramidite Chemistry",
        "Enzymatic Synthesis",
        "Reed-Solomon Coding"
      ],
      "methodologies": [
        "Enzymatic Oligonucleotide Synthesis",
        "Two-Dimensional Error Correction"
      ],
      "datasets": [
        "Archival English Wikipedia 16GB",
        "Synthetic Random Bitstream Benchmarks"
      ],
      "metrics": [
        "Information Density (bits/nm3)",
        "Synthesis Error Rate",
        "Recovery Fidelity"
      ],
      "results": [
        "Achieved 8.2 bits/nm3 information density with zero bit errors",
        "Enzymatic synthesis reduced fabrication time by 42%"
      ],
      "contributions": [
        "Template-free enzymatic synthesis pipeline for molecular storage",
        "Inner-outer parity code achieving perfect recovery under 8% dropout"
      ],
      "advantages": [
        "Zero electrical power required for ambient data retention",
        "1000-fold density improvement over magnetic tape"
      ],
      "limitations": [
        "Synthesis cost remains high at $0.05 per nucleotide",
        "Read-write latency measured in hours rather than milliseconds"
      ],
      "future_directions": [
        "Transition to microfluidic enzymatic synthesis chips",
        "Direct electronic nanopore sequencing integration"
      ],
      "nodes": [
        {
          "id": "node_enzymatic",
          "label": "Enzymatic Synthesis",
          "category": "METHODOLOGY",
          "explanation": "Enzymatic synthesis fabricates DNA strands using terminal deoxynucleotidyl transferase.",
          "evidence": ["Enzymatic synthesis operates without toxic organic reagents."],
          "confidence": 0.95,
          "document": "paper_alpha.pdf",
          "supporting_papers": ["paper_alpha.pdf"],
          "page": 3,
          "chunk_id": "chunk_a3",
          "is_inferred": false,
          "quantitative_value": "42% time reduction"
        },
        {
          "id": "node_density",
          "label": "Information Density",
          "category": "METRIC",
          "explanation": "Physical information storage capacity per unit volume.",
          "evidence": ["The system achieves an unprecedented density of 8.2 bits/nm3."],
          "confidence": 0.96,
          "document": "paper_alpha.pdf",
          "supporting_papers": ["paper_alpha.pdf"],
          "page": 4,
          "chunk_id": "chunk_a4",
          "is_inferred": false,
          "quantitative_value": "8.2 bits/nm3"
        },
        {
          "id": "node_cost_limit",
          "label": "Synthesis Cost Bottleneck",
          "category": "LIMITATION",
          "explanation": "High price per base limits commercial viability.",
          "evidence": ["Synthesis cost remains high at $0.05 per nucleotide."],
          "confidence": 0.91,
          "document": "paper_beta.pdf",
          "supporting_papers": ["paper_beta.pdf"],
          "page": 2,
          "chunk_id": "chunk_b2",
          "is_inferred": false,
          "quantitative_value": "$0.05 per nucleotide"
        }
      ],
      "edges": [
        {
          "source": "node_enzymatic",
          "target": "node_density",
          "relationship": "produces",
          "evidence": "Enzymatic synthesis achieves an unprecedented density of 8.2 bits/nm3.",
          "confidence": 0.94,
          "is_inferred": false,
          "supporting_papers": ["paper_alpha.pdf"]
        },
        {
          "source": "node_cost_limit",
          "target": "node_enzymatic",
          "relationship": "addressed by",
          "evidence": "Enzymatic approaches are proposed to overcome synthesis cost barriers.",
          "confidence": 0.82,
          "is_inferred": true,
          "supporting_papers": ["paper_beta.pdf", "paper_alpha.pdf"]
        }
      ],
      "conflicting_findings": [
        {
          "topic": "Thermal Stability of Dried DNA",
          "paper_a": "paper_alpha.pdf",
          "finding_a": "DNA stored in dry state degraded by 12% at 65C after 4 weeks.",
          "paper_b": "paper_beta.pdf",
          "finding_b": "Dry DNA encapsulated in silica retained 99.8% integrity at 65C after 4 weeks.",
          "explanation": "Direct disagreement regarding thermal degradation rates without protective silica encapsulation.",
          "evidence_chunks": ["chunk_a5", "chunk_b7"]
        }
      ]
    }
    """


def test_ten_dimensions_extraction():
    """Verify all 10 core research knowledge dimensions are extracted and structured."""
    engine = KnowledgeDNA()
    report = engine.parse_response(
        query="DNA Data Storage Archival Synthesis",
        response_text=sample_full_dna_response(),
    )

    # 1. Research Objectives
    assert len(report.objectives) == 2
    assert "synthesis error rates" in report.objectives[0]

    # 2. Core Concepts
    assert "Phosphoramidite Chemistry" in report.core_concepts

    # 3. Methodologies
    assert "Enzymatic Oligonucleotide Synthesis" in report.methodologies

    # 4. Datasets
    assert "Archival English Wikipedia 16GB" in report.datasets

    # 5. Evaluation Metrics
    assert any("Density" in m for m in report.metrics)

    # 6. Experimental Results & Quantitative Values
    assert any("8.2 bits/nm3" in r for r in report.results)
    density_node = next(n for n in report.nodes if n.id == "node_density")
    assert density_node.quantitative_value == "8.2 bits/nm3"

    # 7. Key Contributions
    assert len(report.contributions) == 2

    # 8. Advantages
    assert any("Zero electrical power" in a for a in report.advantages)

    # 9. Limitations
    assert any("$0.05 per nucleotide" in l for l in report.limitations)

    # 10. Future Directions
    assert any("microfluidic" in f for f in report.future_directions)

    # Statistics check
    assert report.statistics["total_concepts"] >= 3
    assert report.statistics["unique_methodologies"] >= 1
    assert report.statistics["datasets"] >= 2
    assert report.statistics["findings"] >= 2
    assert report.statistics["relationships"] >= 2


def test_explicit_vs_inferred_relationships():
    """Verify distinguishing explicitly stated relationships from inferred relationships."""
    engine = KnowledgeDNA()
    report = engine.parse_response(
        query="DNA Data Storage",
        response_text=sample_full_dna_response(),
    )

    explicit_edges = [e for e in report.edges if not e.is_inferred]
    inferred_edges = [e for e in report.edges if e.is_inferred]

    assert len(explicit_edges) == 1
    assert explicit_edges[0].relationship == "produces"
    assert explicit_edges[0].source == "node_enzymatic"
    assert explicit_edges[0].target == "node_density"
    assert explicit_edges[0].is_inferred is False

    assert len(inferred_edges) == 1
    assert inferred_edges[0].relationship == "addressed by"
    assert inferred_edges[0].is_inferred is True


def test_multi_document_duplicate_concept_merging():
    """Verify duplicate/synonymous concepts across papers are merged cleanly without losing citations."""
    engine = KnowledgeDNA()

    nodes = [
        {
            "id": "node_1",
            "label": "DNA Data Storage",
            "category": "CONCEPT",
            "explanation": "Storage of binary data in synthesized DNA molecules.",
            "evidence": ["DNA storage offers millennial longevity."],
            "confidence": 0.90,
            "document": "paper_alpha.pdf",
            "supporting_papers": ["paper_alpha.pdf"],
            "page": 1,
            "chunk_id": "chunk_a1",
        },
        {
            "id": "node_2",
            "label": "dna data storage",
            "category": "CONCEPT",
            "explanation": "Comprehensive molecular archival architecture storing petabytes per gram.",
            "evidence": ["Data density of DNA exceeds magnetic tape by orders of magnitude."],
            "confidence": 0.94,
            "document": "paper_beta.pdf",
            "supporting_papers": ["paper_beta.pdf"],
            "page": 2,
            "chunk_id": "chunk_b2",
        },
        {
            "id": "node_3",
            "label": "Nanopore Readout",
            "category": "METHODOLOGY",
            "explanation": "Single-molecule sequencing using electrical current disruptions.",
            "evidence": ["Nanopore sequencing provides portable real-time readout."],
            "confidence": 0.91,
            "document": "paper_beta.pdf",
            "supporting_papers": ["paper_beta.pdf"],
            "page": 5,
            "chunk_id": "chunk_b5",
        },
    ]

    edges = [
        {
            "source": "node_2",
            "target": "node_3",
            "relationship": "retrieved via",
            "evidence": "DNA data storage files are sequenced via nanopore readout.",
            "confidence": 0.88,
        }
    ]

    payload = json.dumps({
        "query": "DNA Storage",
        "research_area": "DNA Data Storage",
        "nodes": nodes,
        "edges": edges,
    })

    report = engine.parse_response(query="DNA Storage", response_text=payload)

    # 3 nodes were merged to 2 unique nodes
    assert len(report.nodes) == 2
    merged_dna_node = next(n for n in report.nodes if n.label.lower() == "dna data storage")

    # Supporting papers are merged from both documents
    assert "paper_alpha.pdf" in merged_dna_node.supporting_papers
    assert "paper_beta.pdf" in merged_dna_node.supporting_papers
    assert len(merged_dna_node.evidence) == 2
    assert len(merged_dna_node.citations) == 2

    # Relationship edge source was remapped from node_2 to canonical node_1
    assert len(report.edges) == 1
    assert report.edges[0].source == merged_dna_node.id
    assert report.edges[0].target == "node_3"


def test_conflicting_findings_preservation():
    """Verify conflicting findings across papers are tracked without treating missing evidence as conflict."""
    engine = KnowledgeDNA()
    report = engine.parse_response(
        query="DNA Data Storage",
        response_text=sample_full_dna_response(),
    )

    assert len(report.conflicting_findings) == 1
    conflict = report.conflicting_findings[0]
    assert conflict.paper_a == "paper_alpha.pdf"
    assert conflict.paper_b == "paper_beta.pdf"
    assert "degraded by 12%" in conflict.finding_a
    assert "99.8% integrity" in conflict.finding_b
    assert "silica encapsulation" in conflict.explanation


def test_no_llm_deterministic_fallback():
    """Verify deterministic fallback produces a structured 10-dimension Knowledge DNA when LLM is unavailable."""
    engine = KnowledgeDNA()

    mock_evidence = [
        {
            "document": "nature_dna.pdf",
            "page": 1,
            "chunk_id": "chunk_nat_1",
            "text": "The objective is to eliminate synthesis bottlenecks in DNA Data Storage. We introduce Enzymatic Synthesis to fabricate oligonucleotides. The framework achieves 99.2% accuracy and 8.5 bits/nm3 information density on Archival Wikipedia Benchmark. Our key contribution is zero-power molecular archiving.",
        },
        {
            "document": "nature_dna.pdf",
            "page": 2,
            "chunk_id": "chunk_nat_2",
            "text": "However, synthesis cost remains high at $0.02 per base. Future research must develop microfluidic enzymatic reactors to reduce reagents.",
        },
    ]

    report = engine.build_no_llm_dna(
        query="DNA Data Storage",
        evidence=mock_evidence,
        document_names=["nature_dna.pdf"],
    )

    assert report.partial is True
    assert "Limited Knowledge DNA" in (report.notice or "")
    assert len(report.nodes) > 1
    assert len(report.edges) > 1
    assert report.statistics["total_concepts"] > 1

    # Check categories
    categories = {n.category for n in report.nodes}
    assert "CONCEPT" in categories
    assert "METHODOLOGY" in categories
    assert any("Enzymatic" in n.label for n in report.nodes)

    # Check citation preservation
    method_node = next(n for n in report.nodes if "METHOD" in n.category)
    assert method_node.document == "nature_dna.pdf"
    assert method_node.page == 1
    assert method_node.chunk_id == "chunk_nat_1"


def test_empty_retrieval_handling():
    """Verify empty retrieval returns clear insufficient evidence notice without failing."""
    engine = KnowledgeDNA()
    report = engine.build_no_llm_dna(
        query="Nonexistent xyz999",
        evidence=[],
    )

    assert report.nodes == []
    assert report.edges == []
    assert "Not found in available sources" in (report.notice or "")


def test_malformed_json_repair():
    """Verify malformed JSON truncated by token limits is repaired and parsed safely."""
    engine = KnowledgeDNA()
    malformed = """
    {
      "query": "Truncated Test",
      "research_area": "Truncated Area",
      "nodes": [
        {
          "id": "node_1",
          "label": "Truncated Concept",
          "category": "CONCEPT",
          "explanation": "Valid description"
    """

    report = engine.parse_response(
        query="Truncated Test",
        response_text=malformed,
    )

    assert report.research_area == "Truncated Area"
    assert len(report.nodes) == 1
    assert report.nodes[0].label == "Truncated Concept"


def test_rag_service_generate_knowledge_dna_fallback():
    """Verify RAGService falls back to deterministic Knowledge DNA when LLM provider fails."""
    from unittest.mock import patch, MagicMock
    from app.services.rag_service import RAGService
    from app.llm.base_provider import LLMResponse

    # Create dummy service without full model initialization
    service = object.__new__(RAGService)
    from app.rag.knowledge_dna import KnowledgeDNA
    service.knowledge_dna = KnowledgeDNA()
    service.llm = MagicMock()
    service.llm.generate_structured.return_value = LLMResponse(
        answer="",
        provider="mock",
        model="mock-m",
        latency_ms=10.0,
        success=False,
        error="API Quota Exhausted",
    )

    mock_search_results = [
        {
            "document": "paper_test.pdf",
            "page": 1,
            "chunk_id": "c1",
            "text": "We propose Neural DNA Encoding to improve retrieval density. The algorithm achieves 95.4% fidelity.",
        }
    ]

    service._search = MagicMock(return_value=mock_search_results)
    service._build_feature_evidence = MagicMock(return_value=mock_search_results)

    report = service.generate_knowledge_dna(
        query="Neural DNA Encoding",
        document_names=["paper_test.pdf"],
    )

    assert report.partial is True
    assert "Limited Knowledge DNA" in (report.notice or "")
    assert len(report.nodes) >= 1
    assert any("Neural" in n.label or "DNA" in n.label for n in report.nodes)
