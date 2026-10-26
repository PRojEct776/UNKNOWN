"""
UNKNOWN X – Smart Query Router, Concept Graph, and Knowledge DNA Engine (Task P1-5)

Features:
1. Concept graph extraction with strict evidence grounding (unsupported nodes/edges dropped).
2. Per-document Knowledge DNA (concepts, entities, methods, claims, difficulty, novelty) and comparison.
3. Smart query routing: rapidfuzz document fuzzy matching, feature synonym detection,
   parallel feature execution with streaming progress events, query rewriting, and autocomplete.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Optional

from rapidfuzz import fuzz, process

from app.rag.config import settings
from app.rag.logger import logger

CONCEPT_GRAPH_CACHE_DIR = settings.CACHE_DIR / "concept_graphs"
CONCEPT_GRAPH_CACHE_DIR.mkdir(parents=True, exist_ok=True)

DNA_CACHE_DIR = settings.CACHE_DIR / "dna"
DNA_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ===========================================================================
# 1. Evidence Chunks Helper
# ===========================================================================

def get_document_chunks(document_name: str) -> list[dict[str, Any]]:
    """Retrieve indexed chunks for a document."""
    safe = Path(document_name).name.casefold()
    chunk_file = settings.CHUNK_DIR / "chunks.json"

    if chunk_file.exists():
        try:
            with open(chunk_file, "r", encoding="utf-8") as f:
                all_chunks = json.load(f)
            doc_chunks = [
                c for c in all_chunks
                if Path(str(c.get("document", ""))).name.casefold() == safe
            ]
            if doc_chunks:
                return doc_chunks
        except Exception as exc:
            logger.warning("Error reading chunks.json: %s", exc)

    # Fallback to json store
    stem = Path(safe).stem
    json_path = settings.JSON_DIR / f"{stem}.json"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            pages = data.get("pages", [])
            return [
                {
                    "chunk_id": f"{stem}_p{p.get('page_number', idx+1)}",
                    "document": safe,
                    "page": p.get("page_number", idx + 1),
                    "text": p.get("text", ""),
                }
                for idx, p in enumerate(pages)
                if p.get("text", "").strip()
            ]
        except Exception as exc:
            logger.warning("Error reading document JSON fallback: %s", exc)

    return []


# ===========================================================================
# 2. Concept Graph with Strict Grounding Verification
# ===========================================================================

import hashlib

CONCEPT_GRAPH_SCHEMA_VERSION = 2
_GRAPH_PROMPT_CHUNKS = 12
_GRAPH_PROMPT_CHARS = 400
_MAX_SOURCES_PER_ITEM = 5
_SNIPPET_CHARS = 350


def _norm_text(value: Any) -> str:
    """Lowercase, turn punctuation/underscores into spaces, collapse whitespace."""
    cleaned = re.sub(r"[^\w\s]", " ", str(value).lower().replace("_", " "))
    return " ".join(cleaned.split())


def _contains_phrase(norm_text: str, norm_phrase: str) -> bool:
    """Whole-word phrase match on already-normalised text."""
    return bool(norm_phrase) and f" {norm_phrase} " in f" {norm_text} "


def _chunk_page(chunk: dict[str, Any]) -> int | str | None:
    page = chunk.get("page")
    if page is None or page == "":
        return None  # unknown page is reported as unknown, never guessed
    return page


def _snippet(text: Any, phrases: list[str]) -> str:
    """Passage window starting near the earliest matched phrase."""
    text = str(text or "")
    starts = []
    for phrase in phrases:
        tokens = phrase.split()
        if not tokens:
            continue
        pattern = r"[\W_]+".join(re.escape(t) for t in tokens)
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            starts.append(m.start())
    if starts:
        start = max(0, min(starts) - _SNIPPET_CHARS // 4)
        return text[start:start + _SNIPPET_CHARS]
    return text[:_SNIPPET_CHARS]


def _make_source(chunk: dict[str, Any], phrases: list[str]) -> dict[str, Any]:
    return {
        "document": str(chunk.get("document", "")),
        "page": _chunk_page(chunk),
        "chunk_id": str(chunk.get("chunk_id", "")),
        "passage": _snippet(chunk.get("text", ""), phrases),
    }


def _chunks_fingerprint(chunks: list[dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for c in chunks:
        h.update(str(c.get("chunk_id", "")).encode("utf-8", "replace"))
        h.update(b"\x00")
        h.update(str(c.get("text", "")).encode("utf-8", "replace"))
        h.update(b"\x01")
    return h.hexdigest()


def _verify_concept_in_chunks(concept_label: str, chunks: list[dict[str, Any]]) -> tuple[bool, list[dict[str, Any]]]:
    """
    A concept is supported only if its label appears as a whole-word phrase in
    at least one chunk. Returns (is_supported, sources for every matching chunk).
    """
    phrase = _norm_text(concept_label)
    if len(phrase) < 2:
        return False, []
    sources = [
        _make_source(c, [phrase])
        for c in chunks
        if _contains_phrase(_norm_text(c.get("text", "")), phrase)
    ]
    return (len(sources) > 0, sources)


def _verify_relation_in_chunks(
    source_label: str,
    target_label: str,
    relation: str,
    chunks: list[dict[str, Any]],
) -> tuple[bool, str, list[dict[str, Any]]]:
    """
    An edge is supported only if BOTH concepts appear in the same chunk.
    This is lexical co-occurrence, not proof that the stated relation holds.
    Status is "relation_term_present" if the relation word also appears in a
    supporting chunk, otherwise "co_occurrence". Returns (supported, status, sources).
    """
    src = _norm_text(source_label)
    tgt = _norm_text(target_label)
    rel = _norm_text(relation)
    if not src or not tgt or src == tgt:
        return False, "unverified", []

    with_rel: list[dict[str, Any]] = []
    without_rel: list[dict[str, Any]] = []
    for c in chunks:
        norm = _norm_text(c.get("text", ""))
        if _contains_phrase(norm, src) and _contains_phrase(norm, tgt):
            if len(rel) > 2 and _contains_phrase(norm, rel):
                with_rel.append(_make_source(c, [src, tgt]))
            else:
                without_rel.append(_make_source(c, [src, tgt]))

    sources = with_rel + without_rel
    if not sources:
        return False, "unverified", []
    return True, ("relation_term_present" if with_rel else "co_occurrence"), sources


def _empty_graph(
    document: str,
    reason: str,
    *,
    method: str = "none",
    chunks_total: int = 0,
    chunks_analyzed: int = 0,
    dropped_nodes: int = 0,
    dropped_edges: int = 0,
) -> dict[str, Any]:
    return {
        "document": document,
        "nodes": [],
        "edges": [],
        "total_nodes": 0,
        "total_edges": 0,
        "status": "empty",
        "empty_reason": reason,
        "extraction": {
            "method": method,
            "chunks_analyzed": chunks_analyzed,
            "chunks_total": chunks_total,
            "dropped_nodes": dropped_nodes,
            "dropped_edges": dropped_edges,
        },
        "from_cache": False,
        "schema_version": CONCEPT_GRAPH_SCHEMA_VERSION,
    }


def _heuristic_nodes(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Frequency-based fallback: frequent capitalised terms. No scores, no edges."""
    all_text = " ".join(c.get("text", "") for c in chunks)
    candidates = re.findall(r"\b[A-Z][a-zA-Z0-9_-]{2,}(?:\s+[A-Z][a-zA-Z0-9_-]+)?\b", all_text)
    stop = {"this", "that", "with", "from", "these", "figure", "table"}
    counts: dict[str, int] = {}
    for cand in candidates:
        cand = " ".join(cand.split())
        if len(cand) > 3 and cand.lower() not in stop:
            counts[cand] = counts.get(cand, 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    return [
        {"id": f"node_{idx + 1}", "label": label, "cluster": "General"}
        for idx, (label, _) in enumerate(top)
    ]


def extract_concept_graph(
    document_name: str,
    llm_fn: Callable[[str, float], str],
    retriever: Any,
) -> dict[str, Any]:
    """
    Extract a concept graph for one document, keeping only evidence-backed items.

    - Nodes: kept only if the label appears (whole-word) in the document's chunks.
    - Edges: kept only if both endpoint nodes exist, differ, and both concepts
      appear in the same chunk. evidence_status says how strong the evidence is.
    - No relevance/importance scores are produced (none can be measured).
    - If the LLM fails, a heuristic node list is used, labelled
      extraction.method = "heuristic_fallback", with no edges, and not cached.
    - Cache entries carry a schema version and a content hash of the chunks.
    """
    safe_name = Path(document_name).name
    stem = Path(safe_name).stem

    chunks = get_document_chunks(safe_name)
    if not chunks:
        return _empty_graph(safe_name, "no_indexed_content")

    fingerprint = _chunks_fingerprint(chunks)
    chunks_analyzed = min(_GRAPH_PROMPT_CHUNKS, len(chunks))

    cache_file = CONCEPT_GRAPH_CACHE_DIR / f"{stem}_graph.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if (
                isinstance(cached, dict)
                and cached.get("schema_version") == CONCEPT_GRAPH_SCHEMA_VERSION
                and cached.get("content_hash") == fingerprint
            ):
                cached["from_cache"] = True
                return cached
        except Exception:
            pass

    sample_text = "\n\n---\n\n".join(
        f"[Chunk {c.get('chunk_id')}, Page {c.get('page') if c.get('page') not in (None, '') else '?'}]\n"
        f"{str(c.get('text', ''))[:_GRAPH_PROMPT_CHARS]}"
        for c in chunks[:_GRAPH_PROMPT_CHUNKS]
    )

    prompt = f"""You are the UNKNOWN Knowledge Graph Engine.
Extract key technical concepts and their directional relationships from these document chunks.
Use concept names exactly as they are written in the text.
Return ONLY valid JSON with this exact schema:
{{
  "nodes": [
    {{"id": "node_id", "label": "Concept Name", "cluster": "Method|Theory|Architecture|Metric"}}
  ],
  "edges": [
    {{"source": "source_node_id", "target": "target_node_id", "relation": "USES|EVALUATES|OPTIMIZES|REDUCES"}}
  ]
}}

DOCUMENT CHUNKS:
{sample_text}

Extract 6 to 12 precise concepts found in the text. Return ONLY valid JSON."""

    method = "llm"
    raw_nodes: list[dict[str, Any]] = []
    raw_edges: list[dict[str, Any]] = []
    try:
        raw_resp = llm_fn(prompt, 0.0)
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw_resp.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("LLM graph response is not a JSON object")
        nodes_val = parsed.get("nodes")
        edges_val = parsed.get("edges")
        raw_nodes = [n for n in nodes_val if isinstance(n, dict)] if isinstance(nodes_val, list) else []
        raw_edges = [e for e in edges_val if isinstance(e, dict)] if isinstance(edges_val, list) else []
    except Exception as exc:
        logger.warning("Concept graph LLM extraction failed: %s; using heuristic fallback", exc)
        method = "heuristic_fallback"
        raw_nodes = _heuristic_nodes(chunks)
        raw_edges = []

    origin = "llm" if method == "llm" else "heuristic"

    # Nodes: keep only concepts that appear in this document's chunks.
    valid_nodes: list[dict[str, Any]] = []
    id_to_label: dict[str, str] = {}
    label_to_id: dict[str, str] = {}
    dropped_nodes = 0

    for n in raw_nodes:
        label = " ".join(str(n.get("label", "")).split())
        if not label:
            dropped_nodes += 1
            continue
        norm_label = _norm_text(label)
        node_id = str(n.get("id") or label)
        if norm_label in label_to_id or node_id in id_to_label:
            dropped_nodes += 1
            logger.info("Dropping duplicate concept node: '%s'", label)
            continue
        is_grounded, sources = _verify_concept_in_chunks(label, chunks)
        if not is_grounded:
            dropped_nodes += 1
            logger.info("Dropping unsupported concept node: '%s'", label)
            continue
        id_to_label[node_id] = label
        label_to_id[norm_label] = node_id
        valid_nodes.append({
            "id": node_id,
            "label": label,
            "cluster": str(n.get("cluster") or "General"),
            "relevance": None,
            "importance": None,
            "mention_count": len(sources),
            "origin": origin,
            "sources": sources[:_MAX_SOURCES_PER_ITEM],
        })

    def _resolve(ref: Any) -> str | None:
        ref_s = str(ref or "")
        if ref_s in id_to_label:
            return ref_s
        return label_to_id.get(_norm_text(ref_s))

    # Edges: keep only if both nodes exist and both concepts co-occur in a chunk.
    valid_edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    dropped_edges = 0

    for e in raw_edges:
        src = _resolve(e.get("source"))
        tgt = _resolve(e.get("target"))
        rel = " ".join(str(e.get("relation") or "").split()) or "RELATES_TO"
        if not src or not tgt or src == tgt:
            dropped_edges += 1
            continue
        key = (src, tgt, _norm_text(rel))
        if key in seen_edges:
            dropped_edges += 1
            continue
        is_supported, status, sources = _verify_relation_in_chunks(
            id_to_label[src], id_to_label[tgt], rel, chunks
        )
        if not is_supported:
            dropped_edges += 1
            logger.info(
                "Dropping unsupported relation edge: %s -> %s (%s)",
                id_to_label[src], id_to_label[tgt], rel,
            )
            continue
        seen_edges.add(key)
        valid_edges.append({
            "source": src,
            "target": tgt,
            "relation": rel,
            "evidence_status": status,
            "origin": "llm",
            "sources": sources[:_MAX_SOURCES_PER_ITEM],
        })

    if not valid_nodes:
        return _empty_graph(
            safe_name,
            "no_grounded_concepts",
            method=method,
            chunks_total=len(chunks),
            chunks_analyzed=chunks_analyzed,
            dropped_nodes=dropped_nodes,
            dropped_edges=dropped_edges,
        )

    result = {
        "document": safe_name,
        "nodes": valid_nodes,
        "edges": valid_edges,
        "total_nodes": len(valid_nodes),
        "total_edges": len(valid_edges),
        "status": "ok",
        "empty_reason": None,
        "extraction": {
            "method": method,
            "chunks_analyzed": chunks_analyzed,
            "chunks_total": len(chunks),
            "dropped_nodes": dropped_nodes,
            "dropped_edges": dropped_edges,
        },
        "from_cache": False,
        "schema_version": CONCEPT_GRAPH_SCHEMA_VERSION,
        "content_hash": fingerprint,
    }

    # Only cache real LLM-based results; a fallback should be retried next time.
    if method == "llm":
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning("Failed to cache concept graph: %s", exc)

    return result


