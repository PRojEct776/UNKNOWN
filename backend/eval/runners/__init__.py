"""
Evaluation runners package.
"""
from eval.runners.base import RunResult
from eval.runners.pipeline import STRATEGIES, run_strategy

__all__ = ["STRATEGIES", "run_strategy", "RunResult"]
