import sys

def load(path):
    raw = open(path, "rb").read()
    crlf = b"\r\n" in raw
    return raw.decode("utf-8").replace("\r\n", "\n"), crlf

def save(path, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    open(path, "wb").write(text.encode("utf-8"))

def patch(path, old, new, marker):
    text, crlf = load(path)
    if marker in text:
        sys.exit(f"ABORT: {path} already patched.")
    n = text.count(old)
    if n != 1:
        sys.exit(f"ABORT: {path} anchor matched {n} times, expected 1.")
    return text.replace(old, new, 1), crlf

S_PATH = r"app\api\schemas.py"
S_OLD = (
    "    confidence: Confidence | None = None\n\n\n"
    "class ClaimVerificationRequest(BaseModel):"
)
S_NEW = (
    "    confidence: Confidence | None = None\n"
    "    conflicts: list[dict] = Field(default_factory=list)\n"
    "    source_reliability: list[dict] = Field(default_factory=list)\n\n\n"
    "class ClaimVerificationRequest(BaseModel):"
)

R_PATH = r"app\services\rag_service.py"
R_OLD = (
    '        logger.info("Grounded pipeline completed with %d verified sentences, %d claims.", len(verified_sentences), len(claims))\n'
    "\n"
    "        return QueryResponse(\n"
    "            query=normalized_query,\n"
    "            query_type=query_type.value,\n"
    "            answer=answer,\n"
    "            sources=sources,\n"
    "            claims=claims,\n"
    "        )\n"
)
R_NEW = (
    '        logger.info("Grounded pipeline completed with %d verified sentences, %d claims.", len(verified_sentences), len(claims))\n'
    "\n"
    "        conflicts_out: list[dict] = []\n"
    "        reliability_out: list[dict] = []\n"
    "        try:\n"
    "            from app.rag.reliability import compute_reliability, detect_conflicts\n"
    "\n"
    "            for _s in results:\n"
    "                _get = _s.get if isinstance(_s, dict) else (lambda k, d=None, _o=_s: getattr(_o, k, d))\n"
    "                reliability_out.append({\n"
    '                    "source": str(_get("document") or _get("chunk_id") or _get("id") or ""),\n'
    '                    "reliability": round(float(compute_reliability(_s)), 4),\n'
    "                })\n"
    "            _claim_dicts = [\n"
    '                {"text": c.text, "source_ids": list(c.source_ids or [])}\n'
    "                for c in claims[:8]\n"
    "            ]\n"
    "            for _cf in detect_conflicts(_claim_dicts):\n"
    '                conflicts_out.append(_cf.model_dump() if hasattr(_cf, "model_dump") else dict(_cf))\n'
    "        except Exception as exc:  # noqa: BLE001\n"
    '            logger.warning("Reliability/conflict analysis failed (%s); continuing without it.", exc)\n'
    "\n"
    "        return QueryResponse(\n"
    "            query=normalized_query,\n"
    "            query_type=query_type.value,\n"
    "            answer=answer,\n"
    "            sources=sources,\n"
    "            claims=claims,\n"
    "            conflicts=conflicts_out,\n"
    "            source_reliability=reliability_out,\n"
    "        )\n"
)

s_text, s_crlf = patch(S_PATH, S_OLD, S_NEW, "source_reliability")
r_text, r_crlf = patch(R_PATH, R_OLD, R_NEW, "conflicts_out")
save(S_PATH, s_text, s_crlf)
save(R_PATH, r_text, r_crlf)
print("PATCHED OK")
