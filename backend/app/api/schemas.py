"""
UNKNOWN Project - FastAPI Schemas

Defines request and response models for the UNKNOWN API.
"""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Incoming user query."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User's natural-language question.",
    )


class Source(BaseModel):
    """Retrieved source information."""

    rank: int
    document: str
    page: int | str
    chunk_id: str
    hybrid_score: float
    bm25_score: float
    faiss_score: float


class QueryResponse(BaseModel):
    """Final UNKNOWN API response."""

    query: str
    query_type: str
    answer: str
    sources: list[Source]
class ClaimVerificationRequest(BaseModel):
    """Incoming claim verification request."""

    claim: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Claim to verify against the indexed documents.",
    )


class ClaimVerificationResponse(BaseModel):
    """Claim verification API response."""

    claim: str
    verdict: str
    confidence: float
    explanation: str
    evidence: list[str]
    source_chunk_ids: list[str]
    sources: list[Source]