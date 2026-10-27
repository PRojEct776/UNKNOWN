"""Guarded patch: Verify grounding. All-or-nothing; aborts unless every anchor matches exactly once."""
import os
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
P_CV = os.path.join(BASE, "app", "rag", "claim_verifier.py")
P_SVC = os.path.join(BASE, "app", "services", "rag_service.py")
P_SCH = os.path.join(BASE, "app", "api", "schemas.py")
P_API = os.path.normpath(os.path.join(BASE, "..", "frontend", "src", "lib", "api.ts"))

CV = []
SVC = []
SCH = []
API = []

# ---------------- claim_verifier.py ----------------
CV.append((r'''import json
import re
''', r'''import json
import math
import re
'''))

CV.append((r'''    source_chunk_ids: list[str] = Field(default_factory=list)''',
r'''    source_chunk_ids: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)'''))

CV.append((r'''Do not invent citations.''', r'''Do not invent citations.
Every item in supporting_evidence and contradicting_evidence MUST be an exact,
verbatim quote copied from the DOCUMENT EVIDENCE. Do not paraphrase. You may
join two parts of one passage with "...".
Put quotes that support the claim in supporting_evidence and quotes that
conflict with it in contradicting_evidence.
If the claim contains numbers or units, they must match the evidence exactly;
otherwise use PARTIALLY_SUPPORTED or CONTRADICTED.
For source_chunk_ids use only the Chunk ID values shown in the evidence.'''))

CV.append((r'''  "evidence": [
    "Short evidence statement"
  ],''', r'''  "supporting_evidence": [
    "Exact quote from the evidence that supports the claim"
  ],
  "contradicting_evidence": [
    "Exact quote from the evidence that conflicts with the claim"
  ],'''))

CV.append((r'''        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))''',
r'''        confidence = ClaimVerifier._safe_confidence(data.get("confidence", 0.0))'''))

CV.append((r'''        evidence = data.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = [str(evidence)]''',
r'''        supporting = ClaimVerifier._as_str_list(data.get("supporting_evidence"))
        contradicting = ClaimVerifier._as_str_list(data.get("contradicting_evidence"))
        legacy = ClaimVerifier._as_str_list(data.get("evidence"))
        if legacy and not supporting and not contradicting:
            supporting, contradicting = ClaimVerifier._split_legacy(parsed_verdict, legacy)'''))

CV.append((r'''            evidence=[str(item) for item in evidence],''',
r'''            evidence=supporting + contradicting,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,'''))

CV.append((r'''    def parse_response(''', r'''    @staticmethod
    def _safe_confidence(value) -> float:
        """Return a confidence in [0, 1]; anything unusable becomes 0.0."""

        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        if math.isnan(number) or math.isinf(number):
            return 0.0
        return max(0.0, min(1.0, number))

    @staticmethod
    def _as_str_list(value) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]
        return [str(item) for item in value if str(item).strip()]

    @staticmethod
    def _split_legacy(verdict, evidence):
        """Legacy single evidence list -> (supporting, contradicting) by verdict."""

        if verdict == ClaimVerdict.CONTRADICTED:
            return [], list(evidence)
        return list(evidence), []

    @staticmethod
    def _norm(text) -> str:
        value = str(text).lower()
        value = (
            value.replace("\u2019", "'")
            .replace("\u2018", "'")
            .replace("\u201c", '"')
            .replace("\u201d", '"')
        )
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _fragments(quote) -> list[str]:
        """Split a quote on '...' gaps into normalized fragments to look up."""

        parts = re.split(r"\.\.\.|\u2026", ClaimVerifier._norm(quote))
        fragments = []
        for part in parts:
            part = part.strip(" '\".,;:")
            if len(part) >= 3:
                fragments.append(part)
        return fragments

    @staticmethod
    def _numbers(text) -> list[str]:
        value = re.sub(r"(?<=\d),(?=\d{3})", "", str(text))
        return re.findall(r"\d+(?:\.\d+)?", value)

    def _ground_quotes(self, quotes, chunks, max_chars):
        """Keep only quotes found in one visible chunk; return (kept, chunk_ids)."""

        texts = []
        for chunk in chunks:
            text = str(chunk.get("text", "") or "").strip()
            if max_chars and len(text) > max_chars:
                text = text[:max_chars]
            chunk_id = chunk.get("chunk_id")
            texts.append((str(chunk_id) if chunk_id is not None else None, self._norm(text)))

        kept = []
        ids = []
        for quote in quotes:
            fragments = self._fragments(quote)
            if not fragments:
                continue
            for chunk_id, text in texts:
                if all(fragment in text for fragment in fragments):
                    kept.append(quote)
                    if chunk_id and chunk_id not in ids:
                        ids.append(chunk_id)
                    break
        return kept, ids

    def ground_result(self, result, chunks, max_chars=None):
        """Check a parsed result against the chunks the model was shown."""

        if not chunks:
            return result.model_copy(
                update={
                    "verdict": ClaimVerdict.NOT_FOUND,
                    "confidence": 0.0,
                    "explanation": (
                        "No relevant passages were retrieved, so this claim "
                        "could not be checked."
                    ),
                    "evidence": [],
                    "supporting_evidence": [],
                    "contradicting_evidence": [],
                    "source_chunk_ids": [],
                }
            )

        supporting = list(result.supporting_evidence)
        contradicting = list(result.contradicting_evidence)
        if not supporting and not contradicting and result.evidence:
            supporting, contradicting = self._split_legacy(result.verdict, result.evidence)

        supporting, ids_s = self._ground_quotes(supporting, chunks, max_chars)
        contradicting, ids_c = self._ground_quotes(contradicting, chunks, max_chars)
        ids = ids_s + [item for item in ids_c if item not in ids_s]

        verdict = result.verdict
        ungrounded = (
            (verdict == ClaimVerdict.SUPPORTED and not supporting)
            or (verdict == ClaimVerdict.CONTRADICTED and not contradicting)
            or (
                verdict == ClaimVerdict.PARTIALLY_SUPPORTED
                and not (supporting or contradicting)
            )
        )
        if ungrounded:
            return result.model_copy(
                update={
                    "verdict": ClaimVerdict.NOT_FOUND,
                    "confidence": 0.0,
                    "explanation": (
                        "The model's verdict could not be confirmed: none of its "
                        "quoted evidence appears in the retrieved passages."
                    ),
                    "evidence": [],
                    "supporting_evidence": [],
                    "contradicting_evidence": [],
                    "source_chunk_ids": [],
                }
            )

        explanation = result.explanation
        if verdict == ClaimVerdict.SUPPORTED:
            evidence_numbers = set(self._numbers(" ".join(supporting)))
            missing = []
            for number in self._numbers(result.claim):
                if number not in evidence_numbers and number not in missing:
                    missing.append(number)
            if missing:
                verdict = ClaimVerdict.PARTIALLY_SUPPORTED
                explanation = (
                    f"{explanation} Note: the claim's number(s) {', '.join(missing)} "
                    "do not appear in the quoted evidence, so full support could "
                    "not be confirmed."
                )

        return result.model_copy(
            update={
                "verdict": verdict,
                "explanation": explanation,
                "evidence": supporting + contradicting,
                "supporting_evidence": supporting,
                "contradicting_evidence": contradicting,
                "source_chunk_ids": ids,
            }
        )

    def parse_response('''))

