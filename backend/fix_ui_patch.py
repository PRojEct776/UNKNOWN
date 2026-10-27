import os
import sys

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patch_verify_ui.py")
raw = open(path, "rb").read().decode("utf-8")
eol = "\r\n" if "\r\n" in raw else "\n"
text = raw.replace("\r\n", "\n")

old = (
    "API.append((r'''  contradicting_evidence?: string[];''', "
    "r'''  contradicting_evidence?: string[];\n"
)
new = (
    "API.append((r'''  source_chunk_ids: string[];\n"
    "  supporting_evidence?: string[];\n"
    "  contradicting_evidence?: string[];''', "
    "r'''  source_chunk_ids: string[];\n"
    "  supporting_evidence?: string[];\n"
    "  contradicting_evidence?: string[];\n"
)

if text.count(old) != 1:
    print("ABORT: expected 1 match, found", text.count(old))
    sys.exit(1)

text = text.replace(old, new).replace("\n", eol)
open(path, "wb").write(text.encode("utf-8"))
print("OK fixed", path)