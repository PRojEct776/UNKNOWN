"""
UNKNOWN Project - FastAPI Schemas

Defines request and response models for the UNKNOWN API.
"""

from typing import List

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Incoming user query."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User's natural-language question."
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
    sources: List[Source]