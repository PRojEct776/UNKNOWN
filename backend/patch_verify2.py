"""Guarded patch: Verify v2 (verdicts, relevance, units). All-or-nothing."""
import os
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
P_CV = os.path.join(BASE, "app", "rag", "claim_verifier.py")
CV = []

# 1. enum
CV.append((r'''    NOT_FOUND = "NOT_FOUND"''', r'''    NOT_FOUND = "NOT_FOUND"  # legacy: nothing retrieved / quotes not grounded
    UNSUPPORTED = "UNSUPPORTED"
    UNVERIFIABLE = "UNVERIFIABLE"'''))

# 2. prompt label list
CV.append((r'''SUPPORTED
PARTIALLY_SUPPORTED
CONTRADICTED
NOT_FOUND

Definitions:''', r'''SUPPORTED
PARTIALLY_SUPPORTED
CONTRADICTED
UNSUPPORTED
UNVERIFIABLE

Definitions:'''))

# 3. prompt definitions
CV.append((r'''NOT_FOUND:
The supplied evidence does not provide enough information
to support or contradict the claim.''', r'''UNSUPPORTED:
The claim is evaluable, but the supplied evidence does not establish it
and does not adequately contradict it. Missing evidence is NOT a
contradiction.

UNVERIFIABLE:
The claim cannot be reliably assessed with the supplied evidence. State the
specific limitation in the explanation.'''))

# 4. helpers
CV.append((r'''    def _ground_quotes(self, quotes, chunks, max_chars):''', r'''    _UNITS = {
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

    @staticmethod
    def _quantities(text) -> list:
        """Return [(label, (value, dimension))]; percents are stored as fractions."""

        value = re.sub(r"(?<=\d),(?=\d{3})", "", str(text))
        found = []
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
        available = [q for _, q in self._quantities(evidence_text)]
        missing = []
        for label, quantity in self._quantities(claim):
            matched = any(self._qty_match(quantity, item) for item in available)
            if not matched and label not in missing:
                missing.append(label)
        return missing

    def _is_relevant(self, quote, claim) -> bool:
        """Heuristic: a quote must share a content word or a number with the claim."""

        claim_words = self._content_words(claim)
        if claim_words & self._content_words(quote):
            return True
        claim_quantities = self._quantities(claim)
        quote_quantities = [q for _, q in self._quantities(quote)]
        for _, quantity in claim_quantities:
            if any(self._qty_match(quantity, item) for item in quote_quantities):
                return True
        return not claim_words and not claim_quantities

    def _ground_quotes(self, quotes, chunks, max_chars):'''))

# 5. grounding + relevance
CV.append((r'''        supporting, ids_s = self._ground_quotes(supporting, chunks, max_chars)
        contradicting, ids_c = self._ground_quotes(contradicting, chunks, max_chars)
        ids = ids_s + [item for item in ids_c if item not in ids_s]''',
r'''        supporting, _ = self._ground_quotes(supporting, chunks, max_chars)
        contradicting, _ = self._ground_quotes(contradicting, chunks, max_chars)
        grounded_count = len(supporting) + len(contradicting)
        supporting = [q for q in supporting if self._is_relevant(q, result.claim)]
        contradicting = [q for q in contradicting if self._is_relevant(q, result.claim)]
        irrelevant_removed = len(supporting) + len(contradicting) < grounded_count
        supporting, ids_s = self._ground_quotes(supporting, chunks, max_chars)
        contradicting, ids_c = self._ground_quotes(contradicting, chunks, max_chars)
        ids = ids_s + [item for item in ids_c if item not in ids_s]'''))

# 6. ungrounded branch
CV.append((r'''        if ungrounded:
            return result.model_copy(
                update={
                    "verdict": ClaimVerdict.NOT_FOUND,
                    "confidence": 0.0,
                    "explanation": (
                        "The model's verdict could not be confirmed: none of its "
                        "quoted evidence appears in the retrieved passages."
                    ),''', r'''        if ungrounded:
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
                    "explanation": new_explanation,'''))

# 7. unit-aware numbers
CV.append((r'''            evidence_numbers = set(self._numbers(" ".join(supporting)))
            missing = []
            for number in self._numbers(result.claim):
                if number not in evidence_numbers and number not in missing:
                    missing.append(number)
            if missing:''', r'''            missing = self._missing_quantities(result.claim, " ".join(supporting))
            if missing:'''))

PLAN = [(P_CV, CV)]


def die(msg):
    print("ABORT:", msg)
    sys.exit(1)


def conv(s, eol):
    return s.replace("\r\n", "\n").replace("\n", eol)


results = []
for path, edits in PLAN:
    if not os.path.exists(path):
        die("missing file " + path)
    if os.path.exists(path + ".bak2"):
        die(path + ".bak2 already exists; move it first")
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
    shutil.copy2(path, path + ".bak2")
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))
    print("patched", path, "(backup: .bak2)")
print("OK")