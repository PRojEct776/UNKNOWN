# verify_core: VERIFY foundation (stdlib only)

Copy the folder into `backend/` (e.g. `backend/verify_core/`). Run tests from `backend/`:
`python -m unittest verify_core.tests.test_core`  (33 tests, no network, no extra dependencies)

## Modules
| File | Purpose |
|---|---|
| evidence.py | Verdicts, modes, shared evidence schema, citation validation, `to_dict()` for JSON |
| claims.py | Instruction-aware extraction, statement kinds, categories, priority, batching |
| numeric.py | Values, units, rounding tolerance, conditions, relevance gate |
| verdict.py | Source weights, duplicate/derivative clustering, verdict rules, 4-signal confidence |
| pipeline.py | `verify_claim()` enforcing Document / External / Combined modes |

## Plugging into UNKNOWN (the only glue you write)
```python
from verify_core import verify_claim
from verify_core.evidence import Mode, DocumentEvidence, ExternalResearch, ExternalEvidence, SearchInfo

def retrieve_document(claim) -> list[DocumentEvidence]:   # wrap your BM25+FAISS retriever
    ...  # DocumentEvidence(doc_id, doc_name, passage, page=<real page or None>, chunk_id=...)

def research_external(claim) -> ExternalResearch:          # wrap Tavily + page fetch
    ...  # one ExternalEvidence per fetched page; set inspection=FULL_TEXT only if you read the page

def judge(claim, passage) -> Stance:                        # optional: LLM/NLI judge (default = lexical baseline)
    ...

result = verify_claim(text, Mode.DOCUMENT_ONLY, retrieve_document=retrieve_document)
```
`to_dict(result)` gives the JSON for your API/frontend.

## Known limits (honest)
- Default judge is lexical and cannot detect negation. Plug in an LLM/NLI judge for non-numeric claims.
- Source type is supplied by your researcher; domain prestige is deliberately not trusted.
- Confidence is ordinal. Calibrate against labelled examples before showing it as a probability.