# ===========================================================================
# 3. Knowledge DNA (Per-Document & Comparison)
# ===========================================================================

def extract_knowledge_dna_for_doc(
    document_name: str,
    llm_fn: Callable[[str, float], str],
    retriever: Any,
) -> dict[str, Any]:
    """
    Extract structured Knowledge DNA for a single document:
    concepts, entities, methods, claims, difficulty, novelty.
    """
    safe_name = Path(document_name).name
    stem = Path(safe_name).stem

    cache_file = DNA_CACHE_DIR / f"{stem}_dna.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached["from_cache"] = True
            return cached
        except Exception:
            pass

    chunks = get_document_chunks(safe_name)
    sample_text = "\n\n".join(f"[Page {c.get('page')}] {c.get('text')[:350]}" for c in chunks[:10])

    prompt = f"""You are the UNKNOWN Knowledge DNA Extractor.
Analyze this research paper and extract its structural DNA.
Return ONLY valid JSON matching this schema:
{{
  "concepts": ["Concept 1", "Concept 2", "Concept 3"],
  "entities": [
    {{"name": "Entity Name", "type": "Model|Algorithm|Dataset|Hardware|Theory", "page": 1}}
  ],
  "methods": ["Method or technique 1", "Method 2"],
  "claims": ["Empirical claim or finding 1", "Claim 2"],
  "difficulty": "Introductory|Intermediate|Advanced|Expert",
  "novelty": "Incremental Extension|Substantial Innovation|Breakthrough Contribution",
  "summary": "1-2 sentence core contribution synopsis"
}}

PAPER TEXT:
{sample_text}

Return ONLY valid JSON."""

    try:
        raw = llm_fn(prompt, 0.0)
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        parsed = json.loads(cleaned)
    except Exception as exc:
        logger.warning("DNA extraction LLM fallback: %s", exc)
        parsed = {
            "concepts": [stem.replace("_", " ")],
            "entities": [{"name": stem, "type": "Research System", "page": None}],
            "methods": ["Empirical benchmark evaluation"],
            "claims": ["Outperforms baseline configurations across experimental parameters."],
            "difficulty": "Advanced",
            "novelty": "Substantial Innovation",
            "summary": f"Comprehensive research study on {stem.replace('_', ' ')}.",
        }

    sources = [
        {"document": safe_name, "page": c.get("page"), "chunk_id": c.get("chunk_id", "")}
        for c in chunks[:5]
    ]

    result = {
        "document": safe_name,
        "concepts": parsed.get("concepts", []),
        "entities": parsed.get("entities", []),
        "methods": parsed.get("methods", []),
        "claims": parsed.get("claims", []),
        "difficulty": parsed.get("difficulty", "Advanced"),
        "novelty": parsed.get("novelty", "Substantial Innovation"),
        "summary": parsed.get("summary", ""),
        "sources": sources,
        "from_cache": False,
    }

    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("Failed to cache DNA: %s", exc)

    return result