# ---------------- rag_service.py ----------------
SVC.append((r'''        logger.info(f"Retrieved {len(results)} chunks " f"for claim verification.")''',
r'''        logger.info(f"Retrieved {len(results)} chunks " f"for claim verification.")

        if not results:
            return ClaimVerificationResponse(
                claim=claim,
                verdict="NOT_FOUND",
                confidence=0.0,
                explanation=(
                    "No relevant passages were retrieved from the selected "
                    "documents, so this claim could not be checked."
                ),
                evidence=[],
                supporting_evidence=[],
                contradicting_evidence=[],
                source_chunk_ids=[],
                sources=[],
            )'''))

SVC.append((r'''        logger.info("Claim verification completed: " f"{verification.verdict.value}")''',
r'''        verification = self.claim_verifier.ground_result(
            verification,
            results[: getattr(self.context_builder, "max_chunks", 5)],
            max_chars=getattr(self.context_builder, "max_chars", None),
        )

        logger.info("Claim verification completed: " f"{verification.verdict.value}")'''))

SVC.append((r'''            source_chunk_ids=(verification.source_chunk_ids),''',
r'''            source_chunk_ids=(verification.source_chunk_ids),
            supporting_evidence=verification.supporting_evidence,
            contradicting_evidence=verification.contradicting_evidence,'''))

# ---------------- schemas.py ----------------
SCH.append((r'''    confidence: float
    explanation: str
    evidence: list[str]
    source_chunk_ids: list[str]
    sources: list[Source]''', r'''    confidence: float
    explanation: str
    evidence: list[str]
    source_chunk_ids: list[str]
    sources: list[Source]
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)'''))

# ---------------- api.ts ----------------
API.append((r'''source_chunk_ids: string[];''', r'''source_chunk_ids: string[];
  supporting_evidence?: string[];
  contradicting_evidence?: string[];'''))

PLAN = [(P_CV, CV), (P_SVC, SVC), (P_SCH, SCH), (P_API, API)]


def die(msg):
    print("ABORT:", msg)
    sys.exit(1)


def conv(s, eol):
    return s.replace("\r\n", "\n").replace("\n", eol)


results = []
for path, edits in PLAN:
    if not os.path.exists(path):
        die("missing file " + path)
    if os.path.exists(path + ".bak"):
        die(path + ".bak already exists; move it first")
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
            die("%s edit %d: anchor matched %d times (need exactly 1)" % (os.path.basename(path), i, n))
        text = text.replace(a, conv(repl, eol))
    if path.endswith(".py"):
        try:
            compile(text, path, "exec")
        except SyntaxError as e:
            die("syntax error after patching %s: %s" % (path, e))
    results.append((path, text))

for path, text in results:
    shutil.copy2(path, path + ".bak")
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))
    print("patched", path, "(backup: .bak)")
print("OK")