"""
UNKNOWN - Research Intelligence Platform
Adaptive Hybrid Retrieval-Augmented Generation & Academic Discovery
"""

from __future__ import annotations

import datetime
import html
import json
import os
import re

import requests
import streamlit as st
import streamlit.components.v1 as components

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
        padding-top: 1.8rem;
        padding-bottom: 3rem;
        max-width: 1250px;
    }
    .hero {
        padding: 1.5rem;
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 14px;
        margin-bottom: 1.5rem;
        background: rgba(255,255,255,0.02);
    }
    .hero h1 { margin-bottom: .3rem; font-size: 2.1rem; }
    .muted { opacity: .75; font-size: 0.95rem; }
    .source-card {
        padding: 0.85rem;
        border: 1px solid rgba(128,128,128,.2);
        border-radius: 10px;
        margin-bottom: 0.5rem;
    }
    .badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-size: 0.82rem;
        font-weight: 600;
        margin-right: 0.4rem;
        margin-bottom: 0.3rem;
    }
    .badge-subq { background: #e0e7ff; color: #3730a3; }
    .assistant-card {
        padding: 1rem;
        border: 1px solid #6366f1;
        border-radius: 12px;
        background: rgba(99, 102, 241, 0.05);
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize session history
if "session_history" not in st.session_state:
    st.session_state["session_history"] = []

if "user_id" not in st.session_state:
    st.session_state["user_id"] = "default_user"

# ============================================================
# SIDEBAR: WORKSPACE, INGESTION & REPORT
# ============================================================

with st.sidebar:
    st.header("Research Workspace")
    workspace_user_id = st.text_input(
        "Active Workspace / User ID",
        value=st.session_state.get("user_id", "default_user"),
        key="active_workspace_input",
        help="Enforces document isolation. Documents uploaded here belong strictly to this workspace.",
    )
    st.session_state["user_id"] = workspace_user_id.strip() or "default_user"
    active_user = st.session_state["user_id"]

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
        st.success("Backend is online")
    elif st.session_state.get("backend_error"):
        st.error(f"Backend offline: {st.session_state['backend_error']}")

    st.divider()

    # Document Ingestion Widget
    st.subheader("Document Ingestion")
    st.caption(f"Workspace: `{active_user}`")
    uploaded_file = st.file_uploader(
        "Upload research paper",
        type=["pdf", "docx", "txt"],
        key="doc_file_uploader",
        help="Upload PDF, DOCX, or TXT (up to 50MB). Duplicate content is safely rejected.",
    )

    if uploaded_file is not None:
        if st.button("Upload & Index Document", use_container_width=True):
            with st.spinner("Extracting text, chunking, and updating indexes..."):
                try:
                    files = {
                        "file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            uploaded_file.type or "application/octet-stream",
                        )
                    }
                    data_payload = {"user_id": active_user}
                    res = requests.post(
                        f"{API_BASE_URL}/documents/upload",
                        files=files,
                        data=data_payload,
                        timeout=120,
                    )
                    res.raise_for_status()
                    data = res.json()
                    st.success(f"Indexed: {data.get('document')}")
                    st.caption(
                        f"Pages: {data.get('total_pages', 1)} | "
                        f"Chunks: {data.get('document_chunks', 0)} | "
                        f"IQ Score: {data.get('document_iq', {}).get('iq_score', 'N/A')}"
                    )
                    st.session_state["last_uploaded_doc"] = data.get("document")
                except requests.RequestException as exc:
                    err_msg = str(exc)
                    if hasattr(exc, "response") and exc.response is not None:
                        try:
                            err_msg = exc.response.json().get("detail", err_msg)
                        except Exception:
                            pass
                    st.error(f"Upload failed: {err_msg}")

    # Document Library listing (Scoped to user_id)
    workspace_docs: list[dict] = []
    try:
        doc_res = requests.get(
            f"{API_BASE_URL}/documents",
            params={"user_id": active_user},
            timeout=5,
        )
        if doc_res.status_code == 200:
            workspace_docs = doc_res.json().get("documents", [])
    except Exception:
        workspace_docs = []

    with st.expander(f"Document Library ({len(workspace_docs)})", expanded=True):
        if workspace_docs:
            for d in workspace_docs:
                title = d.get("title", d.get("document", "Document"))
                doc_file = d.get("document", "")
                pages = d.get("pages", 0)
                chunks = d.get("chunks", 0)
                iq = d.get("document_iq", {}).get("iq_score", "N/A")
                st.markdown(f"**{title}**")
                st.caption(f"`{doc_file}` · {pages} pages · {chunks} chunks · IQ: {iq}")
        else:
            st.info("No documents in this workspace yet. Upload papers above to begin.")

    st.divider()

    # Session Report Generator
    st.subheader("Research Session")
    history_count = len(st.session_state.get("session_history", []))
    st.caption(f"Queries recorded: **{history_count}**")

    if history_count > 0:
        if st.button("Clear Session History", use_container_width=True):
            st.session_state["session_history"] = []
            st.rerun()

    st.divider()
    st.caption(f"API Base: `{API_BASE_URL}`")

# ============================================================
# MAIN INTERFACE: HERO & QUERY ASSISTANT
# ============================================================

st.title("UNKNOWN Research Intelligence")
st.caption("Adaptive Hybrid Retrieval-Augmented Generation & Academic Discovery Engine")

if not workspace_docs:
    st.warning(
        f"Workspace `{active_user}` has no documents indexed yet. "
        "Please upload your research documents (PDF, DOCX, or TXT) in the sidebar to start searching."
    )

endpoint_map = {
    "Research Assistant": "/query",
    "Multi-Step Reasoning": "/reason",
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
    "Research Assistant": "Ask natural-language questions and retrieve grounded answers and citations.",
    "Multi-Step Reasoning": "Execute Srinidhi's multi-step causal reasoning pipeline with subquestion decomposition and grounded synthesis.",
    "Verify Claim": "Validate a specific factual hypothesis or claim against peer-reviewed citations.",
    "Discover Concept": "Reverse-engineer an unknown technical concept or terminology from an informal description.",
    "Contradictions": "Detect divergent findings, disputes, or conflicting empirical evidence across papers.",
    "Compare Research": "Compare up to 10 selected documents or research entities across structured aspects.",
    "Research Gaps": "Isolate explicit limitations and unaddressed research opportunities in literature.",
    "Research Debate": "Examine two distinct intellectual positions backed by opposing evidence trails.",
    "Knowledge DNA": "Extract core topics, key concepts, methods, findings, limitations, and thematic structures.",
    "Knowledge Mind Map": "Explore interactive conceptual graphs and relational topology across research.",
    "Adaptive Answer": "Generate answers adapted to beginner, intermediate, or expert depth levels.",
    "Visual Answer": "Generate structured visual explanations, stage flows, and evidence-grounded diagrams.",
}

# ============================================================
# QUERY ASSISTANT CHATBOT HELPER
# ============================================================

with st.expander("✨ AI Query Assistant (Need help formulating your research question?)", expanded=False):
    st.markdown(
        "Unsure how to frame your question? Enter your draft idea below and let the Query Assistant "
        "refine it with academic terminology and suggest the optimal UNKNOWN research tool."
    )
    col_qi, col_btn = st.columns([4, 1])
    with col_qi:
        assistant_input = st.text_input(
            "Draft question or topic",
            placeholder="e.g., how fast is DNA storage compared to flash or tape?",
            key="query_assistant_draft",
            label_visibility="collapsed",
        )
    with col_btn:
        run_assistant = st.button("Enhance Query", use_container_width=True)

    if run_assistant and assistant_input.strip():
        with st.spinner("Analyzing research intent and formulating suggestions..."):
            try:
                qa_res = requests.post(
                    f"{API_BASE_URL}/query-assistant",
                    json={"query": assistant_input.strip()},
                    timeout=20,
                )
                if qa_res.status_code == 200:
                    qa_data = qa_res.json()
                    st.session_state["assistant_suggestion"] = qa_data
                else:
                    st.error("Query Assistant could not process this prompt.")
            except Exception as exc:
                st.error(f"Failed to reach Query Assistant: {exc}")

    if st.session_state.get("assistant_suggestion"):
        sugg = st.session_state["assistant_suggestion"]
        st.markdown(
            f"""
            <div class="assistant-card">
                <h4>Refined Query Recommendation</h4>
                <p><strong>Refined Query:</strong> <code>{html.escape(sugg.get('refined_query', ''))}</code></p>
                <p><strong>Recommended Tool:</strong> <strong>{html.escape(sugg.get('suggested_task', ''))}</strong></p>
                <p><em>{html.escape(sugg.get('explanation', ''))}</em></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        alts = sugg.get("alternative_queries", [])
        if alts:
            st.caption("Alternative phrasings:")
            for alt in alts:
                st.markdown(f"- `{alt}`")

        tips = sugg.get("tips", [])
        if tips:
            st.caption("Search tips: " + " · ".join(tips))

        col_apply1, col_apply2 = st.columns(2)
        with col_apply1:
            if st.button("Apply Refined Query & Switch Tool", key="apply_refined_query_btn"):
                target_tool = sugg.get("suggested_task", "Research Assistant")
                if target_tool not in endpoint_map:
                    target_tool = "Research Assistant"
                st.session_state["selected_tool"] = target_tool
                st.session_state[f"query_{target_tool}"] = sugg.get("refined_query", "")
                st.success(f"Applied! Switched to '{target_tool}'.")
                st.rerun()

# ============================================================
# TOOL SELECTION & QUERY FORM
# ============================================================

current_selection = st.session_state.get("selected_tool", "Research Assistant")
tool_index = list(endpoint_map.keys()).index(current_selection) if current_selection in endpoint_map else 0

feature = st.selectbox(
    "Choose a research tool",
    list(endpoint_map.keys()),
    index=tool_index,
    key="active_feature_selector",
)
st.session_state["selected_tool"] = feature

st.subheader(feature)
st.write(descriptions.get(feature, ""))

query_key = f"query_{feature}"
position_a_key = f"position_a_{feature}"
position_b_key = f"position_b_{feature}"

# Example query chips
examples = EXAMPLE_QUERIES.get(feature, [])
if examples:
    st.caption("Example queries (click to load):")
    cols = st.columns(min(len(examples), 4))
    for col, example in zip(cols, examples):
        with col:
            if st.button(example["label"], key=f"ex_{feature}_{example['label']}", use_container_width=True):
                st.session_state[query_key] = example["query"]
                if feature == FEATURE_DEBATE:
                    st.session_state[position_a_key] = example.get("position_a", "")
                    st.session_state[position_b_key] = example.get("position_b", "")

# Comparison Document Selector (Up to 10 documents)
selected_comparison_docs: list[str] = []
if feature == "Compare Research":
    available_doc_names = [d.get("document") for d in workspace_docs if d.get("document")]
    if available_doc_names:
        selected_comparison_docs = st.multiselect(
            "Select specific documents to compare (up to 10 documents)",
            options=available_doc_names,
            max_selections=10,
            help="Limit the comparison scope strictly to these documents. Leave empty to compare across all documents in your workspace.",
        )
        if selected_comparison_docs:
            st.caption(f"Comparing across {len(selected_comparison_docs)} selected documents.")
    else:
        st.info("No documents uploaded yet in this workspace. Comparison will run when documents are uploaded.")

query = st.text_area(
    input_label(feature),
    placeholder=input_placeholder(feature),
    key=query_key,
)

position_a = ""
position_b = ""
if feature == FEATURE_DEBATE:
    col_pa, col_pb = st.columns(2)
    with col_pa:
        position_a = st.text_input(
            "Position A",
            placeholder="First debate position...",
            key=position_a_key,
        )
    with col_pb:
        position_b = st.text_input(
            "Position B",
            placeholder="Second debate position...",
            key=position_b_key,
        )

# ============================================================
# EXECUTION & ERROR HANDLING
# ============================================================

if st.button(f"Run {feature}", type="primary", use_container_width=True):
    if not request_is_ready(feature, query, position_a, position_b):
        st.warning("Please enter your question before running.")
    else:
        endpoint = endpoint_map[feature]
        payload = build_request_payload(
            feature=feature,
            text=query,
            position_a=position_a,
            position_b=position_b,
            documents=selected_comparison_docs if selected_comparison_docs else None,
            user_id=active_user,
        )

        with st.spinner(f"Executing {feature}..."):
            try:
                response = requests.post(
                    f"{API_BASE_URL}{endpoint}",
                    json=payload,
                    timeout=90,
                )

                if response.status_code >= 400:
                    try:
                        err_payload = response.json()
                        detail = err_payload.get("detail", response.text)
                    except Exception:
                        detail = response.text

                    st.error(f"Error ({response.status_code}): {detail}")
                    st.session_state["session_history"].append({
                        "timestamp": datetime.datetime.now().isoformat(),
                        "feature": feature,
                        "query": query.strip(),
                        "success": False,
                        "error": str(detail),
                        "data": None,
                    })

                else:
                    result_data = response.json()
                    st.session_state["last_result"] = result_data
                    st.session_state["last_feature"] = feature
                    st.session_state["last_query"] = query.strip()
                    st.session_state["session_history"].append({
                        "timestamp": datetime.datetime.now().isoformat(),
                        "feature": feature,
                        "query": query.strip(),
                        "success": True,
                        "error": None,
                        "data": result_data,
                    })

            except requests.RequestException as exc:
                st.error(f"Network error communicating with backend: {exc}")


# ============================================================
# VISUALIZATION & RESULT RENDERERS
# ============================================================

def _render_sources_section(sources: list):
    st.markdown("### Retrieved Source Evidence")
    if isinstance(sources, list) and sources:
        for idx, src in enumerate(sources, start=1):
            if not isinstance(src, dict):
                st.write(src)
                continue
            doc = src.get("document", "Unknown document")
            page = src.get("page", "N/A")
            chunk_id = src.get("chunk_id", "N/A")
            h_score = src.get("hybrid_score", 0.0)
            with st.container(border=True):
                col_info, col_score = st.columns([4, 1])
                with col_info:
                    st.markdown(f"**{idx}. {doc}**")
                    st.caption(f"Page `{page}` · Chunk ID: `{chunk_id}`")
                with col_score:
                    if h_score:
                        st.metric("Hybrid Score", f"{float(h_score):.3f}")
    else:
        st.info("No source evidence records retrieved for this query.")


def _render_visjs_network(nodes_data: list[dict], edges_data: list[dict], height_px: int = 480):
    """Render an interactive drag/zoom/physics network graph using vis-network."""
    nodes_json = json.dumps(nodes_data)
    edges_json = json.dumps(edges_data)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
      <style type="text/css">
        #network {{
          width: 100%;
          height: {height_px}px;
          border: 1px solid #334155;
          border-radius: 8px;
          background-color: #0f172a;
        }}
      </style>
    </head>
    <body>
      <div id="network"></div>
      <script type="text/javascript">
        var nodes = new vis.DataSet({nodes_json});
        var edges = new vis.DataSet({edges_json});
        var container = document.getElementById('network');
        var data = {{ nodes: nodes, edges: edges }};
        var options = {{
          nodes: {{
            shape: 'box',
            margin: 10,
            font: {{ color: '#f8fafc', size: 13, face: 'Inter, sans-serif' }},
            borderWidth: 2,
            shadow: true
          }},
          edges: {{
            arrows: 'to',
            color: {{ color: '#94a3b8', highlight: '#38bdf8' }},
            font: {{ color: '#cbd5e1', size: 10, align: 'horizontal' }},
            smooth: {{ type: 'cubicBezier' }}
          }},
          physics: {{
            barnesHut: {{ gravitationalConstant: -3000, springLength: 120 }},
            stabilization: {{ iterations: 100 }}
          }},
          interaction: {{
            hover: true,
            tooltipDelay: 100,
            zoomView: true,
            dragView: true
          }}
        }};
        var network = new vis.Network(container, data, options);
      </script>
    </body>
    </html>
    """
    components.html(html_content, height=height_px + 20)


def _format_result_as_markdown(feature_name: str, query_text: str, result_obj: dict) -> str:
    """Format single result as readable Markdown."""
    lines = [
        f"# UNKNOWN Research Result: {feature_name}",
        f"**Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Query:** {query_text}",
        "---",
    ]
    if "answer" in result_obj:
        lines.append("## Answer")
        lines.append(str(result_obj.get("answer", "")))
        lines.append("")

    if "subquestions" in result_obj:
        lines.append("## Decomposed Sub-Questions")
        for sq in result_obj.get("subquestions", []):
            lines.append(f"- {sq}")
        lines.append("")

    if "comparison" in result_obj:
        lines.append("## Comparison Matrix")
        for aspect in result_obj.get("comparison", []):
            lines.append(f"### {aspect.get('aspect')}")
            for v in aspect.get("values", []):
                lines.append(f"- **{v.get('entity')}**: {v.get('value')} *(Source: {v.get('document')}, p.{v.get('page')})*")
        lines.append("")

    if "gaps" in result_obj:
        lines.append("## Identified Research Gaps")
        for g in result_obj.get("gaps", []):
            lines.append(f"- **[{g.get('type')}]** {g.get('gap')} *(Confidence: {g.get('confidence')})*")
            lines.append(f"  *Rationale:* {g.get('rationale')}")
        lines.append("")

    sources = result_obj.get("sources", [])
    if sources:
        lines.append("## Source Citations")
        for s in sources:
            if isinstance(s, dict):
                lines.append(f"- **{s.get('document', 'Unknown')}** (Page {s.get('page')}, Chunk `{s.get('chunk_id')}`)")
    return "\n".join(lines)


# ============================================================
# RESULTS DISPLAY
# ============================================================

result = st.session_state.get("last_result")
last_feature = st.session_state.get("last_feature", "")
last_query = st.session_state.get("last_query", "")

if result is not None:
    st.divider()
    st.subheader(f"Results: {last_feature}")

    # 1. Multi-Step Reasoning Result Renderer
    if last_feature == "Multi-Step Reasoning" and isinstance(result, dict):
        subqs = result.get("subquestions", [])
        answer = result.get("answer", "")
        sources = result.get("sources", [])

        if subqs:
            st.markdown("### Decomposed Sub-Questions")
            for idx, sq in enumerate(subqs, start=1):
                st.markdown(f'<span class="badge badge-subq">Sub-Q {idx}</span> {html.escape(sq)}', unsafe_allow_html=True)
            st.write("")

        st.markdown("### Grounded Reasoning Synthesis")
        st.info(answer)

        _render_sources_section(sources)

    # 2. Knowledge Mind Map Renderer
    elif last_feature == "Knowledge Mind Map" and isinstance(result, dict):
        nodes = result.get("nodes", [])
        edges = result.get("edges", [])
        sources = result.get("sources", [])

        if not nodes:
            st.info("No conceptual graph nodes were extracted for this query.")
        else:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                all_types = sorted(list({n.get("type", "CONCEPT") for n in nodes}))
                selected_types = st.multiselect("Filter by Node Category", options=all_types, default=all_types)
            with col_f2:
                min_conf = st.slider("Minimum Confidence", 0.0, 1.0, 0.0, 0.05)

            filtered_nodes = [
                n for n in nodes
                if n.get("type", "CONCEPT") in selected_types and float(n.get("confidence", 0.0)) >= min_conf
            ]
            valid_ids = {n.get("id") for n in filtered_nodes}
            filtered_edges = [
                e for e in edges
                if e.get("source") in valid_ids and e.get("target") in valid_ids
            ]

            color_palette = {
                "CONCEPT": "#10b981",
                "METHOD": "#f59e0b",
                "FINDING": "#8b5cf6",
                "TOPIC": "#3b82f6",
                "LIMITATION": "#ef4444",
                "DOCUMENT": "#64748b",
            }

            # Interactive vis.js graph
            vis_nodes = [
                {
                    "id": str(n.get("id")),
                    "label": f"{n.get('label', n.get('id'))}\n[{n.get('type')}]",
                    "color": {
                        "background": color_palette.get(str(n.get("type", "CONCEPT")).upper(), "#3b82f6"),
                        "border": "#f8fafc",
                    },
                    "title": f"<b>{html.escape(str(n.get('label')))}</b><br>{html.escape(str(n.get('description', '')))}<br>Doc: {html.escape(str(n.get('document', '')))}, p.{n.get('page')}",
                }
                for n in filtered_nodes
            ]
            vis_edges = [
                {
                    "from": str(e.get("source")),
                    "to": str(e.get("target")),
                    "label": str(e.get("relationship", "")),
                }
                for e in filtered_edges
            ]

            st.markdown("### Interactive Relational Mind Map (Drag & Zoom)")
            _render_visjs_network(vis_nodes, vis_edges, height_px=450)

            # Static Graphviz fallback
            with st.expander("Static Graphviz Chart", expanded=False):
                gv_lines = ["digraph MindMap {", "  rankdir=LR;", '  node [shape=box, style="rounded,filled", fontname="sans-serif"];']
                for n in filtered_nodes:
                    nid = str(n.get("id")).replace('"', '')
                    lbl = str(n.get("label", nid)).replace('"', '\\"')
                    ntype = str(n.get("type", "CONCEPT")).upper()
                    bg = color_palette.get(ntype, "#e2e8f0")
                    gv_lines.append(f'  "{nid}" [label="{lbl}\\n[{ntype}]", fillcolor="{bg}"];')
                for e in filtered_edges:
                    src = str(e.get("source")).replace('"', '')
                    tgt = str(e.get("target")).replace('"', '')
                    rel = str(e.get("relationship", "")).replace('"', '\\"')
                    gv_lines.append(f'  "{src}" -> "{tgt}" [label="{rel}"];')
                gv_lines.append("}")
                st.graphviz_chart("\n".join(gv_lines), use_container_width=True)

            # Node Details Inspector
            st.markdown("### Graph Node Details")
            for node in filtered_nodes:
                with st.expander(f"{node.get('label', node.get('id'))} [{node.get('type')}]"):
                    st.write(node.get("description", "No description available."))
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Confidence", f"{float(node.get('confidence', 0)):.2f}")
                    c2.write(f"**Document:** {node.get('document', 'N/A')}")
                    c3.write(f"**Page / Chunk:** {node.get('page', 'N/A')} / `{node.get('chunk_id', 'N/A')}`")
                    ev = node.get("evidence", [])
                    if ev:
                        st.caption("**Evidence Quote:** " + "; ".join(ev if isinstance(ev, list) else [str(ev)]))

            if filtered_edges:
                st.markdown("### Relationship Matrix")
                st.dataframe(
                    [
                        {
                            "Source Node": e.get("source"),
                            "Relationship": e.get("relationship"),
                            "Target Node": e.get("target"),
                            "Confidence": f"{float(e.get('confidence', 0)):.2f}",
                            "Evidence": e.get("evidence", ""),
                        }
                        for e in filtered_edges
                    ],
                    use_container_width=True,
                )

        _render_sources_section(sources)

    # 3. Knowledge DNA Renderer
    elif last_feature == "Knowledge DNA" and isinstance(result, dict):
        area = result.get("research_area", "General")
        core_topics = result.get("core_topics", [])
        key_concepts = result.get("key_concepts", [])
        methods = result.get("methods", [])
        findings = result.get("findings", [])
        limitations = result.get("limitations", [])
        themes = result.get("themes", [])
        signals = result.get("signals", [])
        relationships = result.get("relationships", [])
        sources = result.get("sources", [])

        st.markdown(f"**Research Area:** `{area}`")

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Core Topics", len(core_topics))
        m2.metric("Key Concepts", len(key_concepts))
        m3.metric("Methods", len(methods))
        m4.metric("Findings", len(findings))
        m5.metric("Limitations", len(limitations))
        m6.metric("Themes", len(themes))

        if signals:
            dna_colors = {
                "TOPIC": "#3b82f6",
                "CONCEPT": "#10b981",
                "METHOD": "#f59e0b",
                "FINDING": "#8b5cf6",
                "LIMITATION": "#ef4444",
            }
            vis_nodes = [
                {
                    "id": str(s.get("name")),
                    "label": f"{s.get('name')}\n[{s.get('type')}]",
                    "color": {"background": dna_colors.get(str(s.get("type", "CONCEPT")).upper(), "#64748b")},
                    "title": f"<b>{html.escape(str(s.get('name')))}</b><br>Category: {s.get('type')}",
                }
                for s in signals
            ]
            vis_edges = [
                {
                    "from": str(r.get("source")),
                    "to": str(r.get("target")),
                    "label": str(r.get("relationship", "")),
                }
                for r in relationships
            ]
            st.markdown("### Interactive DNA Topology")
            _render_visjs_network(vis_nodes, vis_edges, height_px=420)

        t1, t2, t3, t4 = st.tabs(["Concepts & Topics", "Methods & Findings", "Limitations & Themes", "Signal Relationships"])
        with t1:
            st.markdown("**Core Topics:** " + ", ".join(f"`{t}`" for t in core_topics))
            st.markdown("**Key Concepts:** " + ", ".join(f"`{c}`" for c in key_concepts))
        with t2:
            st.markdown("**Methods:** " + ", ".join(f"`{m}`" for m in methods))
            st.markdown("**Key Findings:**")
            for f in findings:
                st.markdown(f"- ✅ {f}")
        with t3:
            st.markdown("**Reported Limitations:**")
            for lim in limitations:
                st.markdown(f"- ⚠️ {lim}")
            st.markdown("**Synthesized Themes:** " + ", ".join(f"`{th}`" for th in themes))
        with t4:
            if relationships:
                st.dataframe(relationships, use_container_width=True)
            else:
                st.info("No inter-signal relationships recorded.")

        _render_sources_section(sources)

    # 4. Compare Research Renderer
    elif last_feature == "Compare Research" and isinstance(result, dict):
        entities = result.get("entities", [])
        summary = result.get("summary", "")
        comparison = result.get("comparison", [])
        sources = result.get("sources", [])

        st.markdown(f"**Compared Entities:** " + ", ".join(f"`{e}`" for e in entities))
        st.markdown("### Executive Comparison Summary")
        st.write(summary)

        st.markdown("### Detailed Aspect Breakdown")
        for aspect in comparison:
            with st.container(border=True):
                st.markdown(f"#### {aspect.get('aspect', 'Aspect')}")
                for val in aspect.get("values", []):
                    st.markdown(f"- **{val.get('entity')}:** {val.get('value')}")
                    st.caption(f"Evidence: *\"{val.get('evidence')}\"* — Supported by `{val.get('document')}` (Page {val.get('page')})")

        _render_sources_section(sources)

    # 5. Research Gaps Renderer
    elif last_feature == "Research Gaps" and isinstance(result, dict):
        area = result.get("research_area", "")
        findings = result.get("existing_findings", [])
        limitations = result.get("reported_limitations", [])
        gaps = result.get("gaps", [])
        sources = result.get("sources", [])

        if area:
            st.markdown(f"**Research Domain:** `{area}`")

        if findings:
            st.markdown("### Established Findings in Literature")
            for f in findings:
                st.markdown(f"✅ {f}")

        if limitations:
            st.markdown("### Reported Limitations")
            for lim in limitations:
                st.markdown(f"⚠️ {lim}")

        st.markdown("### Identified Research Gaps")
        if not gaps:
            st.info("No research gaps identified from retrieved context.")
        else:
            for idx, g in enumerate(gaps, start=1):
                with st.container(border=True):
                    st.markdown(f"**{idx}. {g.get('gap')}**")
                    col_c, col_r = st.columns([1, 4])
                    col_c.metric("Confidence", f"{float(g.get('confidence', 0)):.2f}")
                    col_c.caption(f"Type: `{g.get('type')}`")
                    col_r.write(f"**Rationale:** {g.get('rationale')}")
                    doc = g.get("document")
                    if doc:
                        col_r.caption(f"Source: `{doc}` (Page {g.get('page')})")

        _render_sources_section(sources)

    # 6. Default / Standard Renderer (Assistant, Claims, etc.)
    else:
        if isinstance(result, dict):
            if "answer" in result:
                st.markdown("### Answer")
                st.write(result["answer"])
            if "verdict" in result:
                st.markdown(f"### Verdict: `{result['verdict']}` (Confidence: {result.get('confidence', 0):.2f})")
                st.write(result.get("explanation", ""))
            if "sources" in result:
                _render_sources_section(result["sources"])
        else:
            st.json(result)

    with st.expander("Raw API JSON Response", expanded=False):
        st.json(result)

    # ============================================================
    # INDIVIDUAL RESULT DOWNLOADS
    # ============================================================
    st.markdown("### Export Current Result")
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "Download Result (JSON)",
            data=json.dumps(result, indent=2, ensure_ascii=False),
            file_name=f"unknown_{last_feature.lower().replace(' ', '_')}.json",
            mime="application/json",
            use_container_width=True,
        )
    with dl_col2:
        md_text = _format_result_as_markdown(last_feature, last_query, result)
        st.download_button(
            "Download Result (Markdown)",
            data=md_text,
            file_name=f"unknown_{last_feature.lower().replace(' ', '_')}.md",
            mime="text/markdown",
            use_container_width=True,
        )

# ============================================================
# CONSOLIDATED RESEARCH REPORT (SESSION LEVEL)
# ============================================================

session_history = st.session_state.get("session_history", [])
if session_history:
    st.divider()
    st.subheader("Consolidated Research Session Report")
    st.write(
        f"Generate a comprehensive report compiled from all **{len(session_history)}** queries executed "
        "in your active session. Failed queries are explicitly marked, and evidence citations are retained."
    )

    def _build_full_markdown_report() -> str:
        rep = [
            "# UNKNOWN Academic Research Report",
            f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Workspace:** {st.session_state.get('user_id', 'default_user')}",
            f"**Total Queries Executed:** {len(session_history)}",
            "",
            "## Executive Summary",
            "This document compiles verified empirical evidence, multi-step causal reasoning, ",
            "comparisons, and knowledge structures generated during the research session.",
            "",
            "---",
        ]
        for idx, entry in enumerate(session_history, start=1):
            rep.append(f"## {idx}. Tool: {entry.get('feature')}")
            rep.append(f"**Query:** {entry.get('query')}")
            rep.append(f"**Status:** {'SUCCESS' if entry.get('success') else 'FAILED'}")
            rep.append(f"**Timestamp:** {entry.get('timestamp')}")
            rep.append("")

            if not entry.get("success"):
                rep.append(f"> ⚠️ **Failure Detail:** {entry.get('error')}")
                rep.append("")
                continue

            data = entry.get("data")
            if isinstance(data, dict):
                if "answer" in data:
                    rep.append("### Synthesized Answer")
                    rep.append(str(data["answer"]))
                    rep.append("")
                if "subquestions" in data:
                    rep.append("### Sub-Questions")
                    for sq in data["subquestions"]:
                        rep.append(f"- {sq}")
                    rep.append("")
                if "summary" in data:
                    rep.append("### Summary")
                    rep.append(str(data["summary"]))
                    rep.append("")
                if "gaps" in data:
                    rep.append("### Research Gaps")
                    for g in data["gaps"]:
                        rep.append(f"- **[{g.get('type')}]** {g.get('gap')} *(Confidence: {g.get('confidence')})*")
                    rep.append("")
                sources = data.get("sources", [])
                if sources:
                    rep.append("### Evidence Citations")
                    for s in sources:
                        if isinstance(s, dict):
                            rep.append(f"- `{s.get('document')}` (p.{s.get('page')}, Chunk `{s.get('chunk_id')}`)")
                    rep.append("")
            rep.append("---")
        return "\n".join(rep)

    def _build_full_html_report() -> str:
        md_content = _build_full_markdown_report()
        # Convert markdown headers and lists to clean HTML for printing / PDF saving
        escaped = html.escape(md_content)
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>UNKNOWN Academic Research Report</title>
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 900px; margin: 40px auto; padding: 0 20px; }}
            h1 {{ color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }}
            h2 {{ color: #1e293b; margin-top: 30px; }}
            h3 {{ color: #334155; }}
            pre {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; overflow-x: auto; white-space: pre-wrap; font-family: monospace; font-size: 13px; }}
            @media print {{ body {{ margin: 0; padding: 0; }} }}
          </style>
        </head>
        <body>
          <pre>{escaped}</pre>
        </body>
        </html>
        """

    full_md = _build_full_markdown_report()
    full_json = json.dumps(session_history, indent=2, ensure_ascii=False)
    full_html = _build_full_html_report()

    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        st.download_button(
            "Download Report (.md)",
            data=full_md,
            file_name=f"unknown_research_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with rc2:
        st.download_button(
            "Download Report (.json)",
            data=full_json,
            file_name=f"unknown_research_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )
    with rc3:
        st.download_button(
            "Download Report (.html / Printable)",
            data=full_html,
            file_name=f"unknown_research_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            mime="text/html",
            use_container_width=True,
            help="Open in any web browser and use File > Print (or Ctrl+P) to save as PDF.",
        )

st.divider()
st.caption("UNKNOWN Research Intelligence Platform · All Rights Reserved")
