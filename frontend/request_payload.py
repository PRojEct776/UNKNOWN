"""Map Streamlit tool inputs to FastAPI request bodies."""

from __future__ import annotations

FEATURE_VERIFY = "Verify Claim"
FEATURE_DISCOVER = "Discover Concept"
FEATURE_DEBATE = "Research Debate"

# Short labels shown on example chips. Click fills the form; it does not run.
EXAMPLE_QUERIES: dict[str, list[dict[str, str]]] = {
    "Research Assistant": [
        {
            "label": "What is SAC-RAG?",
            "query": "What is SAC-RAG?",
        },
        {
            "label": "How does compression work?",
            "query": "How does SAC-RAG compress retrieved context?",
        },
    ],
    FEATURE_VERIFY: [
        {
            "label": "Token-savings claim",
            "query": (
                "SAC-RAG reduces token consumption by 38%–58% "
                "with only a 1–2 percentage point EM drop."
            ),
        },
    ],
    FEATURE_DISCOVER: [
        {
            "label": "Adaptive RAG idea",
            "query": (
                "A RAG method that classifies questions as factual, "
                "definitional, or reasoning and then compresses retrieved context."
            ),
        },
    ],
    "Contradictions": [
        {
            "label": "Compression quality",
            "query": "Does context compression improve or hurt answer quality?",
        },
    ],
    "Compare Research": [
        {
            "label": "Adaptive vs SAC-RAG",
            "query": "How do Adaptive RAG and SAC-RAG compare on HotpotQA?",
        },
    ],
    "Research Gaps": [
        {
            "label": "SAC-RAG limitations",
            "query": "What limitations and open problems remain in SAC-RAG?",
        },
    ],
    FEATURE_DEBATE: [
        {
            "label": "Always compress?",
            "query": (
                "Should RAG systems always compress retrieved context "
                "before generation?"
            ),
            "position_a": "Yes — compression removes noise and saves tokens.",
            "position_b": "No — compression can drop sparse multi-hop evidence.",
        },
    ],
    "Knowledge DNA": [
        {
            "label": "SAC-RAG DNA",
            "query": "Map the core methods and findings of SAC-RAG.",
        },
    ],
    "Knowledge Mind Map": [
        {
            "label": "Retrieval relationships",
            "query": (
                "Map relationships among adaptive retrieval, context compression, "
                "and question types in SAC-RAG."
            ),
        },
    ],
    "Adaptive Answer": [
        {
            "label": "Why type-specific retrieval?",
            "query": (
                "Why does SAC-RAG use different retrieval strategies for fact, "
                "definition, and reasoning questions?"
            ),
        },
    ],
    "Visual Answer": [
        {
            "label": "Pipeline stages",
            "query": (
                "Show the SAC-RAG pipeline stages from classification "
                "to answer generation."
            ),
        },
    ],
}


def input_label(feature: str) -> str:
    if feature == FEATURE_VERIFY:
        return "Claim"
    if feature == FEATURE_DISCOVER:
        return "Concept description"
    if feature == FEATURE_DEBATE:
        return "Debate question"
    return "Research question or input"


def input_placeholder(feature: str) -> str:
    if feature == FEATURE_VERIFY:
        return "Enter the claim to verify..."
    if feature == FEATURE_DISCOVER:
        return "Describe the concept you want to identify..."
    if feature == FEATURE_DEBATE:
        return "Enter the debate question..."
    return "Enter your question here..."


def build_request_payload(
    feature: str,
    text: str,
    position_a: str = "",
    position_b: str = "",
) -> dict[str, str]:
    stripped = text.strip()
    if feature == FEATURE_VERIFY:
        return {"claim": stripped}
    if feature == FEATURE_DISCOVER:
        return {"description": stripped}
    if feature == FEATURE_DEBATE:
        return {
            "query": stripped,
            "position_a": position_a.strip(),
            "position_b": position_b.strip(),
        }
    return {"query": stripped}


def request_is_ready(
    feature: str,
    text: str,
    position_a: str = "",
    position_b: str = "",
) -> bool:
    if not text.strip():
        return False
    if feature == FEATURE_DEBATE:
        return bool(position_a.strip() and position_b.strip())
    return True
