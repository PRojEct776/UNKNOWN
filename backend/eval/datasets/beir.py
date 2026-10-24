"""
BEIR dataset loaders for retrieval evaluation (NFCorpus and SciFact).
"""
from __future__ import annotations

import json
from pathlib import Path
from eval.datasets.base import EvalQuery


def load_beir_nfcorpus(n: int = 50, use_fixture: bool = False) -> list[EvalQuery]:
    """
    Load BEIR NFCorpus evaluation queries.
    Attempts to load from HuggingFace datasets unless use_fixture=True or datasets fails.
    Falls back to bundled fixture file beir_nfcorpus_50.jsonl.
    """
    if not use_fixture:
        try:
            from datasets import load_dataset  # type: ignore

            ds_corpus = load_dataset("BeIR/nfcorpus", "corpus", split="corpus")
            ds_queries = load_dataset("BeIR/nfcorpus", "queries", split="queries")
            ds_qrels = load_dataset("BeIR/nfcorpus-qrels", split="test")

            corpus_map = {str(item["_id"]): item.get("text", "") for item in ds_corpus}
            qrels_map: dict[str, set[str]] = {}
            for row in ds_qrels:
                qid = str(row["query-id"])
                cid = str(row["corpus-id"])
                if row.get("score", 0) > 0:
                    qrels_map.setdefault(qid, set()).add(cid)

            queries: list[EvalQuery] = []
            for item in ds_queries:
                qid = str(item["_id"])
                rel_ids = qrels_map.get(qid, set())
                passages = {cid: corpus_map[cid] for cid in rel_ids if cid in corpus_map}
                queries.append(
                    EvalQuery(
                        query_id=f"nfc_{qid}",
                        query=item["text"],
                        relevant_ids=rel_ids,
                        passages=passages,
                        label="answerable" if rel_ids else "unanswerable",
                    )
                )
                if len(queries) >= n:
                    return queries
        except Exception:
            pass  # Fall through to fixture loader

    fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "beir_nfcorpus_50.jsonl"
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


def load_beir_scifact(n: int = 50, use_fixture: bool = False) -> list[EvalQuery]:
    """
    Load BEIR SciFact evaluation queries.
    Attempts to load from HuggingFace datasets unless use_fixture=True or datasets fails.
    Falls back to bundled fixture file beir_scifact_50.jsonl.
    """
    if not use_fixture:
        try:
            from datasets import load_dataset  # type: ignore

            ds_corpus = load_dataset("BeIR/scifact", "corpus", split="corpus")
            ds_queries = load_dataset("BeIR/scifact", "queries", split="queries")
            ds_qrels = load_dataset("BeIR/scifact-qrels", split="test")

            corpus_map = {str(item["_id"]): item.get("text", "") for item in ds_corpus}
            qrels_map: dict[str, set[str]] = {}
            for row in ds_qrels:
                qid = str(row["query-id"])
                cid = str(row["corpus-id"])
                if row.get("score", 0) > 0:
                    qrels_map.setdefault(qid, set()).add(cid)

            queries: list[EvalQuery] = []
            for item in ds_queries:
                qid = str(item["_id"])
                rel_ids = qrels_map.get(qid, set())
                passages = {cid: corpus_map[cid] for cid in rel_ids if cid in corpus_map}
                queries.append(
                    EvalQuery(
                        query_id=f"bsf_{qid}",
                        query=item["text"],
                        relevant_ids=rel_ids,
                        passages=passages,
                        label="answerable" if rel_ids else "unanswerable",
                    )
                )
                if len(queries) >= n:
                    return queries
        except Exception:
            pass  # Fall through to fixture loader

    fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "beir_scifact_50.jsonl"
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


def load_beir(name: str = "nfcorpus", n: int = 50, use_fixture: bool = False) -> list[EvalQuery]:
    """
    Dispatcher to load BeIR datasets by name ('nfcorpus' or 'scifact').
    """
    clean_name = name.lower().replace("beir_", "").replace("-", "_")
    if clean_name in ("nfcorpus", "nf_corpus"):
        return load_beir_nfcorpus(n=n, use_fixture=use_fixture)
    elif clean_name in ("scifact", "sci_fact"):
        return load_beir_scifact(n=n, use_fixture=use_fixture)
    else:
        raise ValueError(f"Unknown BeIR dataset: {name}. Supported: 'nfcorpus', 'scifact'")