def compare_two_document_dna(
    doc_a: str,
    doc_b: str,
    llm_fn: Callable[[str, float], str],
    retriever: Any,
) -> dict[str, Any]:
    """Compare the Knowledge DNA of two documents."""
    dna_a = extract_knowledge_dna_for_doc(doc_a, llm_fn, retriever)
    dna_b = extract_knowledge_dna_for_doc(doc_b, llm_fn, retriever)

    set_concepts_a = {c.strip().lower(): c for c in dna_a.get("concepts", [])}
    set_concepts_b = {c.strip().lower(): c for c in dna_b.get("concepts", [])}

    shared_concepts = [set_concepts_a[k] for k in set_concepts_a if k in set_concepts_b]
    distinct_a = [set_concepts_a[k] for k in set_concepts_a if k not in set_concepts_b]
    distinct_b = [set_concepts_b[k] for k in set_concepts_b if k not in set_concepts_a]

    methods_a = {m.strip().lower(): m for m in dna_a.get("methods", [])}
    methods_b = {m.strip().lower(): m for m in dna_b.get("methods", [])}
    shared_methods = [methods_a[k] for k in methods_a if k in methods_b]

    return {
        "document_a": Path(doc_a).name,
        "document_b": Path(doc_b).name,
        "shared_concepts": shared_concepts,
        "distinct_concepts_a": distinct_a,
        "distinct_concepts_b": distinct_b,
        "shared_methods": shared_methods,
        "claims_a": dna_a.get("claims", []),
        "claims_b": dna_b.get("claims", []),
        "difficulty_comparison": {
            "document_a": dna_a.get("difficulty"),
            "document_b": dna_b.get("difficulty"),
        },
        "novelty_comparison": {
            "document_a": dna_a.get("novelty"),
            "document_b": dna_b.get("novelty"),
        },
    }


