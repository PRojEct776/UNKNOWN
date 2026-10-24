"""
Evaluation datasets package.
"""
from eval.datasets.base import EvalQuery
from eval.datasets.beir import load_beir, load_beir_nfcorpus, load_beir_scifact
from eval.datasets.qasper import load_qasper
from eval.datasets.scifact import load_scifact

__all__ = [
    "EvalQuery",
    "load_scifact",
    "load_qasper",
    "load_beir",
    "load_beir_nfcorpus",
    "load_beir_scifact",
]
