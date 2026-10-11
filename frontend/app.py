
import json
import os

import requests
import streamlit as st

from request_payload import (
    EXAMPLE_QUERIES,
    FEATURE_DEBATE,
    build_request_payload,
    input_label,
    input_placeholder,
    request_is_ready,
)

API_BASE_URL = os.getenv("UNKNOWN_API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="UNKNOWN | Research Intelligence",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1250px;
    }
    .hero {
        padding: 1.5rem;
        border: 1px solid rgba(128,128,128,.3);
        border-radius: 16px;
        margin-bottom: 1.5rem;
    }
    .hero h1 { margin-bottom: .4rem; }
    .muted { opacity: .75; }
    .source-card {
        padding: 1rem;
        border: 1px solid rgba(128,128,128,.3);
        border-radius: 12px;
        margin-bottom: .7rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("UNKNOWN")
st.caption(
    "Adaptive Hybrid Semantic Retrieval Engine for "
    "Intelligent Information Discovery"
)

# Sidebar: backend health
with st.sidebar:
    st.header("Research workspace")
    st.write("Explore your indexed research papers.")

    if st.button("Check backend connection", use_container_width=True):
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=10)
            response.raise_for_status()
            st.session_state["backend_health"] = response.json()
            st.session_state.pop("backend_error", None)
        except requests.RequestException as exc:
            st.session_state["backend_error"] = str(exc)
            st.session_state.pop("backend_health", None)

    if st.session_state.get("backend_health"):
        st.success("Backend is reachable")
        st.json(st.session_state["backend_health"])

    if st.session_state.get("backend_error"):
        st.error("Backend connection failed")
        st.caption(st.session_state["backend_error"])

    st.divider()
    st.caption(f"API: {API_BASE_URL}")