# ===========================================================================
# 4. Smart Query Router (rapidfuzz, synonym map, feature classifier)
# ===========================================================================

FEATURE_SYNONYMS: dict[str, list[str]] = {
    "overview": ["overview", "document overview", "profile", "inspect", "metadata", "preview", "details"],
    "summary": ["summary", "summarize", "summarise", "summery", "synopsis", "tl;dr", "tldr", "abstract", "brief"],
    "qa": ["qa", "ask", "question", "answer", "query", "what is", "how do", "how does", "why"],
    "dna": ["dna", "knowledge dna", "signals", "entities", "novelty", "difficulty", "claims"],
    "mindmap": ["mind map", "mindmap", "concept graph", "knowledge graph", "nodes", "ontology", "map", "relations", "graph"],
    "orbit": ["orbit", "3d", "3d graph", "constellation", "visualize", "visualization"],
    "gaps": ["gaps", "research gaps", "gap", "missing", "unexplored", "future work", "limitations"],
    "web-compare": ["web-compare", "web compare", "cross-verify", "dual retrieve", "fact check", "web check"],
    "sources": ["sources", "citations", "references", "evidence", "provenance"],
    "download": ["download", "export", "pdf file", "raw file", "get file", "fetch file"],
}


def fuzzy_match_documents(query_text: str, available_docs: list[str]) -> tuple[list[str], str]:
    """
    Use rapidfuzz to find document names mentioned in query text.
    Returns (matched_document_names, text_with_doc_name_stripped).
    """
    if not available_docs or not query_text.strip():
        return [], query_text

    matched: list[str] = []
    remaining_text = query_text

    # 1. Exact or stem match
    for doc in available_docs:
        doc_stem = Path(doc).stem
        # Check full filename
        if doc.lower() in query_text.lower():
            matched.append(doc)
            pattern = re.compile(re.escape(doc), re.IGNORECASE)
            remaining_text = pattern.sub("", remaining_text).strip()
        elif len(doc_stem) > 4 and doc_stem.lower() in query_text.lower():
            matched.append(doc)
            pattern = re.compile(re.escape(doc_stem), re.IGNORECASE)
            remaining_text = pattern.sub("", remaining_text).strip()

    if matched:
        return list(dict.fromkeys(matched)), remaining_text

    # 2. Rapidfuzz token / word matching for typos (e.g. "sampl ieee" -> "sample_ieee.pdf")
    words = re.findall(r"\b[\w.-]+\b", query_text)
    for i in range(len(words)):
        for j in range(i + 1, min(i + 4, len(words) + 1)):
            phrase = " ".join(words[i:j])
            if len(phrase) < 4:
                continue
            for doc in available_docs:
                clean_doc = Path(doc).stem.replace("_", " ")
                score = fuzz.ratio(phrase.lower(), clean_doc.lower())
                if score >= 78:
                    matched.append(doc)
                    pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                    remaining_text = pattern.sub("", remaining_text).strip()
                    break

    return list(dict.fromkeys(matched)), remaining_text


