
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
    st.subheader("Document Ingestion")
    st.caption("Upload PDF, DOCX, or TXT documents to index into the RAG engine.")
    uploaded_file = st.file_uploader(
        "Upload research document",
        type=["pdf", "docx", "txt"],
        key="doc_file_uploader",
    )
    if uploaded_file is not None:
        if st.button("Upload & Index", use_container_width=True):
            with st.spinner("Extracting, chunking, and indexing document..."):
                try:
                    files = {
                        "file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            uploaded_file.type or "application/octet-stream",
                        )
                    }
                    res = requests.post(f"{API_BASE_URL}/documents/upload", files=files, timeout=120)
                    res.raise_for_status()
                    data = res.json()
                    st.success(f"Indexed: {data.get('document')}")
                    st.caption(
                        f"Pages: {data.get('total_pages', 1)} · "
                        f"Chunks: {data.get('document_chunks', 0)} · "
                        f"IQ Score: {data.get('document_iq', {}).get('iq_score', 'N/A')}"
                    )
                except requests.RequestException as exc:
                    err_msg = str(exc)
                    if hasattr(exc, "response") and exc.response is not None:
                        try:
                            err_msg = exc.response.json().get("detail", err_msg)
                        except Exception:
                            pass
                    st.error(f"Upload failed: {err_msg}")

    with st.expander("Indexed Documents"):
        try:
            doc_res = requests.get(f"{API_BASE_URL}/documents", timeout=5)
            if doc_res.status_code == 200:
                docs = doc_res.json().get("documents", [])
                if docs:
                    for d in docs:
                        st.markdown(f"**{d.get('title', d.get('document', 'Unknown'))}**")
                        st.caption(f"Pages: {d.get('pages', 0)} | Chunks: {d.get('chunks', 0)}")
                else:
                    st.write("No documents indexed yet.")
            else:
                st.write("Unable to fetch document list.")
        except Exception:
            st.write("Backend offline.")

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

            if response.status_code == 429:
                st.error("LLM Provider Quota / Rate Limit Exceeded")
                st.info("The AI provider rate limit was reached. Please wait a moment before trying again.")
            elif response.status_code == 503:
                st.error("LLM Providers Temporarily Unavailable")
                st.info("Upstream LLM services are temporarily offline or unreachable.")
            elif response.status_code == 502:
                if (
                    feature == "Research Gaps"
                    and "invalid research gap JSON" in str(detail).lower()
                ):
                    st.warning(
                        "A complete research-gap result could not be generated. "
                        "The provider response was incomplete or invalid. Please try again later."
                    )
                else:
                    st.error("Upstream Generation Failure (HTTP 502)")
                    st.warning(f"{detail or 'The LLM provider failed to process the request.'}")
            elif response.status_code == 400:
                st.error(f"Invalid Request: {detail or 'The request parameters were rejected.'}")
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


