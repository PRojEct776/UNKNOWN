"""Guarded patch: Verify v3 (atomic claims). All-or-nothing; aborts unless every anchor matches once."""
import os
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
P_CV = os.path.join(BASE, "app", "rag", "claim_verifier.py")
P_SVC = os.path.join(BASE, "app", "services", "rag_service.py")
P_SCH = os.path.join(BASE, "app", "api", "schemas.py")

CV = []
SVC = []
SCH = []

# ---------------- claim_verifier.py ----------------
CV.append((r'''    def parse_response(''', r'''    @staticmethod
    def select_atomic_claims(original, parts, max_parts=5) -> list[str]:
        """Validate model-proposed atomic claims; fall back to [original] when unsafe."""

        fallback = [original]
        if not isinstance(parts, list):
            return fallback

        original_words = ClaimVerifier._content_words(original)
        original_quantities = [q for _, q in ClaimVerifier._quantities(original)]

        valid = []
        seen = set()
        covered_words = set()
        covered_quantities = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = str(part.get("text", "") or "").strip()
            if not text:
                continue
            key = ClaimVerifier._norm(text)
            if key in seen:
                continue
            words = ClaimVerifier._content_words(text)
            if not words or len(words & original_words) / len(words) < 0.6:
                continue
            quantities = [q for _, q in ClaimVerifier._quantities(text)]
            if any(
                not any(ClaimVerifier._qty_match(q, o) for o in original_quantities)
                for q in quantities
            ):
                continue
            seen.add(key)
            valid.append(text)
            covered_words |= words
            covered_quantities.extend(quantities)

        if len(valid) < 2 or len(valid) > max_parts:
            return fallback
        for o in original_quantities:
            if not any(ClaimVerifier._qty_match(o, q) for q in covered_quantities):
                return fallback
        if original_words:
            share = len(covered_words & original_words) / len(original_words)
            if share < 0.6:
                return fallback
        return valid

    @staticmethod
    def aggregate_verdicts(verdicts) -> "ClaimVerdict":
        """Combine per-part verdicts into one conservative overall verdict."""

        parsed = [ClaimVerdict(v) for v in verdicts]
        if not parsed:
            return ClaimVerdict.NOT_FOUND
        if ClaimVerdict.CONTRADICTED in parsed:
            return ClaimVerdict.CONTRADICTED
        if all(v == ClaimVerdict.SUPPORTED for v in parsed):
            return ClaimVerdict.SUPPORTED
        if any(v in (ClaimVerdict.SUPPORTED, ClaimVerdict.PARTIALLY_SUPPORTED) for v in parsed):
            return ClaimVerdict.PARTIALLY_SUPPORTED
        for label in (ClaimVerdict.UNSUPPORTED, ClaimVerdict.NOT_FOUND, ClaimVerdict.UNVERIFIABLE):
            if label in parsed:
                return label
        return ClaimVerdict.NOT_FOUND

    def parse_response('''))

# ---------------- schemas.py (field first, then model, so the anchor stays unique) ----------------
SCH.append((r'''    contradicting_evidence: list[str] = Field(default_factory=list)''',
r'''    contradicting_evidence: list[str] = Field(default_factory=list)
    atomic_claims: list[AtomicClaimVerification] = Field(default_factory=list)'''))

SCH.append((r'''class ClaimVerificationResponse(BaseModel):''', r'''class AtomicClaimVerification(BaseModel):
    """Verdict for one atomic part of a compound claim."""

    claim: str
    verdict: str
    confidence: float = 0.0
    explanation: str = ""
    evidence: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)


class ClaimVerificationResponse(BaseModel):'''))

# ---------------- rag_service.py ----------------
SVC.append((r'''    def verify_claim(
        self,
        claim: str,
        document_names: list[str] | None = None,
    ) -> ClaimVerificationResponse:''', r'''    def verify_claim(
        self,
        claim: str,
        document_names: list[str] | None = None,
        _split: bool = True,
    ) -> ClaimVerificationResponse:'''))

