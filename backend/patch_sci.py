import re, sys
p = "app/rag/claim_verifier.py"
raw = open(p, "rb").read().decode("utf-8")
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")
if "_normalize_sci" in s:
    sys.exit("Already patched.")

members = '''    _SUPERSCRIPTS = str.maketrans("\\u2070\\u00b9\\u00b2\\u00b3\\u2074\\u2075\\u2076\\u2077\\u2078\\u2079\\u207b\\u207a", "0123456789-+")
    _SCI = re.compile(
        r"(?:(\\d+(?:\\.\\d+)?)\\s*[x\\u00d7*]\\s*)?10\\s*\\^\\s*\\{?\\s*([-+]?\\d+)\\s*\\}?"
        r"|\\b(\\d+(?:\\.\\d+)?)[eE]([-+]?\\d+)\\b"
    )

    @staticmethod
    def _normalize_sci(text):
        value = str(text)
        value = re.sub(r"10\\s*\\u2212\\s*(\\d)", r"10^-\\1", value)
        value = re.sub(
            r"10([\\u207b\\u207a]?[\\u2070\\u00b9\\u00b2\\u00b3\\u2074-\\u2079]+)",
            lambda m: "10^" + m.group(1).translate(ClaimVerifier._SUPERSCRIPTS),
            value,
        )
        return value.replace("\\u2212", "-")

'''
anchor = "    @staticmethod\n    def _quantities(text) -> list:"
assert s.count(anchor) == 1, "anchor 1 not found"
s = s.replace(anchor, members + anchor)

old = '        value = re.sub(r"(?<=\\d),(?=\\d{3})", "", str(text))\n        found = []\n'
assert s.count(old) == 1, "anchor 2 not found"
new = '''        value = re.sub(r"(?<=\\d),(?=\\d{3})", "", str(text))
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
'''
s = s.replace(old, new)
open(p, "wb").write(s.replace("\n", nl).encode("utf-8"))
print("Patched OK")
