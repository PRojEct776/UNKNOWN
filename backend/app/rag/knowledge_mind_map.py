from __future__ import annotations

import json
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    TOPIC = "TOPIC"
    CONCEPT = "CONCEPT"
    METHOD = "METHOD"
    FINDING = "FINDING"
    LIMITATION = "LIMITATION"
    DOCUMENT = "DOCUMENT"


class MindMapNode(BaseModel):
    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    type: NodeType | str
    description: str = ""
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    document: str = ""
    page: int | str = ""
    chunk_id: str = ""
    parent_id: str | None = None
    children: list[str] = Field(default_factory=list)
    significance: str = ""


class MindMapEdge(BaseModel):
    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    relationship: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)


class KnowledgeMindMap(BaseModel):
    query: str
    research_area: str
    nodes: list[MindMapNode] = Field(default_factory=list)
    edges: list[MindMapEdge] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    partial: bool = False
    notice: str | None = None


# ==============================================================================
# TOPIC & CONCEPT TITLE EXTRACTION HELPERS
# ==============================================================================

def extract_clean_topic(query: str, evidence: list[dict[str, Any]] | None = None) -> str:
    """
    Extract a concise, clean, descriptive topic title (2-5 words).
    Never returns complete user queries like 'Create a mind map of DNA data storage...'.
    """
    if not query or not query.strip():
        return "Core Research Topic"

    raw = query.strip()

    # 1. Strip common interactive prompt prefixes
    prefix_patterns = [
        r"^(?:please\s+)?(?:create|generate|build|construct|show(?:\s+me)?|give(?:\s+me)?|make|produce|visualize|draw)\s+(?:a\s+|an\s+)?(?:knowledge\s+|concept\s+|research\s+)?(?:mind\s*map|map|graph|diagram|tree)\s+(?:of|for|on|about)\s+",
        r"^(?:mind\s*map|concept\s*map|knowledge\s*map)\s+(?:of|for|on|about)\s+",
        r"^(?:overview|summary|synthesis|explanation|analysis)\s+(?:of|for|on|about)\s+",
        r"^(?:what\s+is|explain|describe|explore|analyze|investigate)\s+",
        r"^(?:a\s+|an\s+)?(?:mind\s*map|knowledge\s*map)\s+(?:of|for|on|about)\s+",
    ]
    cleaned = raw
    for pat in prefix_patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

    # 2. Strip trailing scope/instructional clauses
    trailing_patterns = [
        r"\b(?:covering|focusing\s+on|including|with\s+(?:regards\s+to|respect\s+to)|and\s+its|across\s+different|in\s+detail|and\s+their|and\s+related|such\s+as|focusing\s+upon)\b.*$",
        r"\b(?:from\s+the\s+supplied\s+documents|based\s+on\s+the\s+documents|using\s+evidence).*$",
    ]
    for pat in trailing_patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

    cleaned = cleaned.strip(" \t\n\r?.!\"'`:,;")

    # Domain specific canonical short names
    lower_c = cleaned.lower()
    if "dna" in lower_c and ("storage" in lower_c or "data" in lower_c):
        return "DNA Data Storage"
    if "crispr" in lower_c and ("cas9" in lower_c or "editing" in lower_c):
        return "CRISPR-Cas9 Genome Editing"
    if "quantum" in lower_c and ("computing" in lower_c or "algorithm" in lower_c):
        return "Quantum Computing"

    words = cleaned.split()
    acronyms = {
        "dna": "DNA", "rna": "RNA", "pcr": "PCR", "ai": "AI", "ml": "ML",
        "rag": "RAG", "faiss": "FAISS", "bm25": "BM25", "crispr": "CRISPR",
        "cas9": "Cas9", "api": "API", "llm": "LLM", "nlp": "NLP",
        "tpm": "TPM", "gpu": "GPU", "cpu": "CPU", "pb": "PB", "gb": "GB",
        "ecc": "ECC", "ngs": "NGS", "sanger": "Sanger"
    }

    if 1 <= len(words) <= 6:
        topic_words = []
        for w in words:
            w_lower = w.lower()
            if w_lower in acronyms:
                topic_words.append(acronyms[w_lower])
            elif w_lower in {"and", "or", "of", "in", "to", "for", "on", "with", "by", "at"} and topic_words:
                topic_words.append(w_lower)
            else:
                topic_words.append(w.capitalize())
        return " ".join(topic_words)

    if len(words) > 6:
        topic_words = []
        for w in words[:4]:
            w_lower = w.lower()
            if w_lower in acronyms:
                topic_words.append(acronyms[w_lower])
            else:
                topic_words.append(w.capitalize())
        return " ".join(topic_words)

    return cleaned.title() if cleaned else "Core Research Topic"


