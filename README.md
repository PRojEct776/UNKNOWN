# UNKNOWN

> **Discover concepts you can't name.**  
> Describe what a tool or machine does, how it operates, or where it's used.  
> UNKNOWN bridges the lexical gap using dense vector semantics and knowledge-graph verification.

---

## Table of Contents

- [Quick Start (Docker)](#quick-start-docker)
- [Local Development](#local-development)
- [Running Tests](#running-tests)
- [Evaluation](#evaluation)
- [Environment Variables](#environment-variables)
- [spaCy Model](#spacy-model)
- [Architecture Overview](#architecture-overview)

---

## Quick Start (Docker)

**Prerequisites:** Docker 24+ and Docker Compose v2.

```bash
# 1. Clone the repo
git clone <repo-url>
cd UNKNOWN-clean

# 2. Create your .env (only GEMINI_API_KEY is strictly required)
cp .env.example .env
# Open .env and set GEMINI_API_KEY=<your key>

# 3. Start the app
docker compose up
```

The API and frontend are served on **http://localhost:8000**.  
First run downloads spaCy and HuggingFace models (~1 GB); subsequent starts use the Docker layer cache.

To rebuild the image after code changes:

```bash
docker compose up --build
```

---

## Local Development

### Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install the spaCy model (optional but recommended)
python -m spacy download en_core_web_sm

# Copy env and fill in GEMINI_API_KEY
cp ../.env.example .env

# Start the development server (hot-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start the Vite dev server
npm run dev
```

The dev server proxies API calls to http://localhost:8000.  
Open http://localhost:5173 in your browser.

### Production build (frontend only)

```bash
cd frontend
npm run build
# Built SPA is in frontend/dist/ and served by the backend at /
```

---

## Running Tests

All tests live in `backend/tests/`. Slow tests (live model downloads / network calls) are excluded by default.

```bash
cd backend
pytest -q -m "not slow" --timeout=120
```

Expected output ends with all tests passing. CI runs the exact same command.

---

## Evaluation

```bash
# Retrieval evaluation
cd backend
python scripts/eval_retrieval.py

# Full pipeline eval (if eval/ suite is present)
python eval/run_eval.py
```

---

## Environment Variables

Copy `.env.example` to `.env` in the **project root** (Docker reads it there) **and** in `backend/` (local dev reads it there).

| Variable | Default | Required | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | — | **Yes** | Google Gemini API key (also accepted as `GOOGLE_API_KEY`) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | No | Gemini model name |
| `MODEL_NAME` | `gemini-2.5-flash` | No | Alias for `GEMINI_MODEL` |
| `GEMINI_TIMEOUT_MS` | `120000` | No | LLM call timeout in milliseconds |
| `GEMINI_THINKING_LEVEL` | `LOW` | No | Thinking budget: `LOW`, `MEDIUM`, `HIGH` |
| `TEMPERATURE` | `0.2` | No | Generation temperature |
| `MAX_OUTPUT_TOKENS` | `8192` | No | Max tokens per LLM response |
| `LLM_PROVIDER_ORDER` | `gemini,groq,cohere,openrouter,cloudflare` | No | Fallback chain |
| `LLM_TIMEOUT_S` | `10.0` | No | Per-provider timeout (seconds) |
| `GROQ_API_KEY` | _(empty)_ | No | Groq fallback key |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | No | |
| `COHERE_API_KEY` | _(empty)_ | No | Cohere fallback key |
| `COHERE_MODEL` | `command-a-03-2025` | No | |
| `OPENROUTER_API_KEY` | _(empty)_ | No | OpenRouter fallback key |
| `OPENROUTER_MODEL` | `openrouter/free` | No | |
| `CLOUDFLARE_ACCOUNT_ID` | _(empty)_ | No | Cloudflare Workers AI |
| `CLOUDFLARE_API_TOKEN` | _(empty)_ | No | |
| `CLOUDFLARE_MODEL` | `@cf/meta/llama-3.1-8b-instruct-fp8` | No | |
| `CORS_ORIGINS` | `http://localhost:8000,...` | No | Comma-separated allowed origins |
| `VITE_BACKEND_URL` | `http://localhost:8000` | No | Frontend API base URL |
| `MAX_COLLECTION_PAPERS` | `25` | No | Max documents per collection |
| `MAX_FILE_SIZE_BYTES` | `52428800` | No | Upload size limit (50 MB) |
| `FRONTEND_DIST_DIR` | `../frontend/dist` | No | Path to built SPA (relative to backend/) |
| `NLI_MODEL` | `cross-encoder/nli-deberta-v3-small` | No | HuggingFace NLI model for claim verification |
| `SPACY_MODEL` | `en_core_web_sm` | No | spaCy model for NER / sentence splitting |
| `DECOMPOSE_MAX_SUBQS` | `5` | No | Query decomposition: max sub-queries |
| `DECOMPOSE_TOP_K` | `10` | No | Retrieval top-k per sub-query |
| `DECOMPOSE_MIN_PAPERS` | `2` | No | Minimum papers required |
| `DECOMPOSE_TAU_R` | `0.50` | No | Relevance threshold |
| `DECOMPOSE_MAX_ROUNDS` | `2` | No | Max decomposition rounds |
| `DUAL_DOC_TOP_K` | `8` | No | Dual retriever: document top-k |
| `DUAL_WEB_PER_CONNECTOR` | `3` | No | Web results per connector |
| `DUAL_WEB_TIMEOUT_S` | `12.0` | No | Web retrieval timeout |
| `DUAL_NLI_ENTAIL_THRESHOLD` | `0.55` | No | NLI entailment threshold |
| `DUAL_NLI_CONTRA_THRESHOLD` | `0.45` | No | NLI contradiction threshold |
| `CONFIDENCE_W_COVERAGE` | `0.25` | No | Confidence weight: evidence coverage |
| `CONFIDENCE_W_CLAIM_SUPPORT` | `0.35` | No | Confidence weight: claim support |
| `CONFIDENCE_W_AGREEMENT` | `0.20` | No | Confidence weight: source agreement |
| `CONFIDENCE_W_QUALITY` | `0.20` | No | Confidence weight: source quality |
| `CONFIDENCE_FORMULA_VERSION` | `v1.0` | No | Confidence formula version tag |
| `RELIABILITY_ALPHA` | `0.40` | No | Reliability score: recency weight |
| `RELIABILITY_BETA` | `0.30` | No | Reliability score: citation weight |
| `RELIABILITY_GAMMA` | `0.30` | No | Reliability score: venue weight |
| `RELIABILITY_LAMBDA` | `0.05` | No | Reliability score: penalty term |
| `RELIABILITY_CITES_MAX` | `1000.0` | No | Citation count ceiling for normalisation |

---

## spaCy Model

The NER and sentence-splitting pipeline uses `en_core_web_sm` by default.  
A lightweight fallback (regex-based splitting) is used automatically if spaCy is unavailable, so this step is optional for development.

```bash
python -m spacy download en_core_web_sm
```

To use a different model, set `SPACY_MODEL=<model-name>` in your `.env`.

---

## Architecture Overview

```
UNKNOWN-clean/
├── backend/                 FastAPI application
│   ├── app/
│   │   ├── main.py          API routes (FastAPI)
│   │   ├── rag/             RAG engine: retrieval, ranking, confidence, claims
│   │   └── services/        High-level service layer
│   ├── tests/               pytest test suite
│   └── requirements.txt
├── frontend/                React 19 + Vite 8 SPA
│   └── src/
│       ├── components/      Shared UI components
│       └── pages/           Route-level page components
├── scripts/
│   └── download_models.py   Pre-download HuggingFace models (used in Dockerfile)
├── Dockerfile               Multi-stage: builds frontend, then Python backend
├── docker-compose.yml       One-command start
├── .env.example             All variables with safe placeholder values
└── .github/
    └── workflows/
        └── ci.yml           GitHub Actions CI (pytest -m "not slow")
```

**Data flow:**  
Query → Smart Router (`/smart-query`) → hybrid BM25+FAISS retrieval → NLI re-ranking → LLM answer generation → confidence scoring (`compute_confidence`) → source attribution (`build_sources`) → streaming JSON response.