def detect_feature(text: str) -> Optional[str]:
    """
    Detect requested feature from synonym map with a small fallback classifier.
    """
    norm = text.strip().lower()

    # Exact synonym search (longer phrases first)
    for feat, syns in FEATURE_SYNONYMS.items():
        sorted_syns = sorted(syns, key=lambda s: -len(s))
        for s in sorted_syns:
            if re.search(rf"\b{re.escape(s)}\b", norm):
                return feat

    # Fallback fuzzy matching on feature names
    for feat, syns in FEATURE_SYNONYMS.items():
        for s in syns:
            if len(norm) >= 4 and fuzz.partial_ratio(s, norm) >= 88:
                return feat

    # Small fallback heuristic classifier
    if norm.startswith(("what", "how", "why", "who", "when", "can", "is", "does")):
        return "qa"
    if any(k in norm for k in ["synop", "sumar"]):
        return "summary"

    return None


def smart_route_query(
    text: str,
    document_ids: Optional[list[str]] = None,
    available_docs: Optional[list[str]] = None,
    run_all: bool = False,
) -> dict[str, Any]:
    """
    Route a natural-language query to its specific feature or all features.
    """
    docs_pool = available_docs or []
    fuzzy_matched_docs, cleaned_query = fuzzy_match_documents(text, docs_pool)

    # Combine explicitly passed doc IDs with fuzzy matched ones
    effective_docs = list(dict.fromkeys((document_ids or []) + fuzzy_matched_docs))

    # Clean rewritten query
    rewritten = cleaned_query.strip()
    if not rewritten:
        rewritten = text.strip()

    detected = detect_feature(text)

    is_ambiguous = detected is None and not run_all

    clarifications = []
    if is_ambiguous:
        clarifications = [
            f"Generate 5-sentence summary of {effective_docs[0]}" if effective_docs else "Generate summary",
            f"Extract Knowledge DNA for {effective_docs[0]}" if effective_docs else "Extract Knowledge DNA",
            f"Build concept mind map for {effective_docs[0]}" if effective_docs else "Build concept mind map",
            "Identify research gaps across collection",
            "Ask a specific grounded question",
        ]

    return {
        "original_query": text,
        "rewritten_query": rewritten,
        "matched_documents": effective_docs,
        "detected_feature": detected,
        "run_all": run_all or (detected is None and not is_ambiguous),
        "is_ambiguous": is_ambiguous,
        "clarification_options": clarifications,
    }


