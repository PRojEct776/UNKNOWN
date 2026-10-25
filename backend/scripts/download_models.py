"""
Model Pre-download Script for UNKNOWN.
Pre-caches HuggingFace transformer and sentence-transformer models
during the Docker image build or local setup.
"""

import os
import sys

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
root_dir = os.path.dirname(backend_dir)
sys.path.insert(0, backend_dir)
sys.path.insert(0, root_dir)

from sentence_transformers import SentenceTransformer, CrossEncoder
from transformers import pipeline

NLI_MODEL = "cross-encoder/nli-deberta-v3-small"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

def download_all_models():
    print(f"--> [1/3] Downloading embedding model: {EMBEDDING_MODEL}")
    SentenceTransformer(EMBEDDING_MODEL)

    print(f"--> [2/3] Downloading reranker model: {RERANKER_MODEL}")
    CrossEncoder(RERANKER_MODEL)

    print(f"--> [3/3] Downloading NLI model: {NLI_MODEL}")
    pipeline("text-classification", model=NLI_MODEL)

    print("==> ALL MODELS DOWNLOADED SUCCESSFULLY")

if __name__ == "__main__":
    download_all_models()
