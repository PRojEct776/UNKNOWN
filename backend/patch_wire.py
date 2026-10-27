import sys
p = sys.argv[1]
raw = open(p, "rb").read().decode("utf-8")
nl = "\r\n" if "\r\n" in raw else "\n"
t = raw.replace("\r\n", "\n")
old = "        context = self.context_builder.build(results)\n"
new = "        context = self.context_builder.build(results, claim=claim)\n"
if new in t:
    sys.exit("already patched")
if t.count(old) != 1:
    sys.exit("anchor not found or not unique: " + str(t.count(old)))
open(p, "wb").write(t.replace(old, new).replace("\n", nl).encode("utf-8"))
print("rag_service.py patched: build(results, claim=claim)")
