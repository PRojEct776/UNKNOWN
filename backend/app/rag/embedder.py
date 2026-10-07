"""
UNKNOWN - Embedding Model Loader

Provides a singleton SentenceTransformer embedding model for
semantic retrieval.

Model:
    sentence-transformers/all-MiniLM-L6-v2

Embedding dimension:
    384

The same model must be used for both document and query embeddings
so that FAISS similarity search operates in the same vector space.
"""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from app.rag.config import settings
from app.rag.logger import logger

# ================================================================
# EMBEDDING MODEL
# ================================================================

_embedding_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """
    Load the embedding model once and reuse it.

    Returns:
        SentenceTransformer: Singleton embedding model.
    """

    global _embedding_model

    if _embedding_model is None:
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")

        _embedding_model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device="cpu",
        )

        logger.info("Embedding model loaded successfully.")

    return _embedding_model


# ================================================================
# SINGLE TEXT EMBEDDING
# ================================================================


def embed_text(text: str) -> np.ndarray:
    """
    Generate a normalized embedding for a single text.

    Args:
        text: Input text.

    Returns:
        numpy.ndarray:
            Normalized embedding vector.

    For all-MiniLM-L6-v2:
        Shape = (384,)
    """

    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")

    if not text.strip():
        raise ValueError("text must not be empty")

    model = get_embedding_model()

    embedding = model.encode(
        text,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    return np.asarray(embedding, dtype=np.float32)


# ================================================================
# BATCH EMBEDDINGS
# ================================================================


def embed_texts(texts: list[str]) -> np.ndarray:
    """
    Generate normalized embeddings for multiple texts.

    Args:
        texts: List of input strings.

    Returns:
        numpy.ndarray:
            Shape = (number_of_texts, 384)
    """

    if not isinstance(texts, list):
        raise TypeError(f"texts must be list[str], got {type(texts).__name__}")

    if not all(isinstance(text, str) for text in texts):
        raise TypeError("texts must contain only strings")

    if not texts:
        return np.empty(
            (0, 384),
            dtype=np.float32,
        )

    if any(not text.strip() for text in texts):
        raise ValueError("texts must not contain empty strings")

    model = get_embedding_model()

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        batch_size=32,
        show_progress_bar=False,
    )

    return np.asarray(
        embeddings,
        dtype=np.float32,
    )


# ================================================================
# TEST BLOCK
# ================================================================

if __name__ == "__main__":

    sample_query = "Explain virtualization in cloud computing."

    embedding = embed_text(sample_query)

    norm = float(np.linalg.norm(embedding))

    print()
    print("========== EMBEDDER TEST ==========")
    print(f"Model Used      : " f"{settings.EMBEDDING_MODEL}")
    print(f"Sample Query    : " f"{sample_query}")
    print(f"Embedding Shape : " f"{embedding.shape}")
    print(f"Embedding Norm  : " f"{norm:.6f}")
    print(f"First 5 Values  : " f"{embedding[:5]}")
    print("===================================")