def extract_clean_leaf_title(sentence: str, fallback_concept: str) -> str:
    """
    Extract a meaningful, concise title (3 to 7 words) from a supported sentence.
    Never returns incomplete sentences or truncated strings with trailing ellipsis '...'.
    """
    # 1. Strip citation brackets e.g. [1], [1, 2], (Author, 2022)
    s = re.sub(r"\[\d+(?:,\s*\d+)*\]", "", sentence)
    s = re.sub(r"\([A-Z][a-z]+(?:\s+et\s+al\.)?,\s*\d{4}\)", "", s)

    # 2. Strip leading introductory filler phrases
    fillers = [
        r"^(?:in\s+this\s+work|here|herein|we\s+demonstrate\s+that|we\s+show\s+that|the\s+results\s+show\s+that|the\s+results\s+describe|it\s+was\s+found\s+that|specifically|furthermore|moreover|consequently|as\s+a\s+result|importantly|notably|in\s+addition|our\s+findings\s+indicate\s+that|for\s+example|in\s+particular),?\s*",
        r"^(?:as\s+shown\s+in\s+(?:figure|fig\.|table)\s*\d+,?)\s*",
        r"^(?:the\s+authors\s+report\s+that|we\s+propose\s+that)\s*",
    ]
    for f in fillers:
        s = re.sub(f, "", s, flags=re.IGNORECASE).strip()

    # 3. Strip subordinate clauses starting at conjunctions / relative pronouns
    parts = re.split(
        r",\s*(?:which|where|while|although|whereas|thereby|ensuring|allowing|providing)\b|\b(?:because|in\s+order\s+to|so\s+that)\b",
        s,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    first_clause = parts[0].strip(" \t\n\r,;:-.")

    words = first_clause.split()
    if len(words) < 3:
        return fallback_concept

    # If first word is an article, strip it to keep title punchy
    if words[0].lower() in {"a", "an", "the"} and len(words) > 3:
        words = words[1:]

    cutoff = min(len(words), 7)
    selected_words = words[:cutoff]
    while len(selected_words) > 3 and selected_words[-1].lower() in {
        "and", "or", "of", "in", "with", "for", "the", "a", "an", "to", "by", "is", "was", "are", "were", "as", "at", "into", "from"
    }:
        selected_words.pop()

    candidate = " ".join(selected_words)
    if len(candidate) < 12:
        return fallback_concept

    acronyms = {
        "dna": "DNA", "rna": "RNA", "pcr": "PCR", "ai": "AI", "ml": "ML",
        "ecc": "ECC", "ngs": "NGS", "pb": "PB", "tb": "TB", "gb": "GB",
        "mb": "MB", "kb": "kB", "tdt": "TdT", "crc": "CRC", "rs": "RS"
    }
    title_words = []
    for w in candidate.split():
        w_lower = w.lower()
        if w_lower in acronyms:
            title_words.append(acronyms[w_lower])
        elif w_lower in {"and", "or", "of", "in", "to", "for", "on", "with", "by", "at", "into"} and title_words:
            title_words.append(w_lower)
        else:
            title_words.append(w.capitalize())

    res = " ".join(title_words)
    return res.rstrip(".,;: ")


# ==============================================================================
# DOMAIN TAXONOMY DEFINITIONS
# ==============================================================================

DNA_BRANCH_DEFINITIONS: list[dict[str, Any]] = [
    {
        "title": "Data Encoding",
        "type": NodeType.METHOD,
        "keywords": ["encod", "codec", "binary-to-dna", "mapping", "nucleotide mapping", "base-3", "base-4", "bit-to-base", "huffman", "run-length", "homopolymer", "gc content", "shannon"],
        "relationship": "USES",
        "significance": "Translates digital bitstreams into biological nucleotide sequences under biochemical constraints.",
        "subtopics": [
            ("Binary-to-DNA Conversion", ["binary", "bit", "convert", "translation", "base-3", "base-4", "0 and 1"], "Maps binary bitstreams into A, C, G, T sequences."),
            ("DNA Nucleotide Mapping (A, T, G, C)", ["nucleotide", "base", "adenine", "cytosine", "guanine", "thymine", "atgc"], "Allocates quaternary nucleotide bases to digital information states."),
            ("Encoding Constraints & Homopolymers", ["constraint", "homopolymer", "gc content", "repeat", "run-length", "secondary structure"], "Prevents biochemical synthesis and sequencing dropouts."),
            ("Error-Correcting Codes", ["error-correct", "ecc", "reed-solomon", "inner code", "outer code", "fountain"], "Provides algorithmic redundancy to recover dropped or mutated oligonucleotides."),
        ],
    },
    {
        "title": "DNA Synthesis",
        "type": NodeType.METHOD,
        "keywords": ["synthesis", "synthesize", "synthesizer", "phosphoramidite", "enzymatic", "oligo", "oligonucleotide", "de novo", "microarray"],
        "relationship": "USES",
        "significance": "Physically fabricates designed nucleotide sequences as synthetic DNA strands.",
        "subtopics": [
            ("Phosphoramidite Chemical Synthesis", ["phosphoramidite", "chemical synthesis", "column-based", "solid-phase"], "Traditional chemical oligonucleotide synthesis with high single-base fidelity."),
            ("Enzymatic DNA Synthesis", ["enzymatic", "terminal deoxynucleotidyl transferase", "tdt", "polymerase"], "Template-free enzymatic synthesis enabling faster and environmentally cleaner fabrication."),
            ("Synthesis Accuracy & Yield", ["yield", "fidelity", "synthesis error", "truncation", "deletion", "purity"], "Determines sequence length limits and physical copy yields."),
            ("Synthesis Cost & Scalability", ["synthesis cost", "price per base", "expensive", "throughput", "scalable synthesis"], "Major commercial bottleneck for write-intensive archival storage."),
        ],
    },
    {
        "title": "DNA Storage & Preservation",
        "type": NodeType.CONCEPT,
        "keywords": ["storage", "preserv", "encapsulat", "silica", "dry storage", "stability", "durability", "half-life", "degrad", "temperature", "ambient"],
        "relationship": "PRESERVES",
        "significance": "Maintains chemical integrity and molecular stability over centuries without electrical power.",
        "subtopics": [
            ("Dry DNA Storage", ["dry", "dehydrat", "lyophiliz", "anhydrous", "ambient"], "Water-free preservation preventing hydrolytic backbone cleavage."),
            ("Silica Encapsulation", ["silica", "encapsulat", "nanoparticle", "protective matrix", "inorganic"], "Hermetic physical shielding against reactive oxygen species and environmental fluctuations."),
            ("Temperature & Humidity Control", ["temperature", "humidity", "thermal", "moisture", "activation energy"], "Controls kinetic degradation rates to maximize data retention time."),
            ("Long-Term Preservation", ["long-term", "centuries", "millennia", "durability", "archival", "half-life"], "Guarantees molecular information retention for thousands of years."),
        ],
    },
    {
        "title": "Sequencing and Readout",
        "type": NodeType.METHOD,
        "keywords": ["sequenc", "readout", "illumina", "nanopore", "ngs", "sanger", "short-read", "long-read", "coverage depth"],
        "relationship": "READS",
        "significance": "Reads chemical nucleotide sequences back into digital electronic signals.",
        "subtopics": [
            ("High-Throughput Sequencing", ["high-throughput", "ngs", "illumina", "next-generation"], "Massively parallel short-read sequencing with high per-base accuracy."),
            ("Nanopore Readout", ["nanopore", "oxford nanopore", "long-read", "single-molecule", "pore"], "Real-time single-molecule electronic readout with portable instruments."),
            ("Sequencing Error Profile", ["sequencing error", "indel", "substitution", "noise", "read depth", "coverage"], "Characterizes substitution and deletion noise patterns during data retrieval."),
        ],
    },
    {
        "title": "Data Retrieval and Decoding",
        "type": NodeType.METHOD,
        "keywords": ["retriev", "decod", "random access", "pcr", "primer", "amplificat", "barcode", "address", "reconstruction"],
        "relationship": "RETRIEVES",
        "significance": "Selects specific files from molecular pools and reconstructs binary data.",
        "subtopics": [
            ("PCR Amplification & Primers", ["pcr", "polymerase chain reaction", "amplif", "primer"], "Selectively amplifies target files using file-specific primer sequences."),
            ("Barcode & Random Access Addressing", ["random access", "address", "barcode", "index", "selective"], "Enables non-destructive selective access to individual data blocks."),
            ("DNA-to-Binary Reconstruction", ["reconstruct", "decod", "recovery", "consensus", "reassembly"], "Reassembles aligned sequence reads into the exact original binary file."),
        ],
    },
    {
        "title": "Error Correction and Reliability",
        "type": NodeType.CONCEPT,
        "keywords": ["error", "correct", "reed-solomon", "redundanc", "parity", "indel", "substitution", "integrity", "reliability", "fault-toleran"],
        "relationship": "CORRECTS",
        "significance": "Eliminates biological synthesis and sequencing errors to ensure zero bit loss.",
        "subtopics": [
            ("Redundancy & Overheads", ["redundanc", "overhead", "coverage", "replication", "copies"], "Balances physical synthesis overhead against error-recovery guarantees."),
            ("Indel & Substitution Correction", ["indel", "insertion", "deletion", "substitution", "shift"], "Specialized coding algorithms addressing asymmetric molecular noise."),
            ("Data Integrity & Fault Tolerance", ["integrity", "fault-toleran", "zero error", "perfect recovery", "crc"], "Ensures complete bit-exact recovery under heavy dropout conditions."),
        ],
    },
    {
        "title": "Physical Storage Advantages",
        "type": NodeType.CONCEPT,
        "keywords": ["advantage", "benefit", "density", "capacity", "compact", "longevity", "durability", "energy-free", "petabyte", "exabyte", "outperform"],
        "relationship": "SUPPORTS",
        "significance": "Demonstrates revolutionary advantages over silicon, magnetic tape, and optical media.",
        "subtopics": [
            ("Ultra-High Storage Density", ["density", "exabyte", "petabyte", "per gram", "compact", "volume"], "Reaches up to exabytes per gram of physical biological material."),
            ("Millennial Longevity", ["longevity", "centuries", "millennia", "thousands of years", "durable"], "Retains digital readability for thousands of years without data migration."),
            ("Zero Physical Power Maintenance", ["zero power", "passive", "maintenance-free", "energy-free"], "Eliminates active power and cooling requirements in cold storage archives."),
        ],
    },
    {
        "title": "Technical Challenges",
        "type": NodeType.LIMITATION,
        "keywords": ["challenge", "limitation", "bottleneck", "cost", "speed", "latency", "throughput", "expensive", "slow", "trade-off"],
        "relationship": "CHALLENGES",
        "significance": "Highlights key economic, throughput, and latency hurdles prior to commercial scale.",
        "subtopics": [
            ("Synthesis & Sequencing Cost", ["cost", "expensive", "commercial viability", "dollars per megabyte", "price"], "Orders of magnitude higher cost than enterprise magnetic storage."),
            ("Read/Write Latency & Throughput", ["latency", "slow", "read time", "write speed", "throughput bottleneck"], "Biochemical kinetics limit write and readout response times."),
            ("Random Access Limitations", ["random access", "destructive readout", "pool degradation", "pcr bias"], "Repeated sampling and PCR cycles can bias or deplete target molecular pools."),
        ],
    },
    {
        "title": "Future Scope & Scalability",
        "type": NodeType.CONCEPT,
        "keywords": ["future", "outlook", "automation", "scale", "commercial", "next-generation", "standardization", "emerging"],
        "relationship": "ADVANCES",
        "significance": "Charts the trajectory towards fully automated, cloud-integrated DNA storage centers.",
        "subtopics": [
            ("Automated End-to-End Systems", ["automated", "microfluidic", "integrated", "benchtop", "robot"], "Eliminates manual laboratory pipetting via microfluidic automation."),
            ("Cost Reduction Trajectory", ["cost reduction", "commercial", "scaling", "affordable"], "Technological roadmaps aiming for parity with magnetic archival tape."),
            ("Scalable Enterprise DNA Archives", ["archive", "data center", "cloud", "long-term archival"], "Architectures for integrating molecular storage into enterprise cloud storage."),
        ],
    },
]

GENERAL_BRANCH_DEFINITIONS: list[dict[str, Any]] = [
    {
        "title": "Theoretical Foundations & Objectives",
        "type": NodeType.CONCEPT,
        "keywords": ["objective", "theory", "foundation", "background", "motivation", "principle", "concept"],
        "relationship": "EXPLORES",
        "significance": "Defines core goals, theoretical principles, and mathematical underpinnings.",
    },
    {
        "title": "System Architecture & Pipeline",
        "type": NodeType.METHOD,
        "keywords": ["architecture", "pipeline", "framework", "system", "design", "model", "workflow"],
        "relationship": "USES",
        "significance": "Outlines structural components and data flows of the proposed system.",
    },
    {
        "title": "Methodology & Implementation",
        "type": NodeType.METHOD,
        "keywords": ["method", "algorithm", "technique", "implementation", "process", "approach", "experimental"],
        "relationship": "DETAILS",
        "significance": "Details algorithms, procedures, and experimental protocols executed.",
    },
    {
        "title": "Experimental Findings & Results",
        "type": NodeType.FINDING,
        "keywords": ["result", "finding", "experiment", "accuracy", "performance", "metric", "measurement", "benchmark"],
        "relationship": "REPORTS",
        "significance": "Reports measured empirical data, benchmark comparisons, and experimental outcomes.",
    },
    {
        "title": "Comparative Advantages",
        "type": NodeType.CONCEPT,
        "keywords": ["advantage", "benefit", "outperform", "superior", "efficient", "improvement", "strength"],
        "relationship": "SUPPORTS",
        "significance": "Demonstrates measurable superiority or improvements over prior baseline methods.",
    },
    {
        "title": "Technical Limitations & Challenges",
        "type": NodeType.LIMITATION,
        "keywords": ["limitation", "drawback", "bottleneck", "challenge", "error", "trade-off", "constraint", "weakness"],
        "relationship": "LIMITS",
        "significance": "Documents boundary conditions, error rates, and unresolved challenges.",
    },
    {
        "title": "Future Scope & Extensions",
        "type": NodeType.CONCEPT,
        "keywords": ["future", "extension", "outlook", "potential", "direction", "scale", "next step"],
        "relationship": "ADVANCES",
        "significance": "Identifies avenues for scaling, enhancement, and future investigation.",
    },
]


# ==============================================================================
# ENGINE IMPLEMENTATION
# ==============================================================================

class KnowledgeMindMapEngine:
    """
    Evidence-grounded knowledge mind-map generator.

    Converts retrieved research evidence into structured nodes and relationships
    rendered as an interactive graph by the frontend.
    """

    def extract_clean_topic(
        self,
        query: str,
        evidence: list[dict[str, Any]] | None = None,
    ) -> str:
        return extract_clean_topic(query, evidence)

    def build_mind_map_prompt(
        self,
        *,
        query: str,
        evidence: list[dict[str, Any]],
    ) -> str:
        evidence_blocks: list[str] = []
        for index, item in enumerate(evidence, start=1):
            cid = item.get("chunk_id", f"chunk_{index}")
            doc = item.get("document", "Unknown")
            page = item.get("page", "N/A")
            raw_t = item.get("text", "").strip()
            clean_t = " ".join(raw_t.split())
            evidence_blocks.append(f"[{cid}] doc: {doc} | page: {page}\n{clean_t}")

        evidence_text = "\n\n".join(evidence_blocks)
        clean_topic = extract_clean_topic(query, evidence)

        return f"""You are the Knowledge Mind Map Engine of UNKNOWN.
Construct an evidence-grounded hierarchical knowledge mind map strictly from the supplied evidence catalog.

RESEARCH QUERY:
{query}

SUGGESTED TOPIC TITLE:
{clean_topic}

DOCUMENT EVIDENCE CATALOG:
{evidence_text}

STRICT INSTRUCTIONS:
1. Ground every node and edge strictly in the cited evidence catalog. Do not fabricate concepts or relationships.
2. Structure:
   - 1 Central Topic node (id: "root", type: "TOPIC"):
     MUST be a short, clean, descriptive topic title (2-4 words, e.g. "{clean_topic}").
     NEVER use the full user prompt or query sentences as the central topic label.
   - 6-10 Domain-Specific Major Branches (type: "CONCEPT" or "METHOD", parent_id: "root") representing major areas supported by evidence (e.g., Data Encoding, DNA Synthesis, DNA Storage & Preservation, Sequencing & Readout, Data Retrieval, Error Correction, Physical Advantages, Technical Challenges, Future Scope).
   - 2-4 Subtopics under each major branch (type: "FINDING" or "LIMITATION") citing specific details.
   - Edges connecting root -> major branches and major branches -> subtopics.
3. Leaf node quality:
   - Titles MUST be short, clean, meaningful phrases (3-7 words, e.g. "Binary-to-DNA Conversion", "Phosphoramidite Chemical Synthesis").
   - NEVER truncate sentences with ellipsis '...' or use raw sentence beginnings as titles.
   - Provide a complete, informative sentence in "description".
   - Include 1 sentence in "significance" explaining why the concept matters.
   - Every non-root node MUST cite: document, page, chunk_id, and exact supporting evidence passage.
4. Edge relationships: "EXPLORES", "USES", "PRESERVES", "READS", "RETRIEVES", "CORRECTS", "SUPPORTS", "CHALLENGES", "ADVANCES", "DETAILS".
5. Return ONLY a single valid JSON object adhering to this schema with NO markdown fences:

{{
  "query": "{query}",
  "research_area": "{clean_topic}",
  "nodes": [
    {{
      "id": "root",
      "label": "{clean_topic}",
      "type": "TOPIC",
      "description": "Evidence-grounded knowledge mind map for {clean_topic}.",
      "significance": "Central thematic root organizing key research dimensions.",
      "parent_id": null,
      "document": "",
      "page": "",
      "chunk_id": "",
      "evidence": [],
      "confidence": 1.0
    }},
    {{
      "id": "branch_1",
      "label": "Data Encoding",
      "type": "METHOD",
      "description": "Encoding digital bits into nucleotide sequences.",
      "significance": "Determines mapping constraints and error-correction density.",
      "parent_id": "root",
      "document": "doc_name.pdf",
      "page": 1,
      "chunk_id": "chunk_1",
      "evidence": ["Exact excerpt quote"],
      "confidence": 0.95
    }}
  ],
  "edges": [
    {{
      "source": "root",
      "target": "branch_1",
      "relationship": "USES",
      "evidence": "Brief supporting evidence quote",
      "confidence": 0.95
    }}
  ],
  "sources": [
    {{
      "document": "doc_name.pdf",
      "page": 1,
      "chunk_id": "chunk_1"
    }}
  ]
}}""".strip()

    def build_no_llm_mind_map(
        self,
        *,
        query: str,
        evidence: list[dict[str, Any]],
        document_names: list[str] | None = None,
    ) -> KnowledgeMindMap:
        """
        Build a deterministic, evidence-grounded hierarchical mind map directly
        from retrieved document chunks when LLM providers are unavailable.
        Never fabricates concepts, citations, or unsupported edges.
        """
        root_id = "root"
        central_label = extract_clean_topic(query, evidence)

        nodes: list[MindMapNode] = [
            MindMapNode(
                id=root_id,
                label=central_label,
                type=NodeType.TOPIC,
                description=f"Central research topic: {central_label}",
                significance="Central thematic root organizing evidence across retrieved documents.",
                evidence=[],
                confidence=1.0,
                parent_id=None,
                children=[],
            )
        ]
        edges: list[MindMapEdge] = []
        node_ids: set[str] = {root_id}

        # Check domain to pick branch definitions
        all_text = " ".join((item.get("text") or "").lower() for item in evidence)
        q_lower = query.lower()
        is_dna_domain = (
            "dna" in q_lower
            or "storage" in q_lower
            or "oligo" in all_text
            or "nucleotide" in all_text
            or "synthes" in all_text
        )

        branch_defs = DNA_BRANCH_DEFINITIONS if is_dna_domain else GENERAL_BRANCH_DEFINITIONS

        seen_labels: set[str] = {central_label.lower()}
        seen_sentences: set[str] = set()
        branch_idx = 1

        for b_def in branch_defs:
            b_title = b_def["title"]
            b_type = b_def["type"]
            b_kws = b_def["keywords"]
            b_rel = b_def.get("relationship", "EXPLORES")
            b_sig = b_def.get("significance", f"Investigates {b_title} across available evidence.")
            subtopic_defs = b_def.get("subtopics", [])

            # Find matching chunks
            matching_chunks: list[dict[str, Any]] = []
            for item in evidence:
                text = item.get("text", "")
                if any(kw in text.lower() for kw in b_kws):
                    matching_chunks.append(item)

            if not matching_chunks:
                continue

            branch_id = f"branch_{branch_idx}"
            top_chunk = matching_chunks[0]
            top_text = top_chunk.get("text", "").strip()
            clean_top = " ".join(top_text.split())[:180]

            branch_node = MindMapNode(
                id=branch_id,
                label=b_title,
                type=b_type,
                description=f"Evidence-grounded branch: {b_title}.",
                significance=b_sig,
                evidence=[clean_top] if clean_top else [],
                confidence=0.9,
                document=top_chunk.get("document", ""),
                page=top_chunk.get("page", 1),
                chunk_id=top_chunk.get("chunk_id", f"chunk_{branch_idx}"),
                parent_id=root_id,
                children=[],
            )
            nodes.append(branch_node)
            node_ids.add(branch_id)
            nodes[0].children.append(branch_id)
            seen_labels.add(b_title.lower())

            edges.append(
                MindMapEdge(
                    source=root_id,
                    target=branch_id,
                    relationship=b_rel,
                    evidence=clean_top or b_title,
                    confidence=0.9,
                )
            )

            # Sub-branches / leaf nodes under this main branch
            sub_count = 0

            # 1. First attempt to match domain subtopic definitions across chunks
            if subtopic_defs:
                for sub_title, sub_kws, sub_signif in subtopic_defs:
                    for chunk in matching_chunks:
                        c_text = chunk.get("text", "")
                        raw_sents = re.split(r"(?<=[.!?])\s+", c_text)
                        matched_sent = None
                        for s in raw_sents:
                            s_clean = " ".join(s.split())
                            s_key = s_clean[:80].lower()
                            if len(s_clean) >= 30 and any(kw in s_clean.lower() for kw in sub_kws) and s_key not in seen_sentences:
                                matched_sent = s_clean
                                seen_sentences.add(s_key)
                                break

                        if matched_sent:
                            leaf_label = extract_clean_leaf_title(matched_sent, sub_title)
                            if leaf_label.lower() in seen_labels:
                                leaf_label = sub_title
                            seen_labels.add(leaf_label.lower())

                            sub_id = f"sub_{branch_idx}_{sub_count + 1}"
                            if sub_id not in node_ids:
                                sub_node = MindMapNode(
                                    id=sub_id,
                                    label=leaf_label,
                                    type=b_type,
                                    description=matched_sent,
                                    significance=sub_signif,
                                    evidence=[matched_sent],
                                    confidence=0.88,
                                    document=chunk.get("document", ""),
                                    page=chunk.get("page", 1),
                                    chunk_id=chunk.get("chunk_id", f"chunk_{branch_idx}_{sub_count}"),
                                    parent_id=branch_id,
                                    children=[],
                                )
                                nodes.append(sub_node)
                                node_ids.add(sub_id)
                                branch_node.children.append(sub_id)

                                edges.append(
                                    MindMapEdge(
                                        source=branch_id,
                                        target=sub_id,
                                        relationship="DETAILS",
                                        evidence=matched_sent[:120],
                                        confidence=0.88,
                                    )
                                )
                                sub_count += 1
                                if sub_count >= 3:
                                    break
                    if sub_count >= 3:
                        break

            # 2. If fewer than 2 subtopics found, extract clean sentences directly from chunks
            if sub_count < 2:
                # Prioritize distinct documents if available
                seen_docs: set[str] = {n.document for n in nodes if n.parent_id == branch_id and n.document}
                for chunk in matching_chunks:
                    doc = chunk.get("document", "")
                    c_text = chunk.get("text", "")
                    raw_sents = re.split(r"(?<=[.!?])\s+", c_text)
                    for s in raw_sents:
                        s_clean = " ".join(s.split())
                        s_key = s_clean[:80].lower()
                        if len(s_clean) >= 35 and any(kw in s_clean.lower() for kw in b_kws) and s_key not in seen_sentences:
                            seen_sentences.add(s_key)
                            leaf_label = extract_clean_leaf_title(s_clean, f"{b_title} Detail")
                            if leaf_label.lower() in seen_labels:
                                continue
                            seen_labels.add(leaf_label.lower())

                            sub_id = f"sub_{branch_idx}_{sub_count + 1}"
                            if sub_id not in node_ids:
                                sub_node = MindMapNode(
                                    id=sub_id,
                                    label=leaf_label,
                                    type=b_type,
                                    description=s_clean,
                                    significance=b_sig,
                                    evidence=[s_clean],
                                    confidence=0.85,
                                    document=doc,
                                    page=chunk.get("page", 1),
                                    chunk_id=chunk.get("chunk_id", f"chunk_{branch_idx}_{sub_count}"),
                                    parent_id=branch_id,
                                    children=[],
                                )
                                nodes.append(sub_node)
                                node_ids.add(sub_id)
                                branch_node.children.append(sub_id)

                                edges.append(
                                    MindMapEdge(
                                        source=branch_id,
                                        target=sub_id,
                                        relationship="DETAILS",
                                        evidence=s_clean[:120],
                                        confidence=0.85,
                                    )
                                )
                                sub_count += 1
                                seen_docs.add(doc)
                                if sub_count >= 2:
                                    break
                    if sub_count >= 2:
                        break

            branch_idx += 1

        # Fallback if no specific keywords matched: build branches per document
        if len(nodes) == 1 and evidence:
            for i, chunk in enumerate(evidence[:4], start=1):
                b_id = f"branch_{i}"
                doc = chunk.get("document", "Document")
                p = chunk.get("page", 1)
                cid = chunk.get("chunk_id", f"chunk_{i}")
                raw_t = chunk.get("text", "").strip()
                clean_t = " ".join(raw_t.split())
                label = extract_clean_leaf_title(clean_t, f"{doc} Overview")
                nodes.append(
                    MindMapNode(
                        id=b_id,
                        label=label,
                        type=NodeType.CONCEPT,
                        description=clean_t[:180],
                        significance="Direct evidence from document source.",
                        evidence=[clean_t[:180]],
                        confidence=0.85,
                        document=doc,
                        page=p,
                        chunk_id=cid,
                        parent_id=root_id,
                        children=[],
                    )
                )
                node_ids.add(b_id)
                nodes[0].children.append(b_id)
                edges.append(
                    MindMapEdge(
                        source=root_id,
                        target=b_id,
                        relationship="EXPLORES",
                        evidence=clean_t[:100],
                        confidence=0.85,
                    )
                )

        sources: list[dict[str, Any]] = []
        seen_src = set()
        for item in evidence:
            d = item.get("document", "Unknown")
            p = item.get("page", 1)
            cid = item.get("chunk_id", "")
            if cid and cid not in seen_src:
                seen_src.add(cid)
                sources.append({"document": d, "page": p, "chunk_id": cid})

        return KnowledgeMindMap(
            query=query,
            research_area=central_label,
            nodes=nodes,
            edges=edges,
            sources=sources,
            partial=True,
            notice="Limited mind map — generated from available evidence because AI providers were unavailable.",
        )

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        if not text or not text.strip():
            raise ValueError("Knowledge mind map engine returned an empty response.")

        cleaned = text.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise ValueError("Knowledge mind map engine returned invalid JSON.") from None
            try:
                value = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError as error:
                raise ValueError("Knowledge mind map engine returned invalid JSON.") from error

        if not isinstance(value, dict):
            raise ValueError("Knowledge mind map response must be a JSON object.")

        return value

    @staticmethod
    def _parse_node(value: Any) -> MindMapNode:
        if not isinstance(value, dict):
            raise ValueError("Invalid mind map node.")

        raw_type = value.get("type", "CONCEPT")
        if isinstance(raw_type, str):
            raw_upper = raw_type.upper()
            try:
                node_type = NodeType(raw_upper)
            except ValueError:
                node_type = NodeType.CONCEPT
        else:
            node_type = NodeType.CONCEPT

        raw_label = str(value.get("label", "")).strip()
        # Clean trailing ellipsis if present
        clean_label = re.sub(r"(?:\.{3}|…)$", "", raw_label).strip()

        return MindMapNode(
            id=str(value.get("id", "")).strip(),
            label=clean_label or raw_label,
            type=node_type,
            description=str(value.get("description", "")).strip(),
            evidence=value.get("evidence", []) if isinstance(value.get("evidence"), list) else [str(value.get("evidence"))] if value.get("evidence") else [],
            confidence=float(value.get("confidence", 0.9)),
            document=str(value.get("document", "")).strip(),
            page=value.get("page", ""),
            chunk_id=str(value.get("chunk_id", "")).strip(),
            parent_id=value.get("parent_id"),
            children=value.get("children", []) if isinstance(value.get("children"), list) else [],
            significance=str(value.get("significance", "")).strip(),
        )

    @staticmethod
    def _parse_edge(value: Any) -> MindMapEdge:
        if not isinstance(value, dict):
            raise ValueError("Invalid mind map edge.")

        return MindMapEdge(
            source=value.get("source", ""),
            target=value.get("target", ""),
            relationship=value.get("relationship", ""),
            evidence=value.get("evidence", ""),
            confidence=value.get("confidence", 0.0),
        )

    @staticmethod
    def _parse_sources(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        sources: list[dict[str, Any]] = []
        for source in value:
            if not isinstance(source, dict):
                continue
            sources.append(
                {
                    "document": source.get("document", ""),
                    "page": source.get("page", ""),
                    "chunk_id": source.get("chunk_id", ""),
                }
            )

        return sources

    def parse_response(
        self,
        *,
        query: str,
        response_text: str,
    ) -> KnowledgeMindMap:
        payload = self._extract_json(response_text)

        nodes = [self._parse_node(item) for item in payload.get("nodes", [])]
        edges = [self._parse_edge(item) for item in payload.get("edges", [])]

        clean_topic = extract_clean_topic(query)
        # Ensure root node has a clean, meaningful topic title
        for node in nodes:
            if node.id == "root" or node.type == NodeType.TOPIC:
                if len(node.label.split()) > 5 or node.label.lower() == query.strip().lower() or "mind map" in node.label.lower():
                    node.label = clean_topic

        node_ids = {node.id for node in nodes}

        # Reject edges that point to nodes which do not exist
        for edge in edges:
            if edge.source not in node_ids:
                raise ValueError(f"Mind map edge references unknown source node: {edge.source}")
            if edge.target not in node_ids:
                raise ValueError(f"Mind map edge references unknown target node: {edge.target}")

        # Populate hierarchy (parent_id, children) from edges if not already present
        children_map: dict[str, list[str]] = {}
        parent_map: dict[str, str] = {}
        for edge in edges:
            children_map.setdefault(edge.source, []).append(edge.target)
            if edge.target not in parent_map:
                parent_map[edge.target] = edge.source

        for node in nodes:
            if not node.parent_id and node.id in parent_map:
                node.parent_id = parent_map[node.id]
            if not node.children and node.id in children_map:
                node.children = children_map[node.id]

        res_area = payload.get("research_area", clean_topic)
        if len(res_area.split()) > 5 or res_area.lower() == query.strip().lower() or "mind map" in res_area.lower():
            res_area = clean_topic

        return KnowledgeMindMap(
            query=query,
            research_area=res_area,
            nodes=nodes,
            edges=edges,
            sources=self._parse_sources(payload.get("sources", [])),
            partial=payload.get("partial", False),
            notice=payload.get("notice"),
        )