def _render_sources_section(sources: list):
    st.markdown("### Retrieved Source Evidence")
    if isinstance(sources, list) and sources:
        for index, source in enumerate(sources, start=1):
            if not isinstance(source, dict):
                with st.expander(f"Source {index}"):
                    st.write(source)
                continue
            doc = source.get("document", "Unknown document")
            page = source.get("page", "Unknown")
            chunk_id = source.get("chunk_id", "N/A")
            with st.container(border=True):
                st.markdown(f"**{index}. {doc}**")
                st.caption(f"Page `{page}` · Chunk ID: `{chunk_id}`")
    else:
        st.info("No source citations returned for this result.")


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

    elif last_feature == "Knowledge Mind Map" and isinstance(result, dict):
        query = result.get("query", "")
        area = result.get("research_area", "")
        nodes = result.get("nodes", [])
        edges = result.get("edges", [])
        sources = result.get("sources", [])

        st.markdown(f"**Research Area:** {area}")

        if not nodes:
            st.info(
                "No concepts or relationships could be identified from the retrieved "
                "evidence for this query. The graph is currently empty."
            )
        else:
            color_map = {
                "TOPIC": "#dbeafe",
                "CONCEPT": "#dcfce7",
                "METHOD": "#fef3c7",
                "FINDING": "#f3e8ff",
                "LIMITATION": "#fee2e2",
                "DOCUMENT": "#f1f5f9",
            }
            lines = [
                "digraph MindMap {",
                "  rankdir=LR;",
                '  node [shape=box, style="rounded,filled", fontname="sans-serif", margin="0.2,0.1"];',
                '  edge [fontname="sans-serif", fontsize=10];',
            ]
            for node in nodes:
                nid = str(node.get("id", "")).replace('"', '')
                lbl = str(node.get("label", nid)).replace('"', '\\"')
                ntype = str(node.get("type", "CONCEPT")).upper()
                bg = color_map.get(ntype, "#e2e8f0")
                lines.append(f'  "{nid}" [label="{lbl}\\n[{ntype}]", fillcolor="{bg}"];')
            for edge in edges:
                src = str(edge.get("source", "")).replace('"', '')
                tgt = str(edge.get("target", "")).replace('"', '')
                rel = str(edge.get("relationship", "")).replace('"', '\\"')
                lines.append(f'  "{src}" -> "{tgt}" [label="{rel}"];')
            lines.append("}")

            st.markdown("### Interactive Mind Map Graph")
            st.graphviz_chart("\n".join(lines), use_container_width=True)

            st.markdown("### Graph Nodes")
            for node in nodes:
                with st.expander(f"{node.get('label', node.get('id'))} [{node.get('type')}]"):
                    st.write(node.get("description", "No description available."))
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Confidence", f"{float(node.get('confidence', 0)):.2f}")
                    c2.write(f"**Document:** {node.get('document', 'N/A')}")
                    c3.write(f"**Page / Chunk:** {node.get('page', 'N/A')} / `{node.get('chunk_id', 'N/A')}`")
                    ev = node.get("evidence", [])
                    if ev:
                        st.caption("**Evidence:** " + "; ".join(ev if isinstance(ev, list) else [str(ev)]))

            if edges:
                st.markdown("### Relationships")
                edge_table = [
                    {
                        "Source": e.get("source"),
                        "Relationship": e.get("relationship"),
                        "Target": e.get("target"),
                        "Confidence": f"{float(e.get('confidence', 0)):.2f}",
                        "Evidence": e.get("evidence", ""),
                    }
                    for e in edges
                ]
                st.table(edge_table)

        _render_sources_section(sources)

    elif last_feature == "Knowledge DNA" and isinstance(result, dict):
        query = result.get("query", "")
        area = result.get("research_area", "")
        core_topics = result.get("core_topics", [])
        key_concepts = result.get("key_concepts", [])
        methods = result.get("methods", [])
        findings = result.get("findings", [])
        limitations = result.get("limitations", [])
        themes = result.get("themes", [])
        signals = result.get("signals", [])
        relationships = result.get("relationships", [])
        sources = result.get("sources", [])

        st.markdown(f"**Research Area:** {area}")

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Core Topics", len(core_topics))
        m2.metric("Key Concepts", len(key_concepts))
        m3.metric("Methods", len(methods))
        m4.metric("Findings", len(findings))
        m5.metric("Limitations", len(limitations))
        m6.metric("Themes", len(themes))

        if signals:
            color_map = {
                "TOPIC": "#dbeafe",
                "CONCEPT": "#dcfce7",
                "METHOD": "#fef3c7",
                "FINDING": "#f3e8ff",
                "LIMITATION": "#fee2e2",
            }
            lines = [
                "digraph DNA {",
                "  rankdir=LR;",
                '  node [shape=box, style="rounded,filled", fontname="sans-serif", margin="0.2,0.1"];',
                '  edge [fontname="sans-serif", fontsize=10];',
            ]
            for s in signals:
                sname = str(s.get("name", "")).replace('"', '\\"')
                stype = str(s.get("type", "CONCEPT")).upper()
                bg = color_map.get(stype, "#e2e8f0")
                lines.append(f'  "{sname}" [label="{sname}\\n[{stype}]", fillcolor="{bg}"];')
            for r in relationships:
                src = str(r.get("source", "")).replace('"', '\\"')
                tgt = str(r.get("target", "")).replace('"', '\\"')
                rel = str(r.get("relationship", "")).replace('"', '\\"')
                lines.append(f'  "{src}" -> "{tgt}" [label="{rel}"];')
            lines.append("}")

            st.markdown("### DNA Structural Visualization")
            st.graphviz_chart("\n".join(lines), use_container_width=True)

        tab1, tab2, tab3 = st.tabs(["Key Concepts & Topics", "Methods & Findings", "Limitations & Themes"])
        with tab1:
            if core_topics:
                st.markdown("**Core Topics:** " + ", ".join(f"`{t}`" for t in core_topics))
            if key_concepts:
                st.markdown("**Key Concepts:** " + ", ".join(f"`{c}`" for c in key_concepts))
        with tab2:
            if methods:
                st.markdown("**Methods:** " + ", ".join(f"`{m}`" for m in methods))
            if findings:
                st.markdown("**Findings:**")
                for f in findings:
                    st.markdown(f"- {f}")
        with tab3:
            if limitations:
                st.markdown("**Reported Limitations:**")
                for lim in limitations:
                    st.markdown(f"- ⚠️ {lim}")
            if themes:
                st.markdown("**Themes:** " + ", ".join(f"`{t}`" for t in themes))

        _render_sources_section(sources)

    elif last_feature == "Research Gaps" and isinstance(result, dict):
        query = result.get("query", "")
        area = result.get("research_area", "")
        existing_findings = result.get("existing_findings", [])
        reported_limitations = result.get("reported_limitations", [])
        gaps = result.get("gaps", [])
        sources = result.get("sources", [])

        st.markdown(f"**Research Area:** {area}")

        if existing_findings:
            st.markdown("### Existing Findings in Literature")
            for finding in existing_findings:
                st.markdown(f"✅ {finding}")

        if reported_limitations:
            st.markdown("### Reported Limitations")
            for lim in reported_limitations:
                st.markdown(f"⚠️ {lim}")

        st.markdown("### Identified Research Gaps")
        if not gaps:
            st.info("No research gaps were explicitly reported or inferred from the retrieved evidence.")
        else:
            for idx, g in enumerate(gaps, start=1):
                gap_text = g.get("gap", "")
                gap_type = g.get("type", "EXPLICIT")
                conf = float(g.get("confidence", 0.0))
                rationale = g.get("rationale", "")
                doc = g.get("document", "")
                page = g.get("page", "")

                with st.container(border=True):
                    st.markdown(f"**{idx}. {gap_text}**")
                    col1, col2 = st.columns([1, 3])
                    col1.metric("Confidence", f"{conf:.2f}")
                    col1.caption(f"Type: `{gap_type}`")
                    col2.write(f"**Rationale:** {rationale}")
                    if doc:
                        col2.caption(f"Supported by `{doc}` (Page {page})")

        _render_sources_section(sources)

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

    with st.expander("Raw JSON Response"):
        st.json(result)

    st.download_button(
        "Download result as JSON",
        data=json.dumps(result, indent=2, ensure_ascii=False),
        file_name="unknown_result.json",
        mime="application/json",
    )

st.divider()
st.caption("UNKNOWN Research Intelligence | Temporary frontend")
