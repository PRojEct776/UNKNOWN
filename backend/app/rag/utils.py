"""
Project UNKNOWN (AETHER)

Utility functions for document preprocessing.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

from app.rag.config import settings


# ---------------------------------------------------------------------
# Unicode Normalization
# ---------------------------------------------------------------------
def normalize_unicode(text: str) -> str:
    """
    Normalize unicode characters from PDF extraction.
    Example:
        “Smart quotes” -> "Smart quotes"
    """

    return unicodedata.normalize("NFKC", text)


# ---------------------------------------------------------------------
# Text Cleaning
# ---------------------------------------------------------------------
def clean_text(text: str) -> str:
    """
    Clean extracted PDF text.

    Removes:
    - Extra whitespace
    - Line breaks
    - Hyphenated words across lines
    """

    text = normalize_unicode(text)

    # Merge hyphenated line breaks
    text = re.sub(r"-\s*\n\s*", "", text)

    # Replace remaining new lines with spaces
    text = text.replace("\n", " ")

    # Remove repeated whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ---------------------------------------------------------------------
# Metadata Utilities
# ---------------------------------------------------------------------
def count_words(text: str) -> int:
    """Return total word count."""

    return len(text.split())


def estimate_read_time(text: str, words_per_minute: int = 200) -> float:
    """
    Estimate reading time in minutes.
    """

    words = count_words(text)

    return round(words / words_per_minute, 2)


# ---------------------------------------------------------------------
# Hash Generator
# ---------------------------------------------------------------------
def generate_hash(text: str) -> str:
    """
    Generate SHA-256 hash for text.

    Used for chunk IDs.
    """

    return hashlib.sha256(text.encode(settings.DEFAULT_ENCODING)).hexdigest()


# ---------------------------------------------------------------------
# File Validation
# ---------------------------------------------------------------------
def is_supported_document(file_path: Path) -> bool:
    """
    Validate supported document types.
    """

    return file_path.suffix.lower() in settings.SUPPORTED_EXTENSIONS
def list_supported_documents(folder: Path) -> list[Path]:
    """
    Return all supported documents inside a folder.

    Files are returned in alphabetical order for reproducibility.
    """

    return sorted(
        file
        for file in folder.iterdir()
        if file.is_file() and is_supported_document(file)
    )