"""
Base data structures for evaluation datasets.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalQuery:
    query_id: str
    query: str
    relevant_ids: set[str]  # corpus doc IDs that are relevant
    passages: dict[str, str]  # {doc_id: text} — the corpus for this query
    label: str = "answerable"  # "answerable" | "unanswerable" | "conflicting"
    metadata: dict = field(default_factory=dict)
