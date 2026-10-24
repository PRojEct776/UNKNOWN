"""
UNKNOWN Project - FastAPI Schemas

Defines request and response models for the UNKNOWN API.
"""

from typing import Any

from pydantic import BaseModel, Field


class Claim(BaseModel):
    """Atomic claim extracted and verified from generation."""

    text: str
    label: str = Field(
        default="supported",
        description="Verification verdict: supported, partial, unsupported, contradicted",
    )
    source_ids: list[str] = Field(default_factory=list)
    quote: str | None = None


class Conflict(BaseModel):
    """Contradiction or disagreement between claims."""

    topic: str
    side_a: str
    side_b: str
    likely_reason: str | None = None


class ConfidenceBreakdown(BaseModel):
    """Breakdown of confidence score components."""

    evidence_coverage: float = Field(..., ge=0.0, le=1.0)
    claim_support: float = Field(..., ge=0.0, le=1.0)
    source_agreement: float = Field(..., ge=0.0, le=1.0)
    source_quality: float = Field(..., ge=0.0, le=1.0)


class Confidence(BaseModel):
    """Deterministic confidence score and breakdown."""

    score: float = Field(..., ge=0.0, le=100.0)
    breakdown: ConfidenceBreakdown
    formula_version: str = "v1.0"


class ComparisonPair(BaseModel):
    """NLI-labelled pair comparing a doc passage against a web passage for a sub-question."""

    sub_question: str = Field(..., description="The (sub-)question this pair addresses")
    label: str = Field(
        ...,
        description="NLI verdict: agree | disagree | not_addressed",
    )
    doc_quote: str = Field("", description="Verbatim excerpt from the document channel")
    web_quote: str = Field("", description="Verbatim excerpt from the web channel")
    doc_source: str = Field("", description="Document name + page/chunk citation")
    web_source: str = Field("", description="URL from the web channel")
    nli_entail: float = Field(0.0, ge=0.0, le=1.0)
    nli_contra: float = Field(0.0, ge=0.0, le=1.0)


class AnswerRequest(BaseModel):
    """Request for the /answer dual-retrieval endpoint."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User's natural-language question.",
    )
    document_names: list[str] | None = Field(
        default=None,
        description="Scope list: only these docs will be searched. "
                    "Pass an empty list to search no documents (web-only). "
                    "Omit to use all authorized docs.",
    )
    doc_only: bool = Field(
        default=False,
        description="If True, skip all web connector calls (document-only scope).",
    )
    scope: str | None = Field(
        default=None,
        description="Scope restriction, e.g. 'document only'.",
    )
    user_id: str | None = None


class AnswerResponse(BaseModel):
    """Standardized answer response containing atomic claims and evidence breakdown."""

    summary: str = Field("", description="Max 3-sentence summary")
    detail: str = Field("", description="Full answer text from both channels")
    doc_section: str | None = Field(None, description="Grounded doc answer with page/chunk citations")
    web_section: str | None = Field(None, description="Grounded web answer with live URL citations")
    comparison: list[ComparisonPair] = Field(
        default_factory=list,
        description="Per-sub-question pairs labelled agree/disagree/not_addressed with both quotes",
    )
    sources: list[Any] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    confidence: Confidence | None = None
    trace_id: str | None = None


class QueryRequest(BaseModel):
    """Incoming user query."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User's natural-language question.",
    )
    document_names: list[str] | None = Field(
        default=None,
        description="Optional list of document names to scope retrieval to.",
    )
    user_id: str | None = None
    documents: list[str] | None = None

    def model_post_init(self, __context):
        super().model_post_init(__context)
        if self.document_names is None and self.documents is not None:
            self.document_names = self.documents
        elif self.documents is None and self.document_names is not None:
            self.documents = self.document_names


class Source(BaseModel):
    """Canonical source model returned by UNKNOWN endpoints."""

    id: str = "unknown"
    rank: int = 0
    document: str = "Unknown"
    page: int | str = "N/A"
    chunk_id: str = "N/A"
    hybrid_score: float = 0.0
    bm25_score: float = 0.0
    faiss_score: float = 0.0
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    origin: str = "document"
    passage: str | None = None
    quote: str | None = None
    retrieved_at: str | None = None
    reliability: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class QueryResponse(BaseModel):
    """Final UNKNOWN API response."""

    query: str
    query_type: str
    answer: str
    sources: list[Source]
    claims: list[Claim] = Field(default_factory=list)
    confidence: Confidence | None = None


class ClaimVerificationRequest(BaseModel):
    """Incoming claim verification request."""

    claim: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Claim to verify against the indexed documents.",
    )
    document_names: list[str] | None = Field(
        default=None,
        description="Optional list of document names to scope retrieval to.",
    )
    user_id: str | None = None
    documents: list[str] | None = None

    def model_post_init(self, __context):
        super().model_post_init(__context)
        if self.document_names is None and self.documents is not None:
            self.document_names = self.documents
        elif self.documents is None and self.document_names is not None:
            self.documents = self.document_names


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
    document_names: list[str] | None = Field(
        default=None,
        description="Optional list of document names to scope retrieval to.",
    )
    user_id: str | None = None
    documents: list[str] | None = None

    def model_post_init(self, __context):
        super().model_post_init(__context)
        if self.document_names is None and self.documents is not None:
            self.document_names = self.documents
        elif self.documents is None and self.document_names is not None:
            self.documents = self.document_names


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
    document_names: list[str] | None = Field(
        default=None,
        description="Optional list of document names to scope retrieval to.",
    )
    user_id: str | None = None
    documents: list[str] | None = None

    def model_post_init(self, __context):
        super().model_post_init(__context)
        if self.document_names is None and self.documents is not None:
            self.document_names = self.documents
        elif self.documents is None and self.document_names is not None:
            self.documents = self.document_names


class ResearchGapRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Research question or topic for gap detection.",
    )
    document_names: list[str] | None = Field(
        default=None,
        description="Optional list of document names to scope retrieval to.",
    )
    user_id: str | None = None
    documents: list[str] | None = None

    def model_post_init(self, __context):
        super().model_post_init(__context)
        if self.document_names is None and self.documents is not None:
            self.document_names = self.documents
        elif self.documents is None and self.document_names is not None:
            self.documents = self.document_names


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
    document_names: list[str] | None = Field(
        default=None,
        description="Optional list of document names to scope retrieval to.",
    )
    user_id: str | None = None
    documents: list[str] | None = None

    def model_post_init(self, __context):
        super().model_post_init(__context)
        if self.document_names is None and self.documents is not None:
            self.document_names = self.documents
        elif self.documents is None and self.document_names is not None:
            self.documents = self.document_names


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
    document_names: list[str] | None = Field(
        default=None,
        description="Optional list of document names to scope retrieval to.",
    )
    user_id: str | None = None
    documents: list[str] | None = None

    def model_post_init(self, __context):
        super().model_post_init(__context)
        if self.document_names is None and self.documents is not None:
            self.document_names = self.documents
        elif self.documents is None and self.document_names is not None:
            self.documents = self.document_names


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
    document_names: list[str] | None = Field(
        default=None,
        description="Optional list of document names to scope retrieval to.",
    )
    user_id: str | None = None
    documents: list[str] | None = None

    def model_post_init(self, __context):
        super().model_post_init(__context)
        if self.document_names is None and self.documents is not None:
            self.document_names = self.documents
        elif self.documents is None and self.document_names is not None:
            self.documents = self.document_names


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
    document_names: list[str] | None = Field(
        default=None,
        description="Optional list of document names to scope retrieval to.",
    )
    user_id: str | None = None
    documents: list[str] | None = None

    def model_post_init(self, __context):
        super().model_post_init(__context)
        if self.document_names is None and self.documents is not None:
            self.document_names = self.documents
        elif self.documents is None and self.document_names is not None:
            self.documents = self.document_names


class AdaptiveAnswerResponse(BaseModel):
    query: str
    mode: str


class VisualAnswerRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User query for visual answer generation.",
    )
    document_names: list[str] | None = Field(
        default=None,
        description="Optional list of document names to scope retrieval to.",
    )
    user_id: str | None = None
    documents: list[str] | None = None

    def model_post_init(self, __context):
        super().model_post_init(__context)
        if self.document_names is None and self.documents is not None:
            self.document_names = self.documents
        elif self.documents is None and self.document_names is not None:
            self.documents = self.document_names


class VisualAnswerResponse(BaseModel):
    query: str
    visual_type: str
    title: str
    description: str
    data: list[dict]
    elements: list[dict]
    edges: list[dict]
    sources: list[dict]


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


class ConceptDiscoveryRequest(BaseModel):
    """Incoming concept discovery request."""

    description: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural-language description of a concept the user cannot remember.",
    )
    document_names: list[str] | None = Field(
        default=None,
        description="Optional list of document names to scope retrieval to.",
    )
    user_id: str | None = None
    documents: list[str] | None = None

    def model_post_init(self, __context):
        super().model_post_init(__context)
        if self.document_names is None and self.documents is not None:
            self.document_names = self.documents
        elif self.documents is None and self.document_names is not None:
            self.documents = self.document_names


class ConceptDiscoveryResponse(BaseModel):
    """Concept discovery API response."""

    description: str
    concept: str | None
    confidence: float
    explanation: str
    evidence: list[str]
    source_chunk_ids: list[str]


class ReasoningRequest(BaseModel):
    """Incoming multi-step reasoning request."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Reasoning question for multi-step decomposition and synthesis.",
    )
    document_names: list[str] | None = Field(
        default=None,
        description="Optional list of document names to scope retrieval to.",
    )
    user_id: str | None = None
    documents: list[str] | None = None

    def model_post_init(self, __context):
        super().model_post_init(__context)
        if self.document_names is None and self.documents is not None:
            self.document_names = self.documents
        elif self.documents is None and self.document_names is not None:
            self.documents = self.document_names


class ReasoningResponse(BaseModel):
    """Multi-step reasoning API response."""

    query: str
    subquestions: list[str]
    answer: str
    sources: list[Source]


class QueryAssistantRequest(BaseModel):
    """Incoming query improvement request."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Raw or vague user question to refine.",
    )
    task: str | None = Field(
        default=None,
        description="Optional target UNKNOWN tool/task.",
    )
    user_id: str | None = None
    documents: list[str] | None = None
    document_names: list[str] | None = None


class QueryAssistantResponse(BaseModel):
    """Refined query and guidance suggestions."""

    original_query: str
    refined_query: str
    suggested_task: str
    explanation: str
    alternative_queries: list[str]
    tips: list[str]
