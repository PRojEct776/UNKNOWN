"""
Embedding Model Loader for UNKNOWN

Uses the project's original embedding model:

    sentence-transformers/all-MiniLM-L6-v2

Windows compatibility:
Some Windows Application Control policies can block
scikit-learn's native sparsefuncs_fast DLL.

Sentence Transformers imports sklearn.metrics.pairwise_distances
during package initialization, while Transformers may also check
for sklearn during its generation-module initialization.

For UNKNOWN's embedding inference we do not need sklearn.

Therefore this module provides a temporary, in-memory sklearn
compatibility shim ONLY while SentenceTransformers is imported.

The real sklearn installation is not removed, modified, or disabled.
After SentenceTransformers finishes importing, the original module
state is restored.
"""

from __future__ import annotations

import importlib.machinery
import sys
import types

import numpy as np

# ================================================================
# WINDOWS / SKLEARN IMPORT COMPATIBILITY
# ================================================================
# Import only Transformers utility modules first.
# These do not require the blocked sklearn native extension.
import transformers.utils as _transformers_utils
import transformers.utils.import_utils as _transformers_import_utils

# Save original Transformers availability checks.
_original_import_utils_sklearn_check = _transformers_import_utils.is_sklearn_available

_original_utils_sklearn_check = _transformers_utils.is_sklearn_available


def _fallback_pairwise_distances(
    X,
    Y=None,
    metric="euclidean",
    **kwargs,
):
    """
    Minimal dense fallback for sklearn.metrics.pairwise_distances.

    SentenceTransformers does not use this function during ordinary
    embedding generation with all-MiniLM-L6-v2.

    It exists only so SentenceTransformers can finish importing
    without loading sklearn's blocked native DLL.
    """

    X = np.asarray(X, dtype=np.float64)

    if Y is None:
        Y = X
    else:
        Y = np.asarray(Y, dtype=np.float64)

    metric = str(metric).lower()

    if metric in ("euclidean", "l2"):
        diff = X[:, None, :] - Y[None, :, :]
        return np.sqrt(np.sum(diff * diff, axis=2))

    if metric in ("manhattan", "l1", "cityblock"):
        diff = X[:, None, :] - Y[None, :, :]
        return np.sum(np.abs(diff), axis=2)

    if metric == "cosine":
        x_norm = np.linalg.norm(X, axis=1, keepdims=True)
        y_norm = np.linalg.norm(Y, axis=1, keepdims=True)

        x_norm = np.maximum(x_norm, 1e-12)
        y_norm = np.maximum(y_norm, 1e-12)

        similarity = (X @ Y.T) / (x_norm @ y_norm.T)

        return 1.0 - similarity

    raise ValueError(f"Unsupported fallback distance metric: {metric}")


# ---------------------------------------------------------------
# Create temporary sklearn modules.
# ---------------------------------------------------------------

_fake_sklearn = types.ModuleType("sklearn")
_fake_sklearn.__path__ = []
_fake_sklearn.__spec__ = importlib.machinery.ModuleSpec(
    name="sklearn",
    loader=None,
    is_package=True,
)

_fake_metrics = types.ModuleType("sklearn.metrics")
_fake_metrics.__package__ = "sklearn"
_fake_metrics.__spec__ = importlib.machinery.ModuleSpec(
    name="sklearn.metrics",
    loader=None,
    is_package=False,
)

_fake_metrics.pairwise_distances = _fallback_pairwise_distances


# ---------------------------------------------------------------
# Save any existing sklearn module state.
# ---------------------------------------------------------------

_previous_sklearn = sys.modules.get("sklearn")
_previous_sklearn_metrics = sys.modules.get("sklearn.metrics")


try:

    # Put temporary compatibility modules in sys.modules.
    sys.modules["sklearn"] = _fake_sklearn
    sys.modules["sklearn.metrics"] = _fake_metrics

    # Tell Transformers that sklearn is unavailable.
    #
    # This prevents Transformers' optional generation machinery
    # from importing sklearn.metrics.roc_curve.
    _transformers_import_utils.is_sklearn_available = lambda: False
    _transformers_utils.is_sklearn_available = lambda: False

    # Import SentenceTransformers while the compatibility layer
    # is active.
    from sentence_transformers import SentenceTransformer

finally:

    # Restore Transformers functions.
    _transformers_import_utils.is_sklearn_available = (
        _original_import_utils_sklearn_check
    )

    _transformers_utils.is_sklearn_available = _original_utils_sklearn_check

    # Restore previous sklearn state.
    if _previous_sklearn is None:
        sys.modules.pop("sklearn", None)
    else:
        sys.modules["sklearn"] = _previous_sklearn

    if _previous_sklearn_metrics is None:
        sys.modules.pop("sklearn.metrics", None)
    else:
        sys.modules["sklearn.metrics"] = _previous_sklearn_metrics


# ================================================================
# UNKNOWN EMBEDDING MODEL
# ================================================================

from app.rag.config import settings
from app.rag.logger import logger

# Singleton model instance.
_embedding_model = None


def get_embedding_model():
    """
    Load the embedding model once and reuse it.
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


def embed_text(text: str):
    """
    Generate a normalized embedding for one text.

    Returns:
        numpy.ndarray

    For all-MiniLM-L6-v2:
        shape = (384,)
    """

    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")

    model = get_embedding_model()

    return model.encode(
        text,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )


def embed_texts(texts: list[str]):
    """
    Generate normalized embeddings for multiple texts.

    Returns:
        numpy.ndarray

    Expected shape:
        (number_of_texts, 384)
    """

    if not isinstance(texts, list):
        raise TypeError(f"texts must be list[str], got {type(texts).__name__}")

    if not all(isinstance(text, str) for text in texts):
        raise TypeError("texts must contain only strings")

    model = get_embedding_model()

    return model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        batch_size=32,
        show_progress_bar=False,
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
    print(f"Embedding Norm  : " f"{norm}")
    print(f"First 5 Values  : " f"{embedding[:5]}")
    print("===================================")
