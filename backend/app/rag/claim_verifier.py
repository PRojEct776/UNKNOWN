"""
UNKNOWN X - Claim Verification

Verifies user-provided claims against retrieved document evidence.
"""

import json
import math
import re
from enum import Enum

from pydantic import BaseModel, Field


class ClaimVerdict(str, Enum):
    """Possible verification outcomes."""

    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NOT_FOUND = "NOT_FOUND"  # legacy: nothing retrieved / quotes not grounded
    UNSUPPORTED = "UNSUPPORTED"
    UNVERIFIABLE = "UNVERIFIABLE"


class ClaimVerificationResult(BaseModel):
    """Structured result of claim verification."""

    claim: str = Field(..., min_length=1)
    verdict: ClaimVerdict
    confidence: float = Field(..., ge=0.0, le=1.0)
    explanation: str
    evidence: list[str] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)


class ClaimVerifier:
    """Analyze a claim against retrieved document evidence."""

    def build_verification_prompt(
        self,
        claim: str,
        context: str,
    ) -> str:
        """Build a grounded claim-verification prompt."""

        return f"""
You are the claim verification component of UNKNOWN.

Your task is to evaluate the CLAIM using ONLY the supplied
DOCUMENT EVIDENCE.

Do not use outside knowledge.
Do not assume missing information.
Do not invent evidence.
Do not invent citations.
Every item in supporting_evidence and contradicting_evidence MUST be an exact,
verbatim quote copied from the DOCUMENT EVIDENCE. Do not paraphrase. You may
join two parts of one passage with "...".
Put quotes that support the claim in supporting_evidence and quotes that
conflict with it in contradicting_evidence.
If the claim contains numbers or units, they must match the evidence exactly;
otherwise use PARTIALLY_SUPPORTED or CONTRADICTED.
For source_chunk_ids use only the Chunk ID values shown in the evidence.

CLAIM:
{claim}

DOCUMENT EVIDENCE:
{context}

Classify the claim into exactly one of:

SUPPORTED
PARTIALLY_SUPPORTED
CONTRADICTED
UNSUPPORTED
UNVERIFIABLE

Definitions:

SUPPORTED:
The evidence directly supports the claim.

PARTIALLY_SUPPORTED:
The evidence supports only part of the claim or provides
qualified/incomplete support.

CONTRADICTED:
The evidence directly conflicts with the claim.

UNSUPPORTED:
The claim is evaluable, but the supplied evidence does not establish it
and does not adequately contradict it. Missing evidence is NOT a
contradiction.

UNVERIFIABLE:
The claim cannot be reliably assessed with the supplied evidence. State the
specific limitation in the explanation.

Return ONLY valid JSON in this exact structure:

{{
  "verdict": "SUPPORTED",
  "confidence": 0.0,
  "explanation": "Brief explanation based only on the evidence.",
  "supporting_evidence": [
    "Exact quote from the evidence that supports the claim"
  ],
  "contradicting_evidence": [
    "Exact quote from the evidence that conflicts with the claim"
  ],
  "source_chunk_ids": [
    "chunk_id"
  ]
}}

Confidence must be a number between 0 and 1.
""".strip()

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract JSON from a model response."""

        cleaned = text.strip()

        # Direct JSON response.
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Handle markdown JSON fences.
        fenced = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            cleaned,
            flags=re.DOTALL,
        )

        if fenced:
            try:
                return json.loads(fenced.group(1))
            except json.JSONDecodeError:
                pass

        # Last attempt: locate the outermost JSON object.
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError("Provider returned invalid verification JSON.")

    @staticmethod
    def _validate_result(
        claim: str,
        data: dict,
    ) -> ClaimVerificationResult:
        """Validate and normalize model output."""

        verdict = str(data.get("verdict", "")).upper().strip()

        try:
            parsed_verdict = ClaimVerdict(verdict)
        except ValueError as error:
            raise ValueError(
                f"Invalid claim verification verdict: {verdict}"
            ) from error

        confidence = ClaimVerifier._safe_confidence(data.get("confidence", 0.0))

        explanation = str(
            data.get(
                "explanation",
                "No explanation was provided.",
            )
        ).strip()

        supporting = ClaimVerifier._as_str_list(data.get("supporting_evidence"))
        contradicting = ClaimVerifier._as_str_list(data.get("contradicting_evidence"))
        legacy = ClaimVerifier._as_str_list(data.get("evidence"))
        if legacy and not supporting and not contradicting:
            supporting, contradicting = ClaimVerifier._split_legacy(parsed_verdict, legacy)

        source_chunk_ids = data.get("source_chunk_ids", [])
        if not isinstance(source_chunk_ids, list):
            source_chunk_ids = [str(source_chunk_ids)]

        return ClaimVerificationResult(
            claim=claim,
            verdict=parsed_verdict,
            confidence=confidence,
            explanation=explanation,
            evidence=supporting + contradicting,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            source_chunk_ids=[str(item) for item in source_chunk_ids],
        )

    @staticmethod
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
        value = ClaimVerifier._normalize_sci(value)
        value = re.sub(r"10\s*\^\s*\{?\s*-\s*(\d{1,2})(?:\s*\})?", r"10-\1", value)
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

    _UNITS = {
        "ns": ("t", 1e-9), "us": ("t", 1e-6), "\u03bcs": ("t", 1e-6),
        "\u00b5s": ("t", 1e-6), "ms": ("t", 1e-3), "s": ("t", 1.0),
        "sec": ("t", 1.0), "secs": ("t", 1.0), "second": ("t", 1.0),
        "seconds": ("t", 1.0), "min": ("t", 60.0), "mins": ("t", 60.0),
        "minute": ("t", 60.0), "minutes": ("t", 60.0), "h": ("t", 3600.0),
        "hr": ("t", 3600.0), "hrs": ("t", 3600.0), "hour": ("t", 3600.0),
        "hours": ("t", 3600.0),
        "kb": ("d", 1e3), "mb": ("d", 1e6), "gb": ("d", 1e9), "tb": ("d", 1e12),
        "mm": ("l", 1e-3), "cm": ("l", 1e-2), "m": ("l", 1.0), "km": ("l", 1e3),
        "mg": ("w", 1e-6), "g": ("w", 1e-3), "kg": ("w", 1.0),
    }

    _STOP = frozenset(
        "the and for are was were with that this from has have had its their "
        "which been but not than then into over under about also can may will "
        "would should could our per using used use uses such these those they "
        "them there here what when where who whom whose while within without "
        "more most less very each both any all some only just".split()
    )

    @staticmethod
    def _content_words(text) -> set:
        words = re.findall(r"[a-z][a-z0-9\-]{2,}", ClaimVerifier._norm(text))
        return {word for word in words if word not in ClaimVerifier._STOP}

    _SUPERSCRIPTS = str.maketrans("\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079\u207b\u207a", "0123456789-+")
    _SCI = re.compile(
        r"(?:(\d+(?:\.\d+)?)\s*[x\u00d7*]\s*)?10\s*\^\s*\{?\s*([-+]?\d+)\s*\}?"
        r"|\b(\d+(?:\.\d+)?)[eE]([-+]?\d+)\b"
    )

    @staticmethod
    def _normalize_sci(text):
        value = str(text)
        value = re.sub(r"10\s*\u2212\s*(\d)", r"10^-\1", value)
        value = re.sub(
            r"10([\u207b\u207a]?[\u2070\u00b9\u00b2\u00b3\u2074-\u2079]+)",
            lambda m: "10^" + m.group(1).translate(ClaimVerifier._SUPERSCRIPTS),
            value,
        )
        return value.replace("\u2212", "-")

    _FLAT_EXP = re.compile(r"(?<![\d.])10\s*[-\u2212\u2013](\d{1,2})(?!\d)")

    @staticmethod
    def _evidence_quantities(text):
        """Quantities in evidence text. PDF extraction often flattens 10^-6 to
        '10-6', so that form is also offered as 1e-6 (the plain numbers are kept)."""

        quantities = [q for _, q in ClaimVerifier._quantities(text)]
        for match in ClaimVerifier._FLAT_EXP.finditer(str(text)):
            quantities.append((float("1e-" + match.group(1)), ""))
        return quantities

    @staticmethod
    def _quantities(text) -> list:
        """Return [(label, (value, dimension))]; percents are stored as fractions."""

        value = re.sub(r"(?<=\d),(?=\d{3})", "", str(text))
        value = ClaimVerifier._normalize_sci(value)
        found = []

        def _sci(m):
            if m.group(2) is not None:
                mant, exp, label = (m.group(1) or "1"), m.group(2), m.group(0).strip()
            else:
                mant, exp, label = m.group(3), m.group(4), m.group(0)
            found.append((label, (float(f"{mant}e{exp}"), "")))
            return " "

        value = ClaimVerifier._SCI.sub(_sci, value)
        pattern = r"(\d+(?:\.\d+)?)\s*(%|percent\b|[a-zA-Z\u03bc\u00b5]+)?"
        for match in re.finditer(pattern, value):
            number = float(match.group(1))
            raw = (match.group(2) or "").lower()
            label = match.group(1)
            if raw in ("%", "percent"):
                found.append((label + "%", (number / 100.0, "%")))
            elif raw in ClaimVerifier._UNITS:
                dim, factor = ClaimVerifier._UNITS[raw]
                found.append((label + " " + raw, (number * factor, dim)))
            else:
                found.append((label, (number, "")))
        return found

    @staticmethod
    def _qty_match(a, b) -> bool:
        (av, ad), (bv, bd) = a, b

        def close(x, y):
            return math.isclose(x, y, rel_tol=1e-6, abs_tol=1e-9)

        if ad == bd:
            return close(av, bv)
        if {ad, bd} == {"%", ""}:
            fraction, bare = (av, bv) if ad == "%" else (bv, av)
            return close(fraction, bare) or close(fraction * 100.0, bare)
        return False

    def _missing_quantities(self, claim, evidence_text) -> list:
        available = self._evidence_quantities(evidence_text)
        missing = []
        for label, quantity in self._quantities(claim):
            matched = any(self._qty_match(quantity, item) for item in available)
            if not matched and label not in missing:
                missing.append(label)
        return missing

    @staticmethod
    def focus_text(text, claim, max_chars):
        """At most max_chars of text, using the window that best matches the claim."""

        text = str(text or "").strip()
        if not max_chars or len(text) <= max_chars:
            return text
        words = ClaimVerifier._content_words(claim) if claim else set()
        numbers = set(ClaimVerifier._numbers(claim)) if claim else set()
        if not words and not numbers:
            return text[:max_chars]
        last = len(text) - max_chars
        step = max(50, max_chars // 12)
        starts = list(range(0, last + 1, step))
        if starts[-1] != last:
            starts.append(last)
        scored = []
        for start in starts:
            window = text[start:start + max_chars].lower()
            plain = re.sub(r"(?<=\d),(?=\d{3})", "", window)
            score = sum(1 for word in words if word in window)
            score += 2 * sum(1 for number in numbers if number in plain)
            scored.append((score, start))
        best = max(score for score, _ in scored)
        ties = [start for score, start in scored if score == best]
        start = ties[len(ties) // 2]
        return text[start:start + max_chars]

    def _numeric_conflict(self, claim, supporting):
        """Quotes that give a different number for the same statement as the claim.

        A conflict needs: a claim number missing from the evidence, another claim
        number that DOES match in the same clause (the anchor), and a different
        number of the same kind in that clause. Returns (quotes, details) or None."""

        claim_quantities = self._quantities(claim)
        if len(claim_quantities) < 2:
            return None
        available = self._evidence_quantities(" ".join(supporting))
        missing = [
            (label, q)
            for label, q in claim_quantities
            if not any(self._qty_match(q, item) for item in available)
        ]
        if not missing:
            return None
        quotes = []
        details = []
        for quote in supporting:
            for clause in re.split(r"(?<=[.;])\s+", str(quote)):
                clause_quantities = self._quantities(clause)
                anchored = any(
                    self._qty_match(q, c)
                    for _, q in claim_quantities
                    for _, c in clause_quantities
                )
                if not anchored:
                    continue
                for m_label, (m_value, m_dim) in missing:
                    if m_dim == "" and float(m_value).is_integer():
                        continue
                    for c_label, (c_value, c_dim) in clause_quantities:
                        if c_dim != m_dim:
                            continue
                        if any(self._qty_match((c_value, c_dim), q) for _, q in claim_quantities):
                            continue
                        if m_dim == "" and float(c_value).is_integer():
                            continue
                        if quote not in quotes:
                            quotes.append(quote)
                        detail = f"the claim says {m_label} but the document says {c_label}"
                        if detail not in details:
                            details.append(detail)
                        break
        return (quotes, details) if quotes else None

    def _is_relevant(self, quote, claim) -> bool:
        """Heuristic: a quote must share a content word or a number with the claim."""

        claim_words = self._content_words(claim)
        if claim_words & self._content_words(quote):
            return True
        claim_quantities = self._quantities(claim)
        quote_quantities = self._evidence_quantities(quote)
        for _, quantity in claim_quantities:
            if any(self._qty_match(quantity, item) for item in quote_quantities):
                return True
        return not claim_words and not claim_quantities

    def _ground_quotes(self, quotes, chunks, max_chars, claim=None):
        """Keep only quotes found in one visible chunk; return (kept, chunk_ids)."""

        texts = []
        for chunk in chunks:
            text = str(chunk.get("text", "") or "").strip()
            text = self.focus_text(text, claim, max_chars)
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

        supporting, _ = self._ground_quotes(supporting, chunks, max_chars, result.claim)
        contradicting, _ = self._ground_quotes(contradicting, chunks, max_chars, result.claim)
        grounded_count = len(supporting) + len(contradicting)
        supporting = [q for q in supporting if self._is_relevant(q, result.claim)]
        contradicting = [q for q in contradicting if self._is_relevant(q, result.claim)]
        irrelevant_removed = len(supporting) + len(contradicting) < grounded_count
        supporting, ids_s = self._ground_quotes(supporting, chunks, max_chars, result.claim)
        contradicting, ids_c = self._ground_quotes(contradicting, chunks, max_chars, result.claim)
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
            if irrelevant_removed:
                new_verdict = ClaimVerdict.UNSUPPORTED
                new_explanation = (
                    "The quoted passages do not address the claim, so the "
                    "retrieved evidence does not establish it."
                )
            else:
                new_verdict = ClaimVerdict.NOT_FOUND
                new_explanation = (
                    "The model's verdict could not be confirmed: none of its "
                    "quoted evidence appears in the retrieved passages."
                )
            return result.model_copy(
                update={
                    "verdict": new_verdict,
                    "confidence": 0.0,
                    "explanation": new_explanation,
                    "evidence": [],
                    "supporting_evidence": [],
                    "contradicting_evidence": [],
                    "source_chunk_ids": [],
                }
            )

        explanation = result.explanation
        if verdict in (ClaimVerdict.SUPPORTED, ClaimVerdict.PARTIALLY_SUPPORTED) and supporting:
            conflict = self._numeric_conflict(result.claim, supporting)
            if conflict:
                conflict_quotes, details = conflict
                verdict = ClaimVerdict.CONTRADICTED
                contradicting = contradicting + [q for q in conflict_quotes if q not in contradicting]
                supporting = [q for q in supporting if q not in conflict_quotes]
                explanation = "Number mismatch: " + "; ".join(details) + "."
        if verdict == ClaimVerdict.SUPPORTED:
            missing = self._missing_quantities(result.claim, " ".join(supporting))
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

    @staticmethod
    def select_atomic_claims(original, parts, max_parts=5) -> list[str]:
        """Validate model-proposed atomic claims; fall back to [original] when unsafe."""

        fallback = [original]
        if not isinstance(parts, list):
            return fallback

        original_words = ClaimVerifier._content_words(original)
        original_quantities = [q for _, q in ClaimVerifier._quantities(original)]

        valid = []
        part_words = []
        part_quants = []
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
            part_words.append(words)
            part_quants.append(quantities)
            covered_words |= words
            covered_quantities.extend(quantities)

        keep = []
        for i, words_i in enumerate(part_words):
            redundant = any(
                j != i
                and words_i <= part_words[j]
                and all(
                    any(ClaimVerifier._qty_match(q, o) for o in part_quants[j])
                    for q in part_quants[i]
                )
                and (words_i != part_words[j] or j < i)
                for j in range(len(valid))
            )
            if not redundant:
                keep.append(i)
        valid = [valid[i] for i in keep]

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

    def parse_response(
        self,
        claim: str,
        response_text: str,
    ) -> ClaimVerificationResult:
        """Parse and validate an LLM verification response."""

        data = self._extract_json(response_text)

        return self._validate_result(
            claim=claim,
            data=data,
        )