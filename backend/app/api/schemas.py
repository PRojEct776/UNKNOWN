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
    source_mode: str | None = Field(
        default=None,
        pattern="^(documents|web|both)$",
        description="Explicit source choice: documents, web or both. "
                    "When omitted, doc_only and document_names behave as before.",
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
    conflicts: list[dict] = Field(default_factory=list)
    source_reliability: list[dict] = Field(default_factory=list)


class ClaimVerificationRequest(BaseModel):
    """Incoming claim verification request."""

    claim: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Claim to verify against the indexed documents.",
    )
    source_mode: str | None = Field(
        default=None,
        description=(
            "Optional evidence source: 'documents' (default, offline), "
            "'web', or 'both'."
        ),
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


class AtomicClaimVerification(BaseModel):
    """Verdict for one atomic part of a compound claim."""

    claim: str
    verdict: str
    confidence: float = 0.0
    explanation: str = ""
    evidence: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)


class ClaimVerificationResponse(BaseModel):
    """Claim verification API response."""

    claim: str
    verdict: str
    confidence: float
    explanation: str
    evidence: list[str]
    source_chunk_ids: list[str]
    sources: list[Source]
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    atomic_claims: list[AtomicClaimVerification] = Field(default_factory=list)
    # Whole-number percent (0-100) derived from `confidence` so clients display it as is.
    confidence_score: int | None = None

    def model_post_init(self, __context):
        super().model_post_init(__context)
        if self.confidence_score is None:
            clipped = max(0.0, min(1.0, float(self.confidence)))
            self.confidence_score = int(round(clipped * 100))


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


class OverviewSentence(BaseModel):
    """A single grounded summary sentence with page reference."""

    text: str
    source_ids: list[int] = Field(default_factory=list)
    quote: str = ""
    page_ref: str = "N/A"
    support: str = Field(
        default="grounded",
        description="grounded = LLM sentence verified against its cited passage; "
                    "extractive = verbatim sentence copied from a retrieved passage.",
    )


class DocumentIQReport(BaseModel):
    """Scores from the Document IQ engine."""

    iq_score: float = 0.0
    grade: str = "N/A"
    extraction_score: float = 0.0
    chunk_score: float = 0.0
    embedding_score: float = 0.0
    ocr_score: float = 0.0
    metadata_score: float = 0.0


class FigureDetail(BaseModel):
    id: str
    label: str
    caption: str = ""
    page: int | str = 1
    thumbnail: str = ""
    thumbnail_is_placeholder: bool = True  # generic icon, not an image of the real figure


class TableDetail(BaseModel):
    id: str
    label: str
    caption: str = ""
    page: int | str = 1
    thumbnail: str = ""
    thumbnail_is_placeholder: bool = True  # generic icon, not an image of the real table


class SectionStatus(BaseModel):
    """Status of one overview section, so a failure in one never hides the others."""

    status: str = Field(
        default="ok",
        description="ok | partial | empty | unavailable | failed",
    )
    error: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class SuggestedQuestion(BaseModel):
    """A suggested question with provenance."""

    text: str
    type: str = Field(
        default="exploratory",
        description="grounded = generated from retrieved document passages; "
                    "exploratory = generic template, not derived from this document.",
    )


class DocumentOverviewResponse(BaseModel):
    """Rich document overview returned by GET /documents/{name}/overview."""

    document_name: str
    document_hash: str = ""
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    page_count: int = 1
    language: str = "en"
    figure_count: int = 0
    table_count: int = 0
    figures: list[FigureDetail] = Field(default_factory=list)
    tables: list[TableDetail] = Field(default_factory=list)
    summary_sentences: list[OverviewSentence] = Field(default_factory=list)
    key_topics: list[str] = Field(default_factory=list)
    document_iq: dict = Field(default_factory=dict)
    suggested_questions: list[str] = Field(default_factory=list)
    question_details: list[SuggestedQuestion] = Field(default_factory=list)
    section_status: dict[str, SectionStatus] = Field(default_factory=dict)
    generated_at: str = ""
    generation_ms: float = 0.0
    from_cache: bool = False


# ===========================================================================
# Task P1-5: Concept Graph, Knowledge DNA, Smart Router Schemas
# ===========================================================================

class ConceptSource(BaseModel):
    document: str = ""
    page: int | str | None = None  # None = page unknown (never guessed)
    chunk_id: str = ""
    passage: str = ""


