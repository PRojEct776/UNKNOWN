"""
Document Eligibility and Test-Fixture Filtering Module for UNKNOWN

Ensures development/test fixtures (sample_ieee.pdf, duplicate_test_doc.txt, etc.)
are never leaked into normal user retrieval or workspace listings.
Provides workspace authorization filtering based on document metadata.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from app.rag.config import settings
from app.rag.logger import logger

# Canonical set of known development/test fixtures
KNOWN_TEST_DOCUMENTS: frozenset[str] = frozenset(
    {
        "sample_ieee.pdf",
        "sample_ieee",
        "sample_ieee.json",
        "duplicate_test_doc.txt",
        "duplicate_test_doc",
        "duplicate_test_doc.json",
        "duplicate_test_doc_copy.txt",
        "unknown_test.txt.txt",
        "unknown_test.txt",
        "unknown_test",
        "unknown_test.json",
        "empty.txt",
    }
)


def is_test_document(document_name: str, metadata: dict | None = None) -> bool:
    """
    Determine whether a document is a development or test fixture.

    Uses:
    1. Explicit metadata (`is_test_document == True`)
    2. Known test fixture set
    3. Structural naming patterns (e.g. prefix `sample_`, `test_`, `duplicate_test_`)
    """
    if not document_name:
        return True

    # 1. Check provided or disk metadata
    if metadata and metadata.get("is_test_document") is True:
        return True

    norm_name = Path(document_name).name.lower()
    norm_stem = Path(document_name).stem.lower()

    # 2. Known fixture lookup
    if norm_name in KNOWN_TEST_DOCUMENTS or norm_stem in KNOWN_TEST_DOCUMENTS:
        return True

    # 3. Structural pattern checks
    if (
        "sample_ieee" in norm_name
        or "duplicate_test" in norm_name
        or norm_name.startswith("test_")
        or "_test." in norm_name
        or norm_stem.endswith("_test")
    ):
        return True

    # 4. Check saved metadata on disk if not provided
    if settings.METADATA_DIR.exists():
        # Try exact stem or strip extensions
        meta_candidates = [
            settings.METADATA_DIR / f"{norm_stem}_metadata.json",
            settings.METADATA_DIR / f"{Path(norm_stem).stem}_metadata.json",
        ]
        for meta_path in meta_candidates:
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        disk_meta = json.load(f)
                        if disk_meta.get("is_test_document") is True:
                            return True
                except Exception:
                    pass

    return False


def get_user_authorized_documents(
    user_id: str | None,
    include_test_docs: bool = False,
) -> set[str]:
    """
    Return the set of document filenames authorized for a specific user/workspace.

    Rules:
    - If user_id is an explicitly designated test/demo account (or None for unauthenticated test fallback):
      Returns documents owned by the user plus baseline sample documents ("default_user" or demo accounts).
    - If user_id is a fresh/new user (not in designated demo accounts):
      Returns ONLY documents where metadata user_id matches user_id. Fresh accounts start with set() (empty workspace).
    - Test documents (sample_ieee, duplicate_test_doc, etc.) are excluded unless include_test_docs=True.
    """
    from app.auth import is_demo_account
    from app.rag.utils import list_supported_documents

    authorized: set[str] = set()
    user_is_demo = is_demo_account(user_id) or user_id is None

    for paper_path in list_supported_documents(settings.PAPERS_DIR):
        doc_name = paper_path.name
        stem = paper_path.stem

        doc_user = "default_user"
        is_test = is_test_document(doc_name)

        # Check metadata dir
        meta_file = settings.METADATA_DIR / f"{stem}_metadata.json"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    if "user_id" in meta:
                        doc_user = meta["user_id"]
                    if meta.get("is_test_document"):
                        is_test = True
            except Exception:
                pass

        # Check json dir
        json_file = settings.JSON_DIR / f"{stem}.json"
        if json_file.exists():
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    doc_json = json.load(f)
                    if "user_id" in doc_json:
                        doc_user = doc_json["user_id"]
            except Exception:
                pass

        if not include_test_docs and is_test:
            continue

        if user_is_demo:
            if doc_user == user_id or doc_user == "default_user" or is_demo_account(doc_user):
                authorized.add(doc_name)
        else:
            if doc_user == user_id:
                authorized.add(doc_name)

    return authorized
