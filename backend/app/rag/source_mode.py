"""Explicit source-mode resolution for the /answer endpoint."""
from __future__ import annotations

VALID_MODES = ("documents", "web", "both")


def resolve_source_mode(
    source_mode: str | None,
    doc_only: bool,
    document_names: list[str] | None,
) -> tuple[bool, list[str] | None]:
    """Return (doc_only, document_names) for the retriever.

    No source_mode: legacy behaviour, inputs returned unchanged.
    documents: web connectors are never called.
    web: document search is skipped (empty document list).
    both: documents and web.
    An explicit mode that contradicts doc_only raises ValueError.
    """
    if source_mode is None:
        return doc_only, document_names
    if source_mode not in VALID_MODES:
        raise ValueError("Invalid source_mode: " + repr(source_mode))
    if source_mode == "documents":
        return True, document_names
    if doc_only:
        raise ValueError("source_mode=" + source_mode + " contradicts doc_only=true.")
    if source_mode == "web":
        return False, []
    return False, document_names
