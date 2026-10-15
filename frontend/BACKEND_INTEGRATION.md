# UNKNOWN frontend: backend integration handoff

This document describes the current frontend boundary. It is a contract proposal for coordination, not a claim that the backend already exists.

## 1. Current frontend state

- Stack: React 19, TypeScript, Vite, Tailwind CSS v4, React Router, Three.js / React Three Fiber.
- Main routes: `/login`, `/signup`, `/dashboard`, `/search`, `/profile`.
- The knowledge workspace already has query input, seven analysis modes, answer state views, evidence/source panels, search history, and knowledge visualizations.
- Authentication and profile data currently use browser-local demo logic (`src/lib/mockAuth.ts`). This is not production authentication: demo credentials are stored client-side, and displayed `unk_demo_*` tokens are placeholders rather than usable backend credentials. Do not enter real passwords or secrets into this demo. Replace this boundary with server-side authentication before production use.
- Discover currently attempts the retrieval API and falls back to a labelled local sample dataset if the backend cannot be reached or the response does not match the contract.
- Reasoning, verification, comparison, research-gap, debate, and knowledge-map views currently use static demo fixtures. They are not live backend results yet.

## 2. Existing Discover API contract

### Request

`POST {VITE_BACKEND_URL}/api/v1/retrieve`

Headers: `Content-Type: application/json`, `Accept: application/json`

Body:

```json
{
  "query": "Describe the concept or ask a question"
}
```

### Response expected by the current frontend

The endpoint must return one `ConceptResult` object directly (not wrapped in `{ "data": ... }`):

```json
{
  "id": "concept-id",
  "name": "Hybrid Retrieval",
  "category": "Information Retrieval",
  "description": "A concise description of the concept.",
  "usedIn": ["Document discovery"],
  "functions": ["Find relevant passages"],
  "relatedConcepts": ["BM25", "Dense Retrieval"],
  "confidenceScore": 0.9,
  "graphNodes": [
    { "id": "hybrid", "label": "Hybrid Retrieval", "isCentral": true, "type": "concept" }
  ],
  "graphEdges": []
}
```

This contract represents a concept and its graph relationships. It does **not** provide an evidence-grounded generated answer, evidence passages, source citations, or reasoning traces. Do not pretend it does. If the backend team plans a richer response, agree on a separate versioned contract before connecting it to the workspace.

## 3. Environment configuration

1. Copy `.env.example` to `.env.local` in the project root.
2. Set `VITE_BACKEND_URL` to the backend base URL agreed by the team.
3. Set `VITE_BACKEND_TIMEOUT_MS` if the default 5000 ms is unsuitable.
4. Restart Vite after changing environment variables.

Only non-secret configuration belongs in `VITE_*` variables because these values are exposed to browser code. Never put provider API keys, passwords, or private tokens in frontend environment variables.

## 4. Backend contract questions for the team

Before integration, agree on:

- Backend framework and local base URL.
- Whether `POST /api/v1/retrieve` will be kept or replaced.
- Exact request/response JSON and error response shape.
- CORS origins for the Vite development URL (typically `http://localhost:5173`).
- How the backend represents no matches, low-confidence results, and server errors.
- Whether the final RAG endpoint returns answer text, detailed answer, confidence, evidence, sources, and provenance separately from concept graph data.
- Which analysis modes are supported live for V1. Do not label unsupported modes as live.

## 5. Integration test checklist

- [ ] Backend is running at the configured URL.
- [ ] Browser request reaches the correct endpoint (inspect DevTools → Network).
- [ ] CORS permits the frontend origin.
- [ ] A valid response passes runtime validation and is labelled `backend`.
- [ ] Offline server / timeout leads to a clearly labelled `local-fallback` result during frontend development.
- [ ] Invalid JSON or a mismatched response does not crash the UI.
- [ ] Empty queries cannot be submitted.
- [ ] Errors and insufficient-evidence responses are distinguishable from successful answers.
- [ ] Evidence and citations are displayed only when the backend actually returns them.
- [ ] At least one end-to-end query is tested against the real backend before claiming integration is complete.

## 6. Commands

```bash
npm install
npm run dev
npm run build
```

Run `npm run build` after installing dependencies; it performs TypeScript project checks and then builds the Vite app.

## 7. Research-paper wording

Until the backend pipeline is implemented and tested, describe it as the **proposed architecture** or **planned integration**. Describe the current frontend and local fixtures as a prototype/demo. Only report measured performance or successful end-to-end behaviour after actual experiments.
