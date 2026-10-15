# UNKNOWN: Adaptive Hybrid Semantic Retrieval Engine

Frontend dashboard and concept-discovery application for **UNKNOWN: An Adaptive Hybrid Semantic Retrieval Engine for Intelligent Information Discovery**.

Built for College SEPM (Software Engineering and Project Management) & Research Methodology / IPR.

---

## What It Does

Traditional search engines rely on exact keyword matches. When a user knows what an object does, where it is used, or its properties—but does not know the exact terminology—traditional search often fails.

**UNKNOWN** bridges this lexical gap:

- Users input natural language descriptions (e.g. _"What's the thing used in warehouses to lift large loads?"_).
- The system identifies the intended concept (**Forklift**) using dense semantic representations combined with a structured knowledge graph.

---

## Features & Screens

1. **Authentication (`/login`, `/signup`)**
   - Client-side form validation, signup, login, logout, and protected routes.
   - Browser-local demo accounts and persistent sessions; the demo autofill is available on the login page.
   - Profile page with selectable avatars and custom image uploads.

2. **Dashboard (`/dashboard`)**
   - Introduces UNKNOWN as evidence-grounded knowledge discovery.
   - Describes a four-step question → retrieval → reasoning → grounded-answer architecture.
   - Links concept discovery, reasoning, verification, comparison, gap analysis, debate, mind-map, and Knowledge DNA modes into one workspace.

3. **Knowledge Workspace (`/search`)**
   - Natural-language query input and seven analysis modes.
   - Answer, confidence, evidence passages, source drawer, and explicit insufficient-evidence state.
   - Reasoning decomposition, claim outcomes, comparison matrix, research-gap exploration, and balanced debate views.
   - Interactive 3D concept/evidence/document graph, expandable mind map, and Knowledge DNA summary.
   - Search history persists in browser storage across workspace visits.

4. **Local demonstration data**
   - Discover uses the existing retrieval adapter and its established `ConceptResult` contract.
   - Reasoning, verification, comparison, gap analysis, debate, mind map, and Knowledge DNA use labeled local examples until their response contracts are available.
   - Evidence is shown only when the result includes evidence fields; concept results are not presented as source citations.

---

## Tech Stack

- **Framework:** React 19 + TypeScript + Vite
- **Styling:** Tailwind CSS v4 + Lucide React Icons
- **Animation:** Framer Motion
- **3D Graphics:** Three.js + React Three Fiber + Drei
- **Routing:** React Router v7

---

## Quick Start (Local Development)

### 1. Prerequisites

Ensure you have a Node.js version supported by the installed Vite release.

### 2. Install Dependencies

```bash
npm install
```

### 3. Start Development Server

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### 4. Build for Production

```bash
npm run build
```

To preview the built production bundle:

```bash
npm run preview
```

---

## Integration Boundary

The workspace preserves the existing `retrieveConcept` integration for Discover. Other analysis modes use static fixtures until their API response contracts are available. The reusable models are ready to represent future answers, evidence, sources, reasoning, analysis, graphs, and knowledge data without assuming those response formats.

The `src/lib/api.ts` retrieval service validates the response against the `ConceptResult` contract before accepting it. Its concept response does not contain evidence citations, so the UI does not infer evidence or sources from concept descriptions. See [`BACKEND_INTEGRATION.md`](./BACKEND_INTEGRATION.md) for the request/response contract and integration checklist.

Authentication and profile data are also browser-local demonstrations, not production identity management. Replace these boundaries only when backend contracts are ready.
