"""One shared, validated evidence representation for VERIFY."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, List, Optional
from urllib.parse import urlparse

from .textutil import normalize_ws


class Verdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNVERIFIABLE = "UNVERIFIABLE"


class Mode(str, Enum):
    DOCUMENT_ONLY = "document_only"
    EXTERNAL_ONLY = "external_only"
    DOCUMENT_AND_EXTERNAL = "document_and_external"


class Stance(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    PARTIAL = "partial"
    CONTEXT = "context"          # relevant but neither supports nor contradicts


class Level(IntEnum):
    NONE = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3


class SourceType(str, Enum):
    PRIMARY_PAPER = "primary_paper"
    OFFICIAL_DATA = "official_data"
    GOVERNMENT = "government"
    OFFICIAL_DOCS = "official_docs"
    PUBLISHER_RECORD = "publisher_record"
    SCHOLARLY_SECONDARY = "scholarly_secondary"
    NEWS = "news"
    BLOG_OR_FORUM = "blog_or_forum"
    AI_SUMMARY = "ai_summary"
    UNKNOWN = "unknown"


class Inspection(str, Enum):
    FULL_TEXT = "full_text"
    ABSTRACT_ONLY = "abstract_only"
    SNIPPET_ONLY = "snippet_only"
    INACCESSIBLE = "inaccessible"


class Corroboration(str, Enum):
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    CONTRADICTED = "contradicted"
    NOT_FOUND = "not_found"
    NOT_CHECKED = "not_checked"


@dataclass
class DocumentEvidence:
    doc_id: str
    doc_name: str
    passage: str
    page: Optional[int] = None          # never invented; None when unknown
    chunk_id: Optional[str] = None
    stance: Optional[Stance] = None
    numeric: Any = None                 # numeric.NumericCheck


@dataclass
class ExternalEvidence:
    url: str
    passage: str
    source_type: SourceType = SourceType.UNKNOWN
    inspection: Inspection = Inspection.SNIPPET_ONLY
    title: Optional[str] = None
    publisher: Optional[str] = None
    published: Optional[str] = None
    derived_from: Optional[str] = None  # URL this page republishes/cites, if known
    stance: Optional[Stance] = None
    numeric: Any = None


@dataclass
class SearchInfo:
    queries: List[str] = field(default_factory=list)
    found: int = 0
    inspected: int = 0
    failed: int = 0
    failures: List[str] = field(default_factory=list)


@dataclass
class ExternalResearch:
    items: List[ExternalEvidence] = field(default_factory=list)
    search: SearchInfo = field(default_factory=SearchInfo)


@dataclass
class SideFinding:
    """Result of checking the claim against ONE side (document or external)."""
    verdict: Verdict
    evidence: List[Any] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    conflict: bool = False
    weak_opposition: bool = False
    unresolved: bool = False
    abstract_only_deciding: bool = False
    condition_unconfirmed: bool = False
    deciding_weight: float = 0.0
    best_weight: float = 0.0
    coverage: Optional[float] = None
    independent_clusters: int = 0
    retrieved: int = 0
    retrieval_failed: bool = False
    search: Optional[SearchInfo] = None


@dataclass
class ConfidenceReport:
    verdict_confidence: Level
    source_quality: Level
    evidence_coverage: Level
    search_completeness: Level
    reasons: List[str] = field(default_factory=list)


@dataclass
class VerificationResult:
    claim_id: Optional[str]
    claim_text: str
    mode: Mode
    verdict: Verdict
    document: Optional[SideFinding]
    external: Optional[SideFinding]
    corroboration: Corroboration
    confidence: ConfidenceReport
    limitations: List[str] = field(default_factory=list)
    citation_problems: List[str] = field(default_factory=list)


def to_dict(obj: Any) -> Any:
    """JSON-ready conversion (enums -> values, dataclasses -> dicts)."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, IntEnum):
        return obj.name
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (list, tuple)):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------- validation
def validate_document_evidence(
    e: DocumentEvidence, chunk_lookup: Optional[Callable[[str, str], Optional[str]]] = None
) -> List[str]:
    problems: List[str] = []
    if not e.doc_id:
        problems.append("document evidence is missing doc_id")
    if not e.doc_name:
        problems.append("document evidence is missing doc_name")
    if not (e.passage or "").strip():
        problems.append("document evidence has an empty passage")
    if e.page is not None and (not isinstance(e.page, int) or e.page < 1):
        problems.append(f"invalid page number: {e.page!r}")
    if chunk_lookup and e.chunk_id and e.doc_id:
        text = chunk_lookup(e.doc_id, e.chunk_id)
        if text is None:
            problems.append(f"unknown chunk {e.chunk_id!r} in document {e.doc_id!r}")
        elif normalize_ws(e.passage) not in normalize_ws(text):
            problems.append(f"passage is not contained in cited chunk {e.chunk_id!r}")
    return problems


def validate_external_evidence(e: ExternalEvidence, fetched_text: Optional[str] = None) -> List[str]:
    problems: List[str] = []
    parsed = urlparse(e.url or "")
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        problems.append(f"invalid or missing source URL: {e.url!r}")
    if not (e.passage or "").strip():
        problems.append("external evidence has an empty passage")
    if fetched_text is not None and e.passage and normalize_ws(e.passage) not in normalize_ws(fetched_text):
        problems.append("quoted passage not found in the fetched source content")
    return problems
