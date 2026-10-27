import sys
p = sys.argv[1] if len(sys.argv) > 1 else "app/rag/claim_verifier.py"
raw = open(p, "rb").read().decode("utf-8")
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")
if "_normalize_sci" not in s:
    sys.exit("Run patch_sci.py first (the exponent patch is missing).")
if "_evidence_quantities" in s:
    sys.exit("claim_verifier.py already patched (v2).")

def sub(old, new):
    global s
    assert s.count(old) == 1, "anchor not found: " + old[:60]
    s = s.replace(old, new)

# 1. evidence-side handling of PDF-flattened exponents ("10-6" meaning 10^-6)
sub("    @staticmethod\n    def _quantities(text) -> list:",
'''    _FLAT_EXP = re.compile(r"(?<![\\d.])10\\s*[-\\u2212\\u2013](\\d{1,2})(?!\\d)")

    @staticmethod
    def _evidence_quantities(text):
        """Quantities in evidence text. PDF extraction often flattens 10^-6 to
        '10-6', so that form is also offered as 1e-6 (the plain numbers are kept)."""

        quantities = [q for _, q in ClaimVerifier._quantities(text)]
        for match in ClaimVerifier._FLAT_EXP.finditer(str(text)):
            quantities.append((float("1e-" + match.group(1)), ""))
        return quantities

    @staticmethod
    def _quantities(text) -> list:''')
sub("        available = [q for _, q in self._quantities(evidence_text)]",
    "        available = self._evidence_quantities(evidence_text)")
sub("        quote_quantities = [q for _, q in self._quantities(quote)]",
    "        quote_quantities = self._evidence_quantities(quote)")

# 2. drop atomic parts that are redundant subsets of another part
sub("        valid = []\n        seen = set()\n        covered_words = set()\n        covered_quantities = []\n",
    "        valid = []\n        part_words = []\n        part_quants = []\n        seen = set()\n        covered_words = set()\n        covered_quantities = []\n")
sub("            valid.append(text)\n            covered_words |= words\n",
    "            valid.append(text)\n            part_words.append(words)\n            part_quants.append(quantities)\n            covered_words |= words\n")
sub("        if len(valid) < 2 or len(valid) > max_parts:\n            return fallback\n",
'''        keep = []
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
''')
# 3. quote grounding: treat 10^-6, 10^{-6}, 10-superscript and 10-6 as the same text
sub('        return re.sub(r"\\s+", " ", value).strip()\n',
    '        value = ClaimVerifier._normalize_sci(value)\n'
    '        value = re.sub(r"10\\s*\\^\\s*\\{?\\s*-\\s*(\\d{1,2})(?:\\s*\\})?", r"10-\\1", value)\n'
    '        return re.sub(r"\\s+", " ", value).strip()\n')
open(p, "wb").write(s.replace("\n", nl).encode("utf-8"))
print("claim_verifier.py patched (v2)")

# 3. optional: dedupe merged sources in rag_service.py
if len(sys.argv) > 2:
    q = sys.argv[2]
    raw = open(q, "rb").read().decode("utf-8"); nl = "\r\n" if "\r\n" in raw else "\n"
    t = raw.replace("\r\n", "\n")
    old = "                        key = repr(source)\n"
    if "_verify_source_key" in t:
        print("rag_service.py already patched")
    elif t.count(old) != 1:
        print("rag_service.py: anchor not found, skipped")
    else:
        helper = '''def _verify_source_key(source):
    get = source.get if isinstance(source, dict) else (lambda k, d=None: getattr(source, k, d))
    key = (get("document"), get("page"), get("chunk_id"), get("url"))
    return repr(source) if all(v is None for v in key) else repr(key)


'''
        t = t.replace(old, "                        key = _verify_source_key(source)\n")
        t = t.replace("def _verify_web_failed(statuses):", helper + "def _verify_web_failed(statuses):", 1)
        open(q, "wb").write(t.replace("\n", nl).encode("utf-8"))
        print("rag_service.py patched (source dedupe)")
