"""
SciFact dataset loader for retrieval evaluation.
"""
from __future__ import annotations

import json
from pathlib import Path
from eval.datasets.base import EvalQuery


def load_scifact(n: int = 50, use_fixture: bool = False) -> list[EvalQuery]:
    """
    Load SciFact evaluation queries.
    Attempts to load from HuggingFace datasets unless use_fixture=True or datasets fails.
    Falls back to bundled fixture file.
    """
    if not use_fixture:
        try:
            from datasets import load_dataset  # type: ignore

            ds_claims = load_dataset("allenai/scifact", "claims", split="train")
            ds_corpus = load_dataset("allenai/scifact", "corpus", split="train")
            corpus_map = {str(item["doc_id"]): " ".join(item.get("abstract", [])) for item in ds_corpus}

            queries: list[EvalQuery] = []
            for item in ds_claims:
                claim = item["claim"]
                cid = str(item["id"])
                doc_ids = [str(x) for x in item.get("doc_ids", [])]
                # sample local corpus: relevant docs + random distractors
                passages = {did: corpus_map[did] for did in doc_ids if did in corpus_map}
                queries.append(
                    EvalQuery(
                        query_id=f"sf_{cid}",
                        query=claim,
                        relevant_ids=set(doc_ids),
                        passages=passages,
                        label="answerable" if doc_ids else "unanswerable",
                    )
                )
                if len(queries) >= n:
                    return queries
        except Exception:
            pass  # Fall through to fixture loader

    fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "scifact_50.jsonl"
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
