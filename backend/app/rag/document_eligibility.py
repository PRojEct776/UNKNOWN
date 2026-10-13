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
    - If user_id is provided, only documents belonging to user_id are returned.
    - If user_id has uploaded no documents, returns an empty set() (clean workspace).
    - If user_id is None, returns all documents in the library.
    - Test documents are excluded unless include_test_docs=True.
    """
    authorized: set[str] = set()

    if not settings.METADATA_DIR.exists():
        return authorized

    for meta_path in settings.METADATA_DIR.glob("*_metadata.json"):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                doc_name = meta.get("document", "")
                if not doc_name:
                    continue

                # Exclude test documents unless requested
                if not include_test_docs and is_test_document(doc_name, meta):
                    continue

                doc_user = meta.get("user_id")

                # If user_id filter is specified, enforce strict ownership
                if user_id is not None:
                    if doc_user == user_id:
                        authorized.add(doc_name)
                else:
                    authorized.add(doc_name)
        except Exception as exc:
            logger.debug(f"Error reading metadata {meta_path}: {exc}")

    return authorized
