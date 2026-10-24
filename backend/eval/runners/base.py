"""
Base classes and result containers for evaluation runners.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RunResult:
    query_id: str
    retrieved_ids: list[str]  # ordered, best first
    scores: list[float]
    strategy: str
