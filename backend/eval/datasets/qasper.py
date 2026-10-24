"""
QASPER dataset loader for retrieval evaluation.
"""
from __future__ import annotations

import json
from pathlib import Path
from eval.datasets.base import EvalQuery


def load_qasper(n: int = 50, use_fixture: bool = False) -> list[EvalQuery]:
    """
    Load QASPER evaluation queries.
    Attempts to load from HuggingFace datasets unless use_fixture=True or datasets fails.
    Falls back to bundled fixture file.
    """
    if not use_fixture:
        try:
            from datasets import load_dataset  # type: ignore

            ds = load_dataset("allenai/qasper", split="train")
            queries: list[EvalQuery] = []
            for item in ds:
                paper_id = item.get("id", "qp")
                qas = item.get("qas", {})
                questions = qas.get("question", [])
                answers = qas.get("answers", [])
                for q_idx, question in enumerate(questions):
                    ans_list = answers[q_idx].get("answer", []) if q_idx < len(answers) else []
                    rel_ids = set()
                    passages: dict[str, str] = {}
                    for a_idx, ans in enumerate(ans_list):
                        evidences = ans.get("evidence", [])
                        for ev_idx, ev in enumerate(evidences):
                            pid = f"p_{ev_idx}"
                            passages[pid] = ev
                            rel_ids.add(pid)
                    if passages:
                        queries.append(
                            EvalQuery(
                                query_id=f"qp_{paper_id}_{q_idx}",
                                query=question,
                                relevant_ids=rel_ids,
                                passages=passages,
                                label="answerable",
                            )
                        )
                    if len(queries) >= n:
                        return queries
        except Exception:
            pass  # Fall through to fixture loader

    fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "qasper_50.jsonl"
    queries: list[EvalQuery] = []
    with open(fixture_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            queries.append(
                EvalQuery(
                    query_id=data["query_id"],
                    query=data["query"],
                    relevant_ids=set(data.get("relevant_ids", [])),
                    passages=dict(data.get("passages", {})),
                    label=data.get("label", "answerable"),
                    metadata=data.get("metadata", {}),
                )
            )
            if len(queries) >= n:
                break
    return queries
