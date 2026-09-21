"""
UNKNOWN X v2.0 - Evidence Trail Engine

Purpose:
- Convert HybridSearch retrieval results into standardized evidence objects.
- Preserve retrieval metadata for explainability.
- Generate citations for Gemini, FastAPI and Streamlit UI.

Canonical Retrieval Result Schema (HybridSearch.search):

{
    "rank": int,
    "score": float,                # Raw retrieval score
    "normalized_score": float,     # Normalized retrieval score
    "hybrid_score": float,         # Final hybrid relevance score
    "bm25_score": float,
    "faiss_score": float,
    "chunk_id": str,
    "document": str,
    "page": int,
    "text": str
}
"""

from typing import Dict, List


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------

def safe_score(value) -> float:
    """
    Safely convert any score into a rounded float.
    Returns 0.0 for None, empty values, or invalid numbers.
    """
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0.0


# ------------------------------------------------------------------
# Evidence Builder
# ------------------------------------------------------------------

def build_evidence(results: List[Dict]) -> List[Dict]:
    """
    Convert HybridSearch results into standardized evidence objects.

    Args:
        results: List returned from HybridSearch.search()

    Returns:
        List of evidence dictionaries used across UNKNOWN X.
    """

    evidence = []

    for index, result in enumerate(results, start=1):
        evidence.append({
            # Retrieval metadata
            "rank": int(result.get("rank", index)),
            "document": str(result.get("document", "Unknown Document")),
            "page": int(result.get("page", 0)),
            "chunk_id": str(result.get("chunk_id", "unknown")),

            # Scores
            "raw_score": safe_score(result.get("score")),
            "normalized_score": safe_score(result.get("normalized_score")),
            "score": safe_score(result.get("hybrid_score")),
            "hybrid_score": safe_score(result.get("hybrid_score")),
            "bm25_score": safe_score(result.get("bm25_score")),
            "faiss_score": safe_score(result.get("faiss_score")),

            # Supporting text
            "snippet": str(result.get("text", "")).strip()[:350]
        })

    return evidence


# ------------------------------------------------------------------
# Citation Formatter
# ------------------------------------------------------------------

def format_citations(evidence: List[Dict]) -> List[str]:
    """
    Create human-readable citations for API/Streamlit UI.
    """

    return [
        (
            f"[Rank {item['rank']}] "
            f"{item['document']} "
            f"(Page {item['page']}) "
            f"| Hybrid Score: {item['score']}"
        )
        for item in evidence
    ]


# ------------------------------------------------------------------
# Markdown Evidence Trail
# ------------------------------------------------------------------

def evidence_markdown(evidence: List[Dict]) -> str:
    """
    Markdown evidence section for Gemini prompts.
    """

    if not evidence:
        return "## Evidence Trail\nNo supporting evidence found."

    lines = ["## Evidence Trail"]

    for item in evidence:
        lines.append(
            f"- **Rank {item['rank']}** | "
            f"**{item['document']}** | "
            f"Page {item['page']} | "
            f"Hybrid Score: **{item['score']}**"
        )

    return "\n".join(lines)


# ------------------------------------------------------------------
# Utility (Future UI / API)
# ------------------------------------------------------------------

def get_top_evidence(evidence: List[Dict], top_n: int = 3) -> List[Dict]:
    """
    Return the highest-ranked evidence objects.
    """

    return sorted(
        evidence,
        key=lambda x: x["score"],
        reverse=True
    )[:top_n]