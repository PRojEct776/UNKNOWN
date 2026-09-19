"""
Project UNKNOWN (AETHER)
Global configuration module.

Purpose:
    Centralized configuration for the Retrieval-Augmented Generation (RAG) engine.
    Every module imports settings from this file instead of hardcoding values.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Immutable global configuration for Project UNKNOWN."""

    # ------------------------------------------------------------------
    # Project Root (backend/)
    # ------------------------------------------------------------------
    BASE_DIR: Path = Path(__file__).resolve().parents[2]

    # ------------------------------------------------------------------
    # Dataset Directories
    # ------------------------------------------------------------------
    DATASET_DIR: Path = BASE_DIR / "datasets"
    PAPERS_DIR: Path = DATASET_DIR / "papers"
    JSON_DIR: Path = DATASET_DIR / "json"
    CHUNK_DIR: Path = DATASET_DIR / "chunks"

    # ------------------------------------------------------------------
    # Storage Directories
    # ------------------------------------------------------------------
    VECTOR_DIR: Path = BASE_DIR / "vector_store"
    LOG_DIR: Path = BASE_DIR / "logs"

    # ------------------------------------------------------------------
    # RAG Configuration
    # ------------------------------------------------------------------
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    TOP_K_RESULTS: int = 5

    # ------------------------------------------------------------------
    # Embedding Model
    # ------------------------------------------------------------------
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ------------------------------------------------------------------
    # Supported Input Files
    # ------------------------------------------------------------------
    SUPPORTED_EXTENSIONS: tuple[str, ...] = (".pdf", ".docx", ".txt")

    # ------------------------------------------------------------------
    # File Encoding
    # ------------------------------------------------------------------
    DEFAULT_ENCODING: str = "utf-8"


# Global settings instance
settings = Settings()


# ----------------------------------------------------------------------
# Automatically create required project directories.
# ----------------------------------------------------------------------
REQUIRED_DIRECTORIES = [
    settings.PAPERS_DIR,
    settings.JSON_DIR,
    settings.CHUNK_DIR,
    settings.VECTOR_DIR,
    settings.LOG_DIR,
]

for directory in REQUIRED_DIRECTORIES:
    directory.mkdir(parents=True, exist_ok=True)