SVC.append((r'''        logger.info(f"Verifying claim: {claim}")''', r'''        logger.info(f"Verifying claim: {claim}")

        if _split:
            try:
                from app.rag.atomic_claims import split_into_atomic_claims

                raw_parts = split_into_atomic_claims(claim, llm=self.llm)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Atomic claim splitting failed (%s); verifying as one claim.", exc
                )
                raw_parts = []

            parts = self.claim_verifier.select_atomic_claims(claim, raw_parts)

            if len(parts) > 1:
                part_results = [
                    self.verify_claim(part, document_names=document_names, _split=False)
                    for part in parts
                ]
                overall = self.claim_verifier.aggregate_verdicts(
                    [item.verdict for item in part_results]
                )
                merged_supporting: list[str] = []
                merged_contradicting: list[str] = []
                merged_ids: list[str] = []
                merged_sources: list = []
                seen_sources: set[str] = set()
                for item in part_results:
                    for quote in item.supporting_evidence:
                        if quote not in merged_supporting:
                            merged_supporting.append(quote)
                    for quote in item.contradicting_evidence:
                        if quote not in merged_contradicting:
                            merged_contradicting.append(quote)
                    for chunk_id in item.source_chunk_ids:
                        if chunk_id not in merged_ids:
                            merged_ids.append(chunk_id)
                    for source in item.sources:
                        key = repr(source)
                        if key not in seen_sources:
                            seen_sources.add(key)
                            merged_sources.append(source)

                summary = "; ".join(
                    f"[{item.verdict}] {item.claim}" for item in part_results
                )
                return ClaimVerificationResponse(
                    claim=claim,
                    verdict=overall.value,
                    confidence=min(item.confidence for item in part_results),
                    explanation=(
                        f"The claim was checked as {len(part_results)} separate "
                        f"claims: {summary}."
                    ),
                    evidence=merged_supporting + merged_contradicting,
                    source_chunk_ids=merged_ids,
                    supporting_evidence=merged_supporting,
                    contradicting_evidence=merged_contradicting,
                    atomic_claims=[
                        {
                            "claim": item.claim,
                            "verdict": item.verdict,
                            "confidence": item.confidence,
                            "explanation": item.explanation,
                            "evidence": item.evidence,
                            "supporting_evidence": item.supporting_evidence,
                            "contradicting_evidence": item.contradicting_evidence,
                            "source_chunk_ids": item.source_chunk_ids,
                        }
                        for item in part_results
                    ],
                    sources=merged_sources,
                )'''))

PLAN = [(P_CV, CV), (P_SVC, SVC), (P_SCH, SCH)]


def die(msg):
    print("ABORT:", msg)
    sys.exit(1)


def conv(s, eol):
    return s.replace("\r\n", "\n").replace("\n", eol)


results = []
for path, edits in PLAN:
    if not os.path.exists(path):
        die("missing file " + path)
    if os.path.exists(path + ".bak3"):
        die(path + ".bak3 already exists; move it first")
    text = open(path, "rb").read().decode("utf-8")
    if "\r\n" in text:
        if "\n" in text.replace("\r\n", ""):
            die("mixed line endings in " + path)
        eol = "\r\n"
    else:
        eol = "\n"
    for i, (anchor, repl) in enumerate(edits, 1):
        a = conv(anchor, eol)
        n = text.count(a)
        if n != 1:
            die("%s edit %d: anchor matched %d times (need exactly 1)"
                % (os.path.basename(path), i, n))
        text = text.replace(a, conv(repl, eol))
    try:
        compile(text, path, "exec")
    except SyntaxError as e:
        die("syntax error after patching %s: %s" % (path, e))
    results.append((path, text))

for path, text in results:
    shutil.copy2(path, path + ".bak3")
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))
    print("patched", path, "(backup: .bak3)")
print("OK")