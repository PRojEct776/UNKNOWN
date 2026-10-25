import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentence_transformers import SentenceTransformer, CrossEncoder
from transformers import pipeline
from app.rag.atomic_claims import NLI_MODEL

print("Downloading embedding model...")
SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

print("Downloading reranker...")
CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

print("Downloading NLI model:", NLI_MODEL)
pipeline("text-classification", model=NLI_MODEL)

print("ALL MODELS DOWNLOADED")