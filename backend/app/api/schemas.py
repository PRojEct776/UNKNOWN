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


class ContradictionRequest(BaseModel):
    """Incoming contradiction analysis request."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Question or topic to analyze for conflicting evidence.",
    )


class EvidenceClaimResponse(BaseModel):
    """A claim extracted from retrieved document evidence."""

    claim: str
    evidence: str
    document: str
    page: int | str
    chunk_id: str


class ClaimRelationshipResponse(BaseModel):
    """Relationship between two evidence-backed claims."""

    claim_a: EvidenceClaimResponse
    claim_b: EvidenceClaimResponse
    relation: str
    confidence: float
    explanation: str


class ContradictionResponse(BaseModel):
    """Contradiction analysis API response."""

    query: str
    claims: list[EvidenceClaimResponse]
    relationships: list[ClaimRelationshipResponse]
    contradictions_found: int


class ResearchComparisonRequest(BaseModel):
    """Incoming research comparison request."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Research question or topic to compare.",
    )


class ResearchGapRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Research question or topic for gap detection.",
    )


class ResearchGapResponse(BaseModel):
    query: str
    research_area: str
    existing_findings: list[str]
    reported_limitations: list[str]
    gaps: list[dict]
    sources: list[dict]


class DebateRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Research question for evidence-grounded debate.",
    )

    position_a: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="First position in the debate.",
    )

    position_b: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Second position in the debate.",
    )


class DebateResponse(BaseModel):
    query: str
    topic: str
    position_a: str
    position_b: str
    arguments: list[dict]
    rebuttals: list[dict]
    final_verdict: str
    verdict_confidence: float
    sources: list[dict]


class KnowledgeDNARequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Research topic for Knowledge DNA extraction.",
    )


class KnowledgeDNAResponse(BaseModel):
    query: str
    research_area: str
    core_topics: list[str]
    key_concepts: list[str]
    methods: list[str]
    findings: list[str]
    limitations: list[str]
    themes: list[str]
    signals: list[dict]
    relationships: list[dict]
    sources: list[dict]


class KnowledgeMindMapRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Research topic for knowledge mind-map generation.",
    )


class KnowledgeMindMapResponse(BaseModel):
    query: str
    research_area: str
    nodes: list[dict]
    edges: list[dict]
    sources: list[dict]


class AdaptiveAnswerRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User query for adaptive answer mode selection.",
    )


class AdaptiveAnswerResponse(BaseModel):
    query: str
    mode: str


class ComparisonValueResponse(BaseModel):
    entity: str
    value: str
    evidence: str
    document: str
    page: int | str
    chunk_id: str


class ComparisonAspectResponse(BaseModel):
    aspect: str
    values: list[ComparisonValueResponse]


class ResearchComparisonResponse(BaseModel):
    query: str
    entities: list[str]
    comparison: list[ComparisonAspectResponse]
    summary: str
    sources: list[dict]
