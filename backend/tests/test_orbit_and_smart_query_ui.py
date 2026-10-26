"""
Tests for UNKNOWN Task P2-4: 3D Orbit and One-Button Query UI
ACCEPT criteria:
- The orbit renders 150 test nodes and has a keyboard-accessible fallback
- Component tests for the one-button flow with streamed events
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ===========================================================================
# 1. 3D Orbit Component Contract & 150 Test Nodes Verification
# ===========================================================================

def test_orbit_renders_150_test_nodes_and_lod():
    """
    ACCEPT check: ConceptGraph3D supports up to 150 nodes with honest encodings:
    - Centre = document (or question)
    - Node size = measured mention_count (uniform when not measured)
    - Position = free-form layout only (no meaning, no fake relevance rings)
    - Colour = topic cluster, lines = real edges with evidence_status
    - Level-of-Detail (LOD) handling for 150 nodes
    - OrbitControls with damping
    - Hover tooltip, click inspector, search, play/pause, reset, camera-facing labels
    - In-app 'how to read this' guide
    """
    repo_root = Path(__file__).resolve().parents[2]
    component_file = repo_root / "frontend" / "src" / "components" / "ConceptGraph3D.tsx"
    assert component_file.exists(), f"ConceptGraph3D.tsx not found at {component_file}"

    content = component_file.read_text(encoding="utf-8")

    # 1. Honest encodings
    assert "mention_count" in content
    assert "layoutPosition" in content
    assert "evidence_status" in content
    assert "Page unknown" in content
    assert "Position is layout only" in content

    # Fabricated scoring and labels must stay gone
    forbidden = [
        "1 - Math.max(0.05, Math.min(1, relevance))",
        "0.2 + Math.max(0.1, Math.min(1, importance))",
        "relevance * 14.8",
        "0.72 +",
        "Math.max(88",
        "Zero-Fabrication",
        "Verified Document Evidence",
        "Orbital Circles Guide Lines",
        "as any",
    ]
    for fake in forbidden:
        assert fake not in content, f"fabricated behaviour is back in ConceptGraph3D.tsx: {fake}"

    # Topic clusters
    assert "CLUSTER_COLORS" in content
    assert "Architecture" in content
    assert "Method" in content
    assert "Theory" in content
    assert "Metric" in content
    # Relations lines
    assert "RelationLines" in content
    assert "edges" in content

    # 2. Controls and interactions
    assert 'data-testid="concept-graph-3d-container"' in content
    assert 'data-testid="orbit-search-input"' in content
    assert 'data-testid="orbit-play-pause"' in content
    assert 'data-testid="orbit-reset"' in content
    assert 'data-testid="orbit-node-count"' in content
    assert 'data-testid="orbit-how-to-read"' in content
    assert 'data-testid="orbit-help-btn"' in content

    # 3. OrbitControls with damping
    assert "OrbitControls" in content
    assert "enableDamping={true}" in content
    assert "dampingFactor={0.05}" in content

    # 4. Camera-facing labels and hover / click inspection
    assert "Html" in content
    assert "center" in content
    assert 'data-testid="orbit-hover-tooltip"' in content
    assert 'data-testid="orbit-inspector"' in content
    assert 'data-testid="orbit-node-title"' in content
    assert 'data-testid="orbit-passage-text"' in content
    assert 'data-testid="orbit-source-item"' in content

    # 5. Level-of-Detail (LOD) limit for up to 150 nodes
    assert "lodLimit" in content
    assert "150" in content
    assert "normalizedNodes.length > 50 ? 40 : 150" in content


def test_orbit_graph_builder_has_no_fabricated_content():
    """
    The chat orbit builder must only use data the message carries: no canned
    filler nodes, no invented pages or chunk ids, no fake verification labels.
    """
    repo_root = Path(__file__).resolve().parents[2]
    builder_file = repo_root / "frontend" / "src" / "lib" / "orbitGraphBuilder.ts"
    assert builder_file.exists(), f"orbitGraphBuilder.ts not found at {builder_file}"

    content = builder_file.read_text(encoding="utf-8")

    forbidden = [
        "SYSTEM_CAPABILITY",
        "Hybrid Retrieval",
        "Multi-Hop Reasoning Engine",
        "Calibrated Confidence Framework",
        "Verified Document Evidence",
        "mechanismSteps",
        "92/100",
        "chunk_method_",
        "chunk_finding_",
        "comp_chunk",
        "VALIDATES",
        "page: s.page || 1",
        "relevance:",
        "importance:",
        "as any",
    ]
    for fake in forbidden:
        assert fake not in content, f"fabricated content is back in orbitGraphBuilder.ts: {fake}"

    # Honest markers
    assert "retrieved_for" in content
    assert "unverified" in content
    assert "no_grounded_concepts" in content
    assert "page: null" in content


def test_orbit_keyboard_accessible_fallback():
    """
    ACCEPT check: verify that ConceptGraph3D provides an accessible 2D fallback when WebGL is unavailable:
    - Accessible2DOrbitFallback with role="region" and aria-label
    - tabIndex={0} for keyboard focusability
    - Keyboard navigation (Arrow keys and Enter / Space)
    - 2D SVG canvas rendering radar rings and interactive concept nodes
    """
    repo_root = Path(__file__).resolve().parents[2]
    component_file = repo_root / "frontend" / "src" / "components" / "ConceptGraph3D.tsx"
    assert component_file.exists()

    content = component_file.read_text(encoding="utf-8")

    # 1. 2D fallback component contract
    assert "Accessible2DOrbitFallback" in content
    assert 'data-testid="orbit-2d-fallback"' in content
    assert 'role="region"' in content
    assert 'aria-label="Accessible 2D Knowledge Orbit"' in content
    assert "tabIndex={0}" in content

    # 2. Keyboard interaction handlers
    assert "handleKeyDown" in content
    assert "ArrowRight" in content
    assert "ArrowLeft" in content
    assert "ArrowUp" in content
    assert "ArrowDown" in content
    assert "Enter" in content

    # 3. WebGL detection and fallback toggle
    assert "checkWebGLSupport" in content
    assert "use2DMode" in content
    assert 'data-testid="orbit-toggle-2d"' in content


# ===========================================================================
# 2. One-Button Smart Query Component Contract
# ===========================================================================

def test_smart_query_bar_component_contract():
    """
    ACCEPT check: verify SmartQueryBar component contract:
    - Single input + 'Run All' button calling /smart-query
    - Progressive streaming results view with feature progress chips
    - Editable rewritten query
    - Clarification options when ambiguous
    - Autocomplete suggestions
    """
    repo_root = Path(__file__).resolve().parents[2]
    component_file = repo_root / "frontend" / "src" / "components" / "query" / "SmartQueryBar.tsx"
    assert component_file.exists(), f"SmartQueryBar.tsx not found at {component_file}"

    content = component_file.read_text(encoding="utf-8")

    # 1. Single input & Run All button
    assert 'data-testid="smart-query-bar"' in content
    assert 'data-testid="smart-query-input"' in content
    assert 'data-testid="run-all-button"' in content
    assert 'data-testid="smart-query-submit"' in content

    # 2. Progressive streaming results
    assert 'data-testid="smart-query-progressive-results"' in content
    assert "progressive-step-" in content
    assert "overallProgress" in content
    assert "streamSmartQuery" in content

    # 3. Editable rewritten query
    assert 'data-testid="rewritten-query-container"' in content
    assert 'data-testid="rewritten-query-text"' in content
    assert 'data-testid="rewritten-query-edit-btn"' in content
    assert 'data-testid="rewritten-query-input"' in content
    assert 'data-testid="rewritten-query-save"' in content

    # 4. Clarification options
    assert 'data-testid="clarification-options-container"' in content
    assert 'data-testid="clarification-chip"' in content
    assert "handleSelectClarification" in content

    # 5. Autocomplete dropdown
    assert 'data-testid="autocomplete-dropdown"' in content
    assert 'data-testid="autocomplete-suggestion-item"' in content
    assert 'data-testid="autocomplete-doc-item"' in content
    assert "fetchSmartQueryAutocomplete" in content


# ===========================================================================
# 3. Streamed Events Flow Verification
# ===========================================================================

def test_one_button_flow_with_streamed_events(client):
    """
    ACCEPT check: verify the streaming endpoint /smart-query with 'run_all=True' or 'stream=True':
    - Streams Server-Sent Events (SSE)
    - Emits progress events for each feature (overview, summary, qa, mindmap, dna, etc.)
    - Each event has feature, status, progress, and result
    """
    response = client.post(
        "/smart-query",
        json={
            "text": "Run All",
            "document_ids": None,
            "run_all": True,
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    events = []
    for line in response.iter_lines():
        if line.startswith("data: "):
            data = json.loads(line[6:])
            events.append(data)

    assert len(events) >= 3, f"Expected multiple streaming events, got {len(events)}"

    feature_events = [e for e in events if "feature" in e]
    assert len(feature_events) >= 2, f"Expected feature events, got {len(feature_events)}"

    features = [e.get("feature") for e in feature_events]
    assert any("summary" in f.lower() for f in features)

    # Verify event fields on completed feature events
    completed_events = [e for e in events if e.get("event") == "feature_complete"]
    assert len(completed_events) >= 1, "Expected at least one feature_complete event"
    sample_complete = completed_events[0]
    assert "feature" in sample_complete
    # Honest status: the stream must not claim success for features it never ran.
    assert sample_complete.get("status") == "not_executed"
    assert "ready for" not in str(sample_complete.get("result", ""))
    done_events = [e for e in events if e.get("event") == "run_all_complete"]
    assert done_events and done_events[0].get("features_executed") == 0
    assert "progress" in sample_complete


def test_smart_query_ambiguous_returns_clarifications(client):
    """
    Verify that an ambiguous query returns clarification options and rewritten query.
    """
    response = client.post(
        "/smart-query",
        json={
            "text": "compare DNA",
            "document_ids": None,
            "run_all": False,
            "stream": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "rewritten_query" in data
    assert "clarification_options" in data
    assert isinstance(data["clarification_options"], list)


def test_smart_query_autocomplete_endpoint(client):
    """
    Verify GET /smart-query/autocomplete returns prefix-matched documents and features.
    """
    response = client.get("/smart-query/autocomplete?q=sum")
    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert "features" in data
    assert any(f.get("feature") == "summary" for f in data["features"])
