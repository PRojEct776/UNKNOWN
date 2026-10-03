"""
UNKNOWN X v2.3 - Global Configuration Module

Purpose:
    Centralized configuration for the Retrieval-Augmented Generation (RAG) engine.
    Every module imports `settings` from this file instead of hardcoding values.

Features:
    - Immutable project configuration.
    - Automatic directory creation.
    - Environment variable support (.env).
    - Gemini API configuration.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# ==========================================================
# Load Environment Variables
# ==========================================================

BASE_DIR = Path(__file__).resolve().parents[2]

# Load backend/.env automatically.
load_dotenv(BASE_DIR / ".env")


# ==========================================================
# Global Settings
# ==========================================================


@dataclass(frozen=True)
class Settings:
    """Immutable global configuration for UNKNOWN X."""

    # ------------------------------------------------------
    # Project Root
    # ------------------------------------------------------
    BASE_DIR: Path = BASE_DIR

    # ------------------------------------------------------
    # Dataset Directories
    # ------------------------------------------------------
    DATASET_DIR: Path = BASE_DIR / "datasets"
    PAPERS_DIR: Path = DATASET_DIR / "papers"
    JSON_DIR: Path = DATASET_DIR / "json"
    CHUNK_DIR: Path = DATASET_DIR / "chunks"

    # ------------------------------------------------------
    # Storage Directories
    # ------------------------------------------------------
    VECTOR_DIR: Path = BASE_DIR / "vector_store"
    LOG_DIR: Path = BASE_DIR / "logs"

    # Metadata / Cache Directories
    METADATA_DIR: Path = BASE_DIR / "app" / "data" / "metadata"
    CACHE_DIR: Path = BASE_DIR / "app" / "data" / "cache"

    # ------------------------------------------------------
    # RAG Configuration
    # ------------------------------------------------------
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    TOP_K_RESULTS: int = 5

    # ------------------------------------------------------
    # Embedding Model
    # ------------------------------------------------------
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ------------------------------------------------------
    # Gemini Configuration
    # ------------------------------------------------------
    GOOGLE_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    GEMINI_MODEL: str = os.getenv(
        "MODEL_NAME",
        "gemini-3.6-flash",
    )

    # Provider timeout (milliseconds)
    GEMINI_TIMEOUT_MS: int = int(os.getenv("GEMINI_TIMEOUT_MS", "120000"))

    # LOW | MEDIUM | HIGH
    GEMINI_THINKING_LEVEL: str = os.getenv(
        "GEMINI_THINKING_LEVEL",
        "LOW",
    )

    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.2"))

    MAX_OUTPUT_TOKENS: int = int(os.getenv("MAX_OUTPUT_TOKENS", "2048"))
    # ------------------------------------------------------
    # Multi-LLM Provider Configuration
    # ------------------------------------------------------
    LLM_PROVIDER_ORDER: str = os.getenv(
        "LLM_PROVIDER_ORDER",
        "gemini,groq,cohere,openrouter",
    )

    LLM_TIMEOUT_S: float = float(os.getenv("LLM_TIMEOUT_S", "10.0"))

    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173",
    )

    # ------------------------------------------------------
    # Groq Configuration
    # ------------------------------------------------------
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv(
        "GROQ_MODEL",
        "openai/gpt-oss-120b",
    )

    # ------------------------------------------------------
    # Cohere Configuration
    # ------------------------------------------------------
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")
    COHERE_MODEL: str = os.getenv(
        "COHERE_MODEL",
        "command-a-03-2025",
    )

    # ------------------------------------------------------
    # OpenRouter Configuration
    # ------------------------------------------------------
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv(
        "OPENROUTER_MODEL",
        "openrouter/free",
    )
    # ------------------------------------------------------
    # Supported Input Files
    # ------------------------------------------------------
    SUPPORTED_EXTENSIONS: tuple[str, ...] = (
        ".pdf",
        ".docx",
        ".txt",
    )

    # ------------------------------------------------------
    # File Encoding
    # ------------------------------------------------------
    DEFAULT_ENCODING: str = "utf-8"

    def validate(self) -> None:
        """Validate configuration values that affect runtime behavior."""

        if not 0.0 <= self.TEMPERATURE <= 2.0:
            raise ValueError("TEMPERATURE must be between 0.0 and 2.0.")

        if self.MAX_OUTPUT_TOKENS <= 0:
            raise ValueError("MAX_OUTPUT_TOKENS must be greater than 0.")

        if self.GEMINI_TIMEOUT_MS <= 0:
            raise ValueError("GEMINI_TIMEOUT_MS must be greater than 0.")

        if self.LLM_TIMEOUT_S <= 0:
            raise ValueError("LLM_TIMEOUT_S must be greater than 0.")

        providers = {
            provider.strip().lower()
            for provider in self.LLM_PROVIDER_ORDER.split(",")
            if provider.strip()
        }

        supported = {"gemini", "groq", "cohere", "openrouter"}

        unknown = providers - supported
        if unknown:
            raise ValueError(f"Unsupported LLM providers configured: {sorted(unknown)}")

        if not providers:
            raise ValueError("LLM_PROVIDER_ORDER must contain at least one provider.")


# ==========================================================
# Global Settings Instance
# ==========================================================

settings = Settings()
settings.validate()

# ==========================================================
# Automatically Create Required Directories
# ==========================================================

REQUIRED_DIRECTORIES = [
    settings.PAPERS_DIR,
    settings.JSON_DIR,
    settings.CHUNK_DIR,
    settings.VECTOR_DIR,
    settings.LOG_DIR,
    settings.METADATA_DIR,
    settings.CACHE_DIR,
]

for directory in REQUIRED_DIRECTORIES:
    directory.mkdir(parents=True, exist_ok=True)
