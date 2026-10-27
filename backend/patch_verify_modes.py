import sys
from pathlib import Path

CHECK_ONLY = "--check" in sys.argv
BASE = Path(__file__).resolve().parent
EDITS = []


def edit(path, old, new):
    EDITS.append((path, old, new))


# ---------------- schemas.py ----------------
edit("app/api/schemas.py", r'''        description="Claim to verify against the indexed documents.",
    )
''', r'''        description="Claim to verify against the indexed documents.",
    )
    source_mode: str | None = Field(
        default=None,
        description=(
            "Optional evidence source: 'documents' (default, offline), "
            "'web', or 'both'."
        ),
    )
''')

# ---------------- main.py ----------------
edit("app/main.py", r'''    try:
        response = rag_service.verify_claim(request.claim, document_names=request.document_names)
''', r'''    if request.source_mode is not None:
        from app.rag.source_mode import VALID_MODES

        if request.source_mode not in VALID_MODES:
            raise HTTPException(
                status_code=400,
                detail="Invalid source_mode: " + repr(request.source_mode),
            )

    try:
        if request.source_mode is None:
            response = rag_service.verify_claim(request.claim, document_names=request.document_names)
        else:
            response = rag_service.verify_claim(
                request.claim,
                document_names=request.document_names,
                source_mode=request.source_mode,
            )
''')

# ---------------- rag_service.py ----------------
RS = "app/services/rag_service.py"

edit(RS, r'''from app.rag.dual_retriever import DualRetriever, web_chunk_to_source_dict
''', r'''from app.rag.dual_retriever import (
    DualRetriever,
    _fetch_web_chunks,
    _web_gaps_from_statuses,
    web_chunk_to_source_dict,
)
''')

edit(RS, r'''class RAGService:
    """Application service for the UNKNOWN X RAG pipeline."""
''', r'''def _verify_web_failed(statuses):
    return any(
        s.get("outcome") in ("error", "timeout", "not_loaded") for s in (statuses or [])
    )


def _verify_web_gaps(statuses):
    try:
        return [str(g) for g in _web_gaps_from_statuses(statuses or [])]
    except Exception:  # noqa: BLE001
        return []


def _verify_web_note(web_chunks, statuses):
    parts = []
    if _verify_web_failed(statuses):
        parts.extend(_verify_web_gaps(statuses))
    if web_chunks:
        parts.append(
            "Web evidence reflects the retrieved web passages "
            "(abstracts or snippets), not the full pages."
        )
    return (" " + " ".join(parts)) if parts else ""


def _verify_empty_response(claim, mode, statuses):
    if mode == "web" or _verify_web_failed(statuses):
        verdict = "UNVERIFIABLE"
    else:
        verdict = "NOT_FOUND"
    scope = "web sources" if mode == "web" else "the selected documents or web sources"
    explanation = (
        "No usable evidence was retrieved from "
        + scope
        + ", so this claim could not be checked. "
        + " ".join(_verify_web_gaps(statuses))
    ).strip()
    return ClaimVerificationResponse(
        claim=claim,
        verdict=verdict,
        confidence=0.0,
        explanation=explanation,
        evidence=[],
        supporting_evidence=[],
        contradicting_evidence=[],
        source_chunk_ids=[],
        sources=[],
    )


def _verify_merge_web(doc_results, web_chunks, budget):
    docs = list(doc_results or [])
    web = [
        web_chunk_to_source_dict(c)
        for c in (web_chunks or [])
        if isinstance(c, dict) and c.get("text")
    ]
    if not web:
        return docs
    web_take = min(len(web), max(1, budget // 2))
    doc_take = min(len(docs), budget - web_take)
    web_take = min(len(web), budget - doc_take)
    merged = docs[:doc_take]
    for i, item in enumerate(web[:web_take]):
        item.setdefault("rank", doc_take + i + 1)
        merged.append(item)
    return merged


class RAGService:
    """Application service for the UNKNOWN X RAG pipeline."""
''')

