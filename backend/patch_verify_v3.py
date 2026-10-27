import os
import sys

if len(sys.argv) < 3:
    sys.exit("usage: python patch_verify_v3.py <claim_verifier.py> <context_builder.py>")

cv_path, cb_path = sys.argv[1], sys.argv[2]


def load(path):
    raw = open(path, "rb").read().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n"), nl


def save(path, text, nl):
    open(path, "wb").write(text.replace("\n", nl).encode("utf-8"))


s, cv_nl = load(cv_path)
if "_evidence_quantities" not in s:
    sys.exit("Run patch_verify_v2.py first (v2 is missing).")
if "focus_text" in s:
    sys.exit("claim_verifier.py already patched (v3).")


def sub(old, new):
    global s
    assert s.count(old) == 1, "anchor not found: " + old[:70]
    s = s.replace(old, new)


# 1. new methods: focus_text (nearest-passage window) and _numeric_conflict
sub("    def _is_relevant(self, quote, claim) -> bool:\n",
    r'''    @staticmethod
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
''')

# 2. grounding uses the same claim-focused window the model was shown
sub("    def _ground_quotes(self, quotes, chunks, max_chars):\n",
    "    def _ground_quotes(self, quotes, chunks, max_chars, claim=None):\n")
sub("            if max_chars and len(text) > max_chars:\n                text = text[:max_chars]\n",
    "            text = self.focus_text(text, claim, max_chars)\n")
sub("        supporting, _ = self._ground_quotes(supporting, chunks, max_chars)\n",
    "        supporting, _ = self._ground_quotes(supporting, chunks, max_chars, result.claim)\n")
sub("        contradicting, _ = self._ground_quotes(contradicting, chunks, max_chars)\n",
    "        contradicting, _ = self._ground_quotes(contradicting, chunks, max_chars, result.claim)\n")
sub("        supporting, ids_s = self._ground_quotes(supporting, chunks, max_chars)\n",
    "        supporting, ids_s = self._ground_quotes(supporting, chunks, max_chars, result.claim)\n")
sub("        contradicting, ids_c = self._ground_quotes(contradicting, chunks, max_chars)\n",
    "        contradicting, ids_c = self._ground_quotes(contradicting, chunks, max_chars, result.claim)\n")

# 3. wrong number next to a matching number -> CONTRADICTED
sub("        explanation = result.explanation\n        if verdict == ClaimVerdict.SUPPORTED:\n",
    r'''        explanation = result.explanation
        if verdict in (ClaimVerdict.SUPPORTED, ClaimVerdict.PARTIALLY_SUPPORTED) and supporting:
            conflict = self._numeric_conflict(result.claim, supporting)
            if conflict:
                conflict_quotes, details = conflict
                verdict = ClaimVerdict.CONTRADICTED
                contradicting = contradicting + [q for q in conflict_quotes if q not in contradicting]
                supporting = [q for q in supporting if q not in conflict_quotes]
                explanation = "Number mismatch: " + "; ".join(details) + "."
        if verdict == ClaimVerdict.SUPPORTED:
''')

compile(s, cv_path, "exec")  # abort before writing if the result is not valid Python

# 4. context_builder.py: pick the passage nearest the claim
b, cb_nl = load(cb_path)
if "claim" in b and "focus_text" in b:
    print("context_builder.py already patched")
    b = None
else:
    old_sig = "    def build(self, search_results: list[dict]) -> str:\n"
    old_cut = '            if len(text) > self.max_chars:\n                text = text[: self.max_chars] + "..."\n'
    assert b.count(old_sig) == 1, "anchor not found in context_builder.py: build()"
    assert b.count(old_cut) == 1, "anchor not found in context_builder.py: truncation"
    b = b.replace(old_sig, "    def build(self, search_results: list[dict], claim=None) -> str:\n")
    b = b.replace(
        old_cut,
        '            if len(text) > self.max_chars:\n'
        '                if claim:\n'
        '                    from app.rag.claim_verifier import ClaimVerifier\n'
        '\n'
        '                    text = ClaimVerifier.focus_text(text, claim, self.max_chars) + "..."\n'
        '                else:\n'
        '                    text = text[: self.max_chars] + "..."\n',
    )
    compile(b, cb_path, "exec")

# 5. tests
TESTS = r'''import pytest

from app.rag.claim_verifier import ClaimVerdict, ClaimVerificationResult, ClaimVerifier

KEY = "A single copy gives 0.767 after 3,000 generations."


def _chunk():
    prefix = ("filler words here. " * 80)[:1432]
    body = prefix + KEY
    body = body + (" filler words here." * 40)[: 2100 - len(body)]
    return {"chunk_id": "chunk_34", "text": body}


def _result(claim, verdict, quote):
    return ClaimVerificationResult(
        claim=claim,
        verdict=verdict,
        confidence=0.9,
        explanation="model explanation",
        supporting_evidence=[quote],
    )


def test_wrong_number_is_contradicted():
    claim = "A single copy gives 0.777 after 3,000 generations."
    result = _result(claim, ClaimVerdict.SUPPORTED, "A single copy gives 0.767 after 3,000 generations")
    out = ClaimVerifier().ground_result(result, [_chunk()], max_chars=1200)
    assert out.verdict == ClaimVerdict.CONTRADICTED
    assert out.contradicting_evidence
    assert "0.777" in out.explanation and "0.767" in out.explanation


def test_partially_with_wrong_number_is_contradicted():
    claim = "A single copy gives 0.777 after 3,000 generations."
    result = _result(claim, ClaimVerdict.PARTIALLY_SUPPORTED, "A single copy gives 0.767 after 3,000 generations")
    out = ClaimVerifier().ground_result(result, [_chunk()], max_chars=1200)
    assert out.verdict == ClaimVerdict.CONTRADICTED


def test_correct_number_stays_supported():
    claim = "A single copy gives 0.767 after 3,000 generations."
    result = _result(claim, ClaimVerdict.SUPPORTED, "A single copy gives 0.767 after 3,000 generations")
    out = ClaimVerifier().ground_result(result, [_chunk()], max_chars=1200)
    assert out.verdict == ClaimVerdict.SUPPORTED
    assert out.source_chunk_ids == ["chunk_34"]


def test_focus_text_finds_sentence_past_the_old_cut():
    chunk = _chunk()
    assert len(chunk["text"]) > 2000
    assert chunk["text"].index("0.767") > 1200
    window = ClaimVerifier.focus_text(chunk["text"], "single copy 0.767 after 3,000 generations", 1200)
    assert len(window) <= 1200
    assert KEY in window


def test_focus_text_without_claim_keeps_start():
    chunk = _chunk()
    assert ClaimVerifier.focus_text(chunk["text"], "", 1200) == chunk["text"][:1200]


def test_context_builder_shows_window_near_claim():
    module = pytest.importorskip("app.rag.context_builder")
    context = module.ContextBuilder(max_chars=1200).build(
        [dict(_chunk(), rank=1, document="paper.pdf", page=3)],
        claim="A single copy gives 0.777 after 3,000 generations.",
    )
    assert "0.767 after 3,000" in context
'''
os.makedirs("tests", exist_ok=True)
open(os.path.join("tests", "test_claim_verifier_v3.py"), "w", encoding="utf-8", newline="\n").write(TESTS)

save(cv_path, s, cv_nl)
if b is not None:
    save(cb_path, b, cb_nl)
print("claim_verifier.py patched (v3)")
print("context_builder.py patched" if b is not None else "context_builder.py unchanged")
print("tests/test_claim_verifier_v3.py written")
