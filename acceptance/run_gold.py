"""
UNKNOWN Acceptance Suite - Gold Questions Evaluation Runner
Reads gold/questions.jsonl, executes real RAG API queries via FastAPI app (zero mocks),
and saves answers, claims, sources, and confidence to results/raw.jsonl.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure backend package is in python path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT / "backend"))

from fastapi.testclient import TestClient
from app.main import app

def run_gold_evaluation(
    gold_path: Path | str = WORKSPACE_ROOT / "gold" / "questions.jsonl",
    results_path: Path | str = WORKSPACE_ROOT / "results" / "raw.jsonl",
) -> list[dict]:
    gold_file = Path(gold_path)
    out_file = Path(results_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if not gold_file.exists():
        raise FileNotFoundError(f"Gold questions file not found: {gold_file}")

    questions: list[dict] = []
    with open(gold_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))

    client = TestClient(app)
    results: list[dict] = []

    print(f"Executing {len(questions)} gold benchmark questions with real API pipeline...")

    with open(out_file, "w", encoding="utf-8") as f_out:
        for idx, item in enumerate(questions, 1):
            q_id = item.get("id", f"q{idx}")
            query = item["question"]
            doc = item.get("document")
            grounded = item.get("grounded", True)

            payload = {
                "query": query,
                "document_names": [doc] if doc else None,
                "scope": "all",
            }

            print(f"[{idx}/{len(questions)}] Querying: '{query[:60]}...' (doc={doc})")
            try:
                response = client.post("/answer", json=payload)
                status_code = response.status_code
                if status_code == 200:
                    data = response.json()
                    answer_text = data.get("detail") or data.get("summary") or ""
                    claims = data.get("claims") or []
                    sources = data.get("sources") or []
                    confidence = data.get("confidence")
                else:
                    data = {}
                    answer_text = f"API error: {response.text}"
                    claims = []
                    sources = []
                    confidence = 0.0
            except Exception as exc:
                status_code = 500
                data = {}
                answer_text = f"Exception: {exc}"
                claims = []
                sources = []
                confidence = 0.0

            result_entry = {
                "id": q_id,
                "question": query,
                "expected_grounded": grounded,
                "document": doc,
                "status_code": status_code,
                "answer": answer_text,
                "claims": claims,
                "sources": sources,
                "confidence": confidence,
            }

            results.append(result_entry)
            f_out.write(json.dumps(result_entry, ensure_ascii=False) + "\n")
            f_out.flush()

    print(f"Successfully evaluated {len(results)} questions. Results saved to {out_file}")
    return results

if __name__ == "__main__":
    run_gold_evaluation()
