"""
Project UNKNOWN (AETHER)

Custom exception hierarchy for document ingestion and retrieval.
Supports PDF, DOCX, TXT, and future document formats.
"""


class UnknownProjectError(Exception):
    """Base exception for all Project UNKNOWN errors."""


class DocumentNotFoundError(UnknownProjectError):
    """Raised when the requested document does not exist."""


class UnsupportedDocumentError(UnknownProjectError):
    """Raised when the document format is not supported."""


class EmptyDocumentError(UnknownProjectError):
    """Raised when a document contains no extractable text."""


class DocumentExtractionError(UnknownProjectError):
    """Raised when document parsing or extraction fails."""