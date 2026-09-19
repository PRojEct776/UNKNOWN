"""
Embedding Model Loader for UNKNOWN

This module loads the embedding model only once (Singleton Pattern)
and provides helper functions for generating embeddings for
queries and document chunks.
"""

from sentence_transformers import SentenceTransformer

from app.rag.config import settings
from app.rag.logger import logger

# Singleton instance of the embedding model
_embedding_model = None


def get_embedding_model():
    """
    Load the embedding model once and reuse it across the application.
    """
    global _embedding_model

    if _embedding_model is None:
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")

        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)

        logger.info("Embedding model loaded successfully.")

    return _embedding_model


def embed_text(text: str):
    """
    Generate a normalized embedding for a single query or document text.

    Args:
        text (str): Input query or document text.

    Returns:
        numpy.ndarray: 384-dimensional normalized embedding vector.
    """
    model = get_embedding_model()

    return model.encode(
        text,
        normalize_embeddings=True
    )


def embed_texts(texts: list[str]):
    """
    Generate normalized embeddings for multiple texts in a batch.

    Args:
        texts (list[str]): List of document chunks.

    Returns:
        numpy.ndarray: Batch of normalized embedding vectors.
    """
    model = get_embedding_model()

    return model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=False
    )


# ---------------------- TEST BLOCK ---------------------- #

if __name__ == "__main__":

    sample_query = "Explain virtualization in cloud computing."

    embedding = embed_text(sample_query)

    print("\n========== EMBEDDER TEST ==========")
    print(f"Model Used      : {settings.EMBEDDING_MODEL}")
    print(f"Sample Query    : {sample_query}")
    print(f"Embedding Shape : {embedding.shape}")
    print(f"First 5 Values  : {embedding[:5]}")
    print("===================================")