st.markdown(
    """
    <div class="hero">
        <h1>Research beyond search.</h1>
        <p class="muted">
        Ask questions about research papers and explore evidence,
        knowledge structures, and visual explanations.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

endpoint_map = {
    "Research Assistant": "/query",
    "Verify Claim": "/verify",
    "Discover Concept": "/discover-concept",
    "Contradictions": "/contradictions",
    "Compare Research": "/compare",
    "Research Gaps": "/gaps",
    "Research Debate": "/debate",
    "Knowledge DNA": "/knowledge-dna",
    "Knowledge Mind Map": "/knowledge-mind-map",
    "Adaptive Answer": "/adaptive-answer",
    "Visual Answer": "/visual-answer",
}

descriptions = {
    "Research Assistant": "Ask questions and retrieve evidence from your research papers.",
    "Verify Claim": "Check a claim against retrieved research evidence.",
    "Discover Concept": "Explore concepts found in your research collection.",
    "Contradictions": "Investigate conflicting findings across research sources.",
    "Compare Research": "Compare research topics, methods, or findings.",
    "Research Gaps": "Explore potential gaps in the research literature.",
    "Research Debate": "Examine differing research arguments and evidence.",
    "Knowledge DNA": "Extract key concepts, methods, findings, and research themes.",
    "Knowledge Mind Map": "Explore relationships between research concepts.",
    "Adaptive Answer": "Generate an answer adapted to your question.",
    "Visual Answer": "Generate structured visual explanations from evidence.",
}

feature = st.selectbox("Choose a research tool", list(endpoint_map.keys()))
st.subheader(feature)
st.write(descriptions[feature])

query_key = f"query_{feature}"
position_a_key = f"position_a_{feature}"
position_b_key = f"position_b_{feature}"

examples = EXAMPLE_QUERIES.get(feature, [])
if examples:
    st.caption("Example queries — click to fill the form. This does not run the tool.")
    columns = st.columns(len(examples))
    for column, example in zip(columns, examples):
        with column:
            if st.button(
                example["label"],
                key=f"example_{feature}_{example['label']}",
                use_container_width=True,
            ):
                st.session_state[query_key] = example["query"]
                if feature == FEATURE_DEBATE:
                    st.session_state[position_a_key] = example.get("position_a", "")
                    st.session_state[position_b_key] = example.get("position_b", "")

query = st.text_area(
    input_label(feature),
    placeholder=input_placeholder(feature),
    key=query_key,
)

position_a = ""
position_b = ""
if feature == FEATURE_DEBATE:
    position_a = st.text_input(
        "Position A",
        placeholder="First debate position...",
        key=position_a_key,
    )
    position_b = st.text_input(
        "Position B",
        placeholder="Second debate position...",
        key=position_b_key,
    )

if st.button(
    f"Run {feature}",
    type="primary",
    disabled=not request_is_ready(feature, query, position_a, position_b),
    use_container_width=True,
):
    try:
        with st.spinner(f"Running {feature}..."):
            response = requests.post(
                f"{API_BASE_URL}{endpoint_map[feature]}",
                json=build_request_payload(
                    feature,
                    query,
                    position_a,
                    position_b,
                ),
                timeout=180,
            )

        if not response.ok:
            try:
                error_data = response.json()
            except ValueError:
                error_data = {}

            detail = (
                error_data.get("detail", "")
                if isinstance(error_data, dict)
                else ""
            )

            if (
                feature == "Research Gaps"
                and response.status_code == 502
                and "invalid research gap JSON" in str(detail).lower()
            ):
                st.warning(
                    "A complete research-gap result could not be generated. "
                    "The provider response was incomplete or invalid. "
                    "Please try again later."
                )
            else:
                st.error(f"Backend returned HTTP {response.status_code}")
                if detail:
                    st.write(str(detail))
                else:
                    st.code(response.text[:1000])

        else:
            try:
                result = response.json()
            except ValueError:
                st.error("The backend returned an invalid JSON response.")
            else:
                st.session_state["last_result"] = result
                st.session_state["last_feature"] = feature
                st.session_state["last_query"] = query.strip()

    except requests.RequestException as exc:
        st.error(f"Could not reach the backend: {exc}")

# Results renderer
result = st.session_state.get("last_result")
last_feature = st.session_state.get("last_feature", "")

if result is not None:
    st.divider()
    st.subheader(f"Results: {last_feature}")

    if last_feature == "Research Assistant" and isinstance(result, dict):
        answer = result.get("answer")
        query_type = result.get("query_type")
        sources = result.get("sources", [])

        if answer is not None:
            st.markdown("### Answer")
            if isinstance(answer, (dict, list)):
                st.json(answer)
            else:
                st.markdown(str(answer))

        if query_type is not None:
            st.markdown("### Query type")
            st.info(str(query_type).replace("_", " ").title())

        st.markdown("### Sources")

        if isinstance(sources, list) and sources:
            for index, source in enumerate(sources, start=1):
                if not isinstance(source, dict):
                    with st.expander(f"Source {index}"):
                        st.write(source)
                    continue

                rank = source.get("rank", index)
                document = source.get("document", "Unknown document")
                page = source.get("page", "Unknown")
                chunk_id = source.get("chunk_id", "Unavailable")

                with st.container(border=True):
                    st.markdown(f"**{rank}. {document}**")
                    st.caption(f"Page {page} · Chunk `{chunk_id}`")

                    score_columns = st.columns(3)
                    for column, key, label in zip(
                        score_columns,
                        ("hybrid_score", "bm25_score", "faiss_score"),
                        ("Hybrid score", "BM25 score", "FAISS score"),
                    ):
                        value = source.get(key)
                        with column:
                            if isinstance(value, (int, float)):
                                st.metric(label, f"{value:.4f}")
                            elif value is not None:
                                st.metric(label, str(value))
        else:
            st.info("No source metadata was returned for this response.")

        other_fields = {
            key: value
            for key, value in result.items()
            if key not in {"answer", "query_type", "sources"}
        }
        if other_fields:
            with st.expander("Additional response details"):
                st.json(other_fields)

    else:
        # Generic display for other research tools.
        if isinstance(result, dict):
            for key, value in result.items():
                with st.expander(
                    key.replace("_", " ").title(),
                    expanded=key in {
                        "answer",
                        "summary",
                        "visual_type",
                        "title",
                        "nodes",
                        "elements",
                    },
                ):
                    if isinstance(value, (dict, list)):
                        st.json(value)
                    else:
                        st.write(value)
        else:
            st.json(result)

    st.download_button(
        "Download result as JSON",
        data=json.dumps(result, indent=2, ensure_ascii=False),
        file_name="unknown_result.json",
        mime="application/json",
    )

st.divider()
st.caption("UNKNOWN Research Intelligence | Temporary frontend")
