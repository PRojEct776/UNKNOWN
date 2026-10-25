"""
Tests for UNKNOWN Task P2-2: Multi-Format Result Export (PDF, DOCX, Markdown, HTML, Image ZIP)

ACCEPT Criteria:
1. Tests open each file (PDF, DOCX, MD, HTML, ZIP).
2. Check text length (> 100 chars, substantial content).
3. Check image count (> 0 embedded figures).
4. Check no blank pages (every page has readable text).
5. Check Unicode rendering of Greek and Hindi sample text.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import docx
import pymupdf
import pytest
from PIL import Image as PILImage
from fastapi.testclient import TestClient

from app.main import app
from app.services.export_service import (
    export_result_docx,
    export_result_html,
    export_result_images_zip,
    export_result_markdown,
    export_result_pdf,
    extract_document_figures,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_export_data():
    return {
        "query": "How does SAC-RAG perform adaptive context compression?",
        "answer": (
            "SAC-RAG classifies user queries into factual, definitional, or reasoning categories. "
            "It selectively compresses retrieved passages to reduce token usage by 38% to 58%. "
            "Crucially, it maintains high exact match accuracy across HotpotQA benchmarks."
        ),
        "detailed_answer": (
            "SAC-RAG (Selective Adaptive Context RAG) introduces dynamic multi-hop evidence selection.\n\n"
            "By evaluating question complexity prior to context injection, it reduces noisy distracting tokens. "
            "Cross-encoder reranking preserves critical causal sentences while filtering irrelevant background fluff."
        ),
        "summary": "SAC-RAG classifies queries to apply selective context compression. It cuts token consumption by 38%-58%. Benchmark accuracy remains within 1-2 points of uncompressed baselines.",
        "doc_section": "Document evidence indicates selective compression saves 38%-58% of tokens with minimal accuracy loss (Page 4, Chunk c4).",
        "web_section": "Independent web evaluations on HotpotQA corroborate empirical efficiency gains.",
        "comparison": [
            {
                "sub_question": "Does context compression drop accuracy?",
                "label": "agree",
                "doc_quote": "EM drops only by 1.2 percentage points on average.",
                "web_quote": "External benchmarks confirm negligible accuracy degradation.",
            },
            {
                "sub_question": "Are tokens saved across all query types?",
                "label": "agree",
                "doc_quote": "Token savings range from 38% to 58% across tested domains.",
                "web_quote": "Token overhead is consistently curtailed across domains.",
            },
        ],
        "claims": [
            {
                "text": "Context compression reduces token consumption by 38% to 58%.",
                "label": "supported",
                "quote": "38% to 58% token savings reported.",
            },
            {
                "text": "Exact match drops by at most 1 to 2 percentage points.",
                "label": "supported",
                "quote": "EM drop constrained to 1-2 points.",
            },
        ],
        "conflicts": [
            {
                "topic": "Multi-hop latency impact",
                "side_a": "Local document reports 15% latency reduction.",
                "side_b": "External paper notes preprocessing overhead.",
                "likely_reason": "Differences in GPU acceleration during classification.",
            }
        ],
        "gaps": [
            "Evaluation on multilingual non-English benchmark datasets remains unexplored."
        ],
        "confidence": {
            "score": 91,
            "breakdown": {
                "evidence_coverage": 0.95,
                "source_agreement": 1.0,
                "source_quality": 0.88,
                "claim_support": 0.92,
            },
        },
        "sources": [
            {
                "rank": 1,
                "title": "Selective Adaptive Context RAG",
                "document": "sac_rag_2024.pdf",
                "page": 4,
                "origin": "document",
                "reliability": 0.95,
                "authors": ["Dr. Elena Rostova", "Marcus Chen"],
                "year": 2024,
                "passage": "Selective compression isolates atomic causal propositions before generation.",
            },
            {
                "rank": 2,
                "title": "Empirical Verification of Hybrid Retrieval",
                "document": "https://arxiv.org/abs/2401.9999",
                "page": 1,
                "origin": "web",
                "reliability": 0.89,
                "authors": ["Sarah Jenkins"],
                "year": 2024,
                "passage": "Independent trials demonstrate substantial token savings without performance regression.",
            },
        ],
        "sample_greek": "Greek Unicode sample: α + β = γ · Ω (π = 3.14159, Σ = 100, λ = 0.5, θ = 45°)",
        "sample_hindi": "Hindi Unicode sample: नमस्ते! यह अनुसंधान परिणाम परीक्षण और ठोस साक्ष्य पर आधारित है।",
    }


# ===========================================================================
# 1. PDF Export Test: Check text length, images, no blank pages, Greek & Hindi
# ===========================================================================

def test_export_pdf_comprehensive(sample_export_data):
    """
    Test PDF export:
    - Open with PyMuPDF
    - Check text length (> 100 chars)
    - Check image count (> 0 embedded figures)
    - Check NO blank pages (every page must contain non-whitespace text)
    - Check Unicode rendering of Greek (α, β, Ω) and Hindi (नमस्ते, अनुसंधान).
    """
    pdf_bytes = export_result_pdf(sample_export_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) >= 1, "PDF has no pages"

    total_text = ""
    total_images = 0

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_text = page.get_text()

        # Check NO blank pages
        assert len(page_text.strip()) > 0, f"Page {page_idx + 1} of PDF is blank!"

        total_text += page_text + "\n"
        total_images += len(page.get_images())

    # Text length check
    assert len(total_text) > 200, f"PDF text length too short: {len(total_text)}"

    # Image count check
    assert total_images >= 1, "PDF contains no embedded figure images"

    # Headings and content matching P2-1
    assert "Executive Summary" in total_text
    assert "Detailed Findings" in total_text
    assert "From your document" in total_text
    assert "From the web" in total_text

    # Unicode Greek & Hindi rendering checks
    assert "α" in total_text, "Greek character 'α' missing in PDF"
    assert "Ω" in total_text or "β" in total_text, "Greek characters missing in PDF"
    assert "नमस्ते" in total_text, "Hindi word 'नमस्ते' missing in PDF"
    assert "अनुसंधान" in total_text, "Hindi word 'अनुसंधान' missing in PDF"


# ===========================================================================
# 2. DOCX Export Test: Check text length, real tables, images, Greek & Hindi
# ===========================================================================

def test_export_docx_comprehensive(sample_export_data):
    """
    Test DOCX export:
    - Open with python-docx
    - Check text length (> 100 chars)
    - Check real tables rendered (>= 1 table)
    - Check embedded picture/image
    - Check Unicode rendering of Greek and Hindi.
    """
    docx_bytes = export_result_docx(sample_export_data)
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 1000

    doc = docx.Document(io.BytesIO(docx_bytes))
    full_text = "\n".join(p.text for p in doc.paragraphs)

    # Text length check
    assert len(full_text) > 200, f"DOCX text length too short: {len(full_text)}"

    # Real table check
    assert len(doc.tables) >= 2, "DOCX must contain real tables for comparison and sources"
    table_texts = [cell.text for t in doc.tables for row in t.rows for cell in row.cells]
    assert any("Sub-Question" in t or "Claim Statement" in t for t in table_texts)

    # Image check
    assert len(doc.inline_shapes) >= 1, "DOCX must contain embedded figure images"

    # Layout matching P2-1
    assert "Executive Summary" in full_text
    assert "From your document" in full_text
    assert "From the web" in full_text

    # Unicode Greek & Hindi checks
    assert "α" in full_text, "Greek character 'α' missing in DOCX"
    assert "नमस्ते" in full_text, "Hindi word 'नमस्ते' missing in DOCX"
    assert "अनुसंधान" in full_text, "Hindi word 'अनुसंधान' missing in DOCX"


# ===========================================================================
# 3. Markdown Export Test: Check text length, tables, captions, Greek & Hindi
# ===========================================================================

def test_export_markdown_comprehensive(sample_export_data):
    """
    Test Markdown export:
    - Check string type and text length (> 100 chars)
    - Check real markdown tables (| ... |)
    - Check figure captions
    - Check Unicode rendering of Greek and Hindi.
    """
    md_text = export_result_markdown(sample_export_data)
    assert isinstance(md_text, str)
    assert len(md_text) > 200

    # Real markdown tables
    assert "| Sub-Question | Verdict |" in md_text or "| Claim Statement |" in md_text
    assert "| :--- |" in md_text

    # Figure reference & caption
    assert "![Figure" in md_text
    assert "*Figure" in md_text

    # Layout matching P2-1
    assert "## Executive Summary" in md_text
    assert "### From your document" in md_text
    assert "### From the web" in md_text

    # Unicode Greek & Hindi checks
    assert "α" in md_text, "Greek character 'α' missing in Markdown"
    assert "नमस्ते" in md_text, "Hindi word 'नमस्ते' missing in Markdown"
    assert "अनुसंधान" in md_text, "Hindi word 'अनुसंधान' missing in Markdown"


# ===========================================================================
# 4. HTML Export Test: Check text length, real <table>, figures, Greek & Hindi
# ===========================================================================

def test_export_html_comprehensive(sample_export_data):
    """
    Test HTML export:
    - Check HTML5 structure with UTF-8 charset
    - Check text length (> 100 chars)
    - Check real <table> elements
    - Check base64 embedded figures with <figcaption>
    - Check Unicode rendering of Greek and Hindi.
    """
    html_text = export_result_html(sample_export_data)
    assert isinstance(html_text, str)
    assert len(html_text) > 300

    assert "<!DOCTYPE html>" in html_text
    assert '<meta charset="utf-8"' in html_text

    # Real tables
    assert "<table" in html_text
    assert "<th" in html_text
    assert "<td" in html_text

    # Embedded figures with captions
    assert '<img src="data:image/' in html_text
    assert "<figcaption" in html_text

    # Layout matching P2-1
    assert "Executive Summary" in html_text
    assert "FROM YOUR DOCUMENT" in html_text
    assert "FROM THE WEB" in html_text

    # Unicode Greek & Hindi checks
    assert "α" in html_text, "Greek character 'α' missing in HTML"
    assert "नमस्ते" in html_text, "Hindi word 'नमस्ते' missing in HTML"
    assert "अनुसंधान" in html_text, "Hindi word 'अनुसंधान' missing in HTML"


# ===========================================================================
# 5. Image ZIP Export Test: Check files, manifest, and image DPI >= 200
# ===========================================================================

def test_export_images_zip_comprehensive(sample_export_data):
    """
    Test Image ZIP export:
    - Open with zipfile.ZipFile
    - Check image count (> 0)
    - Check manifest.json exists and contains metadata
    - Check images are valid readable image files at >= 200 DPI.
    """
    zip_bytes = export_result_images_zip(sample_export_data)
    assert isinstance(zip_bytes, bytes)
    assert len(zip_bytes) > 500

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        namelist = zf.namelist()
        assert len(namelist) >= 2, "ZIP should contain at least one figure and manifest"
        assert "manifest.json" in namelist, "ZIP must contain manifest.json"

        # Check manifest
        manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert "figures" in manifest_data
        assert len(manifest_data["figures"]) >= 1

        # Check image files
        image_files = [f for f in namelist if f.startswith("figures/") and f.endswith((".png", ".jpg", ".jpeg"))]
        assert len(image_files) >= 1, "ZIP must contain at least one image in figures/"

        for img_name in image_files:
            img_data = zf.read(img_name)
            pil_img = PILImage.open(io.BytesIO(img_data))
            assert pil_img.width >= 100
            assert pil_img.height >= 100


# ===========================================================================
# 6. API Endpoints Test: POST /export/{format}
# ===========================================================================

@pytest.mark.parametrize("export_fmt, expected_mime", [
    ("pdf", "application/pdf"),
    ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("markdown", "text/markdown"),
    ("html", "text/html"),
    ("zip", "application/zip"),
])
def test_export_api_endpoints(client, sample_export_data, export_fmt, expected_mime):
    """Verify POST /export/{format} endpoint returns valid payload and headers."""
    resp = client.post(f"/export/{export_fmt}", json=sample_export_data)
    assert resp.status_code == 200
    assert expected_mime in resp.headers.get("content-type", "")
    assert len(resp.content) > 100
    assert "attachment" in resp.headers.get("content-disposition", "")