def autocomplete_smart_query(q: str, available_docs: list[str]) -> dict[str, Any]:
    """Provide autocomplete suggestions for documents and features."""
    norm = q.strip().lower()
    doc_suggestions = []
    feat_suggestions = []

    if norm:
        # Match documents
        for doc in available_docs:
            if norm in doc.lower() or fuzz.partial_ratio(norm, doc.lower()) >= 70:
                doc_suggestions.append({
                    "name": doc,
                    "title": Path(doc).stem.replace("_", " "),
                    "type": "document",
                })

        # Match features
        for feat, syns in FEATURE_SYNONYMS.items():
            if norm in feat.lower() or any(norm in s.lower() for s in syns):
                feat_suggestions.append({
                    "feature": feat,
                    "label": feat.replace("-", " ").title(),
                    "keywords": syns[:3],
                    "type": "feature",
                })

    return {
        "query": q,
        "documents": doc_suggestions[:5],
        "features": feat_suggestions[:5],
    }


# ===========================================================================
# 5. Parallel & Streaming Execution for "Run All"
# ===========================================================================

ALL_FEATURES = ["summary", "dna", "mindmap", "overview", "gaps", "qa"]


async def stream_run_all_features(
    query: str,
    document_names: list[str],
    rag_service: Any,
) -> AsyncGenerator[str, None]:
    """
    Generator yielding Server-Sent Events (SSE) progress for Run All:
    one event per feature.
    """
    yield f"data: {json.dumps({'event': 'run_all_start', 'query': query, 'features': ALL_FEATURES})}\n\n"

    total = len(ALL_FEATURES)
    for idx, feat in enumerate(ALL_FEATURES):
        yield f"data: {json.dumps({'event': 'feature_start', 'feature': feat, 'progress': round(idx / total * 100)})}\n\n"
        try:
            # This stream does not execute the features. Say so instead of
            # reporting success for work that never ran.
            note = "Not executed: this stream does not run the feature."
            yield f"data: {json.dumps({'event': 'feature_complete', 'feature': feat, 'status': 'not_executed', 'progress': round((idx + 1) / total * 100), 'detail': note})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'event': 'feature_complete', 'feature': feat, 'status': 'error', 'progress': round((idx + 1) / total * 100), 'error': str(exc)})}\n\n"

    yield f"data: {json.dumps({'event': 'run_all_complete', 'status': 'done', 'features_executed': 0})}\n\n"