edit(RS, r'''        _split: bool = True,
    ) -> ClaimVerificationResponse:
''', r'''        _split: bool = True,
        source_mode: str | None = None,
        _web: tuple | None = None,
    ) -> ClaimVerificationResponse:
''')

edit(RS, r'''        logger.info(f"Verifying claim: {claim}")
''', r'''        logger.info(f"Verifying claim: {claim}")

        mode = source_mode
        if mode is not None:
            from app.rag.source_mode import VALID_MODES

            if mode not in VALID_MODES:
                raise ValueError("Invalid source_mode: " + repr(mode))

        web = None
        web_chunks: list = []
        web_statuses: list = []
        web_note = ""
        if mode in ("web", "both"):
            web = _web
            if web is None:
                try:
                    web = _fetch_web_chunks(claim)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Web retrieval failed: %s", exc)
                    web = (
                        [],
                        [
                            {
                                "connector": "web",
                                "outcome": "error",
                                "count": 0,
                                "detail": type(exc).__name__,
                            }
                        ],
                    )
            web_chunks, web_statuses = web
            if mode == "web" and not web_chunks:
                return _verify_empty_response(claim, mode, web_statuses)
            web_note = _verify_web_note(web_chunks, web_statuses)
''')

edit(RS, r'''                part_results = [
                    self.verify_claim(part, document_names=document_names, _split=False)
                    for part in parts
                ]
''', r'''                extra: dict = {}
                if mode is not None:
                    extra["source_mode"] = mode
                if web is not None:
                    extra["_web"] = web
                part_results = [
                    self.verify_claim(
                        part, document_names=document_names, _split=False, **extra
                    )
                    for part in parts
                ]
''')

edit(RS, r'''                    explanation=(
                        f"The claim was checked as {len(part_results)} separate "
                        f"claims: {summary}."
                    ),
''', r'''                    explanation=(
                        f"The claim was checked as {len(part_results)} separate "
                        f"claims: {summary}."
                    )
                    + web_note,
''')

edit(RS, r'''        results = self._search(claim, document_names=document_names)
''', r'''        if mode == "web":
            results = []
        else:
            results = self._search(claim, document_names=document_names)

        if mode in ("web", "both"):
            results = _verify_merge_web(
                results,
                web_chunks,
                getattr(self.context_builder, "max_chunks", 5),
            )
            if not results:
                return _verify_empty_response(claim, mode, web_statuses)
''')

edit(RS, r'''            explanation=verification.explanation,
            evidence=verification.evidence,
            source_chunk_ids=(verification.source_chunk_ids),
''', r'''            explanation=(verification.explanation or "") + web_note,
            evidence=verification.evidence,
            source_chunk_ids=(verification.source_chunk_ids),
''')

# ---------------- apply (all-or-nothing) ----------------
files = {}
errors = []
for rel, old, new in EDITS:
    if rel not in files:
        raw = (BASE / rel).read_bytes()
        crlf = b"\r\n" in raw
        files[rel] = [raw.decode("utf-8").replace("\r\n", "\n"), crlf]
    text = files[rel][0]
    n = text.count(old)
    if n != 1:
        errors.append("%s: anchor matched %d times (need exactly 1):\n%s" % (rel, n, old))
        continue
    files[rel][0] = text.replace(old, new, 1)

if not errors:
    for rel, (text, _crlf) in files.items():
        try:
            compile(text, rel, "exec")
        except SyntaxError as exc:
            errors.append("%s: would not compile: %s" % (rel, exc))

if errors:
    print("ABORTED. Nothing was written.")
    for e in errors:
        print("-", e)
    sys.exit(1)

if CHECK_ONLY:
    print("CHECK OK: %d edits, every anchor matched exactly once, all files compile. Nothing written." % len(EDITS))
    sys.exit(0)

for rel, (text, crlf) in files.items():
    out = text.replace("\n", "\r\n") if crlf else text
    (BASE / rel).write_bytes(out.encode("utf-8"))
    print("patched", rel)
print("DONE: %d edits applied." % len(EDITS))