class ConceptGraphNode(BaseModel):
    id: str
    label: str
    cluster: str = "General"
    # Kept for API compatibility. No measured score exists, so these are
    # always None; the UI must not display or invent a value.
    relevance: float | None = None
    importance: float | None = None
    # Measured: number of document chunks whose text contains the label.
    mention_count: int = 0
    # "llm" = proposed by the model; "heuristic" = frequency-based fallback.
    origin: str = "unknown"
    sources: list[ConceptSource] = Field(default_factory=list)


class ConceptGraphEdge(BaseModel):
    source: str
    target: str
    # Relation type is the extractor's proposal, not a verified fact.
    relation: str = "RELATES_TO"
    # "co_occurrence": both concepts appear in the same passage (lexical only).
    # "relation_term_present": co-occurrence plus the relation word appears there.
    # "unverified": no evidence status was recorded.
    evidence_status: str = "unverified"
    origin: str = "unknown"
    sources: list[ConceptSource] = Field(default_factory=list)


class ConceptGraphExtraction(BaseModel):
    # "llm" or "heuristic_fallback"
    method: str = "llm"
    chunks_analyzed: int = 0
    chunks_total: int = 0
    dropped_nodes: int = 0
    dropped_edges: int = 0


class ConceptGraphResponse(BaseModel):
    document: str
    nodes: list[ConceptGraphNode] = Field(default_factory=list)
    edges: list[ConceptGraphEdge] = Field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0
    # "ok" or "empty"; when empty, empty_reason says why.
    status: str = "ok"
    empty_reason: str | None = None
    extraction: ConceptGraphExtraction = Field(default_factory=ConceptGraphExtraction)
    from_cache: bool = False


class DocumentDNAResponse(BaseModel):
    document: str
    concepts: list[str] = Field(default_factory=list)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    difficulty: str = "Intermediate"
    novelty: str = "Medium"
    summary: str = ""
    sources: list[ConceptSource] = Field(default_factory=list)
    from_cache: bool = False


class DNACompareRequest(BaseModel):
    document_a: str
    document_b: str


class DNACompareResponse(BaseModel):
    document_a: str
    document_b: str
    shared_concepts: list[str] = Field(default_factory=list)
    distinct_concepts_a: list[str] = Field(default_factory=list)
    distinct_concepts_b: list[str] = Field(default_factory=list)
    shared_methods: list[str] = Field(default_factory=list)
    claims_a: list[str] = Field(default_factory=list)
    claims_b: list[str] = Field(default_factory=list)
    difficulty_comparison: dict[str, Any] = Field(default_factory=dict)
    novelty_comparison: dict[str, Any] = Field(default_factory=dict)


class SmartQueryRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Query text or command")
    document_ids: list[str] | None = None
    stream: bool = False
    run_all: bool = False


class SmartQueryResponse(BaseModel):
    original_query: str
    rewritten_query: str
    matched_documents: list[str] = Field(default_factory=list)
    detected_feature: str | None = None
    executed_feature: str | None = None
    run_all: bool = False
    is_ambiguous: bool = False
    clarification_options: list[str] = Field(default_factory=list)
    result: Any = None


class AutocompleteDocItem(BaseModel):
    name: str
    title: str = ""
    type: str = "document"


class AutocompleteFeatureItem(BaseModel):
    feature: str
    label: str = ""
    keywords: list[str] = Field(default_factory=list)
    type: str = "feature"


class AutocompleteResponse(BaseModel):
    query: str
    documents: list[AutocompleteDocItem] = Field(default_factory=list)
    features: list[AutocompleteFeatureItem] = Field(default_factory=list)


# ===========================================================================
# Task P2-1: Feedback Schemas
# ===========================================================================

class FeedbackRequest(BaseModel):
    query: str
    answer: str
    sources: list[Any] = Field(default_factory=list)
    feedback_type: str = "thumbs_up"  # thumbs_up | thumbs_down | wrong_answer
    comment: str | None = None
    user_id: str | None = None


class FeedbackResponse(BaseModel):
    status: str
    id: str
    feedback_type: str
    recorded_at: str


# ===========================================================================
# Task P2-2: Export Request Schema
# ===========================================================================

class ExportRequest(BaseModel):
    query: str = "UNKNOWN Research Inquiry"
    answer: str = ""
    detailed_answer: str | None = None
    summary: str | None = None
    doc_section: str | None = None
    web_section: str | None = None
    comparison: list[dict[str, Any] | Any] = Field(default_factory=list)
    claims: list[dict[str, Any] | Any] = Field(default_factory=list)
    conflicts: list[dict[str, Any] | Any] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    confidence: dict[str, Any] | float | None = None
    sources: list[dict[str, Any] | Any] = Field(default_factory=list)
    document_names: list[str] = Field(default_factory=list)
    sample_greek: str | None = None
    sample_hindi: str | None = None