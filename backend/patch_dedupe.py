import sys
q = sys.argv[1]
raw = open(q, "rb").read().decode("utf-8")
nl = "\r\n" if "\r\n" in raw else "\n"
t = raw.replace("\r\n", "\n")
old = "                        key = repr(source)\n"
if "_verify_source_key" in t:
    sys.exit("rag_service.py already patched")
if t.count(old) != 1:
    sys.exit("anchor not found in rag_service.py")
helper = '''def _verify_source_key(source):
    get = source.get if isinstance(source, dict) else (lambda k, d=None: getattr(source, k, d))
    key = (get("document"), get("page"), get("chunk_id"), get("url"))
    return repr(source) if all(v is None for v in key) else repr(key)


'''
t = t.replace(old, "                        key = _verify_source_key(source)\n")
t = t.replace("def _verify_web_failed(statuses):", helper + "def _verify_web_failed(statuses):", 1)
open(q, "wb").write(t.replace("\n", nl).encode("utf-8"))
print("rag_service.py patched (source dedupe)")
