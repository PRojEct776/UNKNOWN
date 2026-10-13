"""
UNKNOWN Project - FastAPI Application

Exposes the verified UNKNOWN RAG pipeline through HTTP APIs.
"""

import hashlib
import json
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.auth import (
    SessionCreateRequest,
    SessionResponse,
    resolve_authenticated_workspace,
    session_manager,
)
from app.rag.document_eligibility import is_test_document

from app.api.schemas import (
    AdaptiveAnswerRequest,
    AdaptiveAnswerResponse,
    ClaimVerificationRequest,
    ClaimVerificationResponse,
    ConceptDiscoveryRequest,
    ConceptDiscoveryResponse,
    ContradictionRequest,
    ContradictionResponse,
    DebateRequest,
    DebateResponse,
    KnowledgeDNARequest,
    KnowledgeDNAResponse,
    KnowledgeMindMapRequest,
    KnowledgeMindMapResponse,
    QueryAssistantRequest,
    QueryAssistantResponse,
    QueryRequest,
    QueryResponse,
    ReasoningRequest,
    ReasoningResponse,
    ResearchComparisonRequest,
    ResearchComparisonResponse,
    ResearchGapRequest,
    ResearchGapResponse,
    Source,
    VisualAnswerRequest,
    VisualAnswerResponse,
)
from app.rag.config import settings
from app.rag.exceptions import EmptyDocumentError, UnsupportedDocumentError
from app.rag.logger import logger
from app.services.document_service import ingest_document
from app.services.rag_service import (
    RAGService,
)  # pyright: ignore[reportAttributeAccessIssue]

# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="UNKNOWN AI",
    description="Adaptive Hybrid Retrieval-Augmented Generation API",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.CORS_ORIGINS.split(",")  # type: ignore
        if origin.strip()
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# RAG SERVICE
# ============================================================

rag_service = RAGService()


# ============================================================
# HEALTH CHECK
# ============================================================


@app.get("/health")
def health_check():
    """Check whether the UNKNOWN API is running."""

    return {
        "status": "healthy",
        "service": "UNKNOWN AI",
        "version": "1.0.0",
    }


# ============================================================
# AUTHENTICATION & WORKSPACE SESSIONS
# ============================================================


@app.post("/auth/session", response_model=SessionResponse)
def create_session(request: SessionCreateRequest | None = None):
    """
    Generate a server-side session token for a dedicated workspace partition.
    Protects user documents from client-supplied identity spoofing.
    """
    desired_workspace = request.workspace_id if request else None
    session_data = session_manager.create_session(desired_workspace)
    return SessionResponse(
        token=session_data["token"],
        workspace_id=session_data["workspace_id"],
        created_at=session_data["created_at"],
        is_authenticated=session_data["is_authenticated"],
    )


@app.get("/auth/session")
def get_session_info(
    request: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    """Inspect active session token and resolved workspace partition."""
    workspace, is_auth = resolve_authenticated_workspace(
        request, authorization, x_session_token
    )
    return {
        "workspace_id": workspace,
        "is_authenticated": is_auth,
        "security_isolation": (
            "Cryptographically verified session partition"
            if is_auth
            else "Unauthenticated sandbox workspace"
        ),
    }


# ============================================================
# DOCUMENT MANAGEMENT & INGESTION
# ============================================================


@app.post(
    "/documents/upload",
    responses={
        400: {"description": "Invalid, unsupported, empty, or duplicate file."},
        500: {"description": "Ingestion or indexing failure."},
    },
)
@app.post("/upload", include_in_schema=False)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Form("default_user"),
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    """
    Upload and index a PDF, DOCX, or TXT research document into the caller's workspace.

    Automatically extracts text, builds overlapping chunks,
    updates BM25 and FAISS vector indices, updates Document IQ metadata,
    and makes the new document instantly searchable strictly within the workspace.
    """
    active_user, _ = resolve_authenticated_workspace(
        request, authorization, x_session_token, client_user_id=user_id
    )

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file was provided.")

    filename = Path(file.filename).name
    # Path traversal and injection defense
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename format.")

    extension = Path(filename).suffix.lower()

    if extension not in settings.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{extension}'. Supported formats: {', '.join(settings.SUPPORTED_EXTENSIONS)}",
        )

    settings.PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    # Store with unique filename per workspace to prevent collisions
    if active_user != "default_user":
        storage_filename = f"{active_user}__{filename}"
    else:
        storage_filename = filename

    destination_path = settings.PAPERS_DIR / storage_filename

    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # Limit file size to 50MB
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds maximum allowed limit of 50MB.")

        # Content hash check for duplicate prevention
        content_hash = hashlib.sha256(content).hexdigest()

        # Check existing metadata for identical hash
        if settings.METADATA_DIR.exists():
            for m_path in settings.METADATA_DIR.glob("*_metadata.json"):
                try:
                    with open(m_path, "r", encoding="utf-8") as mf:
                        m_data = json.load(mf)
                        if m_data.get("document_hash") == content_hash:
                            raise HTTPException(
                                status_code=400,
                                detail=f"Duplicate upload detected: Document '{m_data.get('document', filename)}' with identical content already exists.",
                            )
                except HTTPException:
                    raise
                except Exception:
                    pass

        with open(destination_path, "wb") as f:
            f.write(content)

        report = ingest_document(destination_path, user_id=active_user)
        # Ensure display name returned to caller reflects clean filename
        report["document"] = filename
        report["user_id"] = active_user
        rag_service.reload_retriever()

        return report

    except HTTPException:
        raise
    except EmptyDocumentError as error:
        raise HTTPException(
            status_code=400,
            detail=f"Document contains no extractable text: {error}",
        ) from error
    except UnsupportedDocumentError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except Exception as error:
        logger.exception("Document ingestion failed.")
        raise HTTPException(
            status_code=500,
            detail=f"Document ingestion failed: {error}",
        ) from error


@app.get("/documents")
def list_documents(
    request: Request,
    user_id: str | None = None,
    include_test_docs: bool = False,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    """
    List indexed documents with metadata and Document IQ scores.
    Strictly filters by workspace and excludes test development documents by default.
    """
    active_user, has_token = resolve_authenticated_workspace(
        request, authorization, x_session_token, client_user_id=user_id
    )
    # If caller explicitly gave user_id or has a session token, scope to that user
    effective_user = active_user if (has_token or user_id) else None

    documents = []
    if settings.METADATA_DIR.exists():
        for path in sorted(settings.METADATA_DIR.glob("*_metadata.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    doc = json.load(f)
                    doc_name = doc.get("document", "")
                    # Exclude development/test fixtures unless explicitly requested
                    if not include_test_docs and is_test_document(doc_name, doc):
                        continue
                    # Filter by workspace
                    if effective_user and doc.get("user_id") and doc.get("user_id") != effective_user:
                        continue
                    documents.append(doc)
            except Exception:
                pass
    return {"documents": documents}



# ============================================================
# QUERY ENDPOINT
# ============================================================


@app.post(
    "/query",
    response_model=QueryResponse,
    responses={
        400: {
            "description": "The LLM provider rejected the request.",
        },
        429: {
            "description": "LLM provider quota or rate limit exceeded.",
        },
        502: {
            "description": "The configured LLM provider rejected the request or all providers failed.",
        },
        503: {
            "description": "LLM providers are temporarily unavailable.",
        },
        500: {
            "description": "Unexpected query processing failure.",
        },
    },
)
def query(
    request: QueryRequest,
    raw_req: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    """Execute the complete UNKNOWN RAG pipeline with workspace scoping."""
    if request.documents and len(request.documents) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 documents allowed for comparison or filtering.",
        )
    active_user, _ = resolve_authenticated_workspace(
        raw_req, authorization, x_session_token, client_user_id=request.user_id
    )

    start_time = time.perf_counter()

    try:
        response = rag_service.query(
            request.query,
            user_id=active_user,
            documents=request.documents,
        )
    except RuntimeError as error:
        logger.exception("Query processing failed.")

        error_kind = getattr(error, "error_kind", None)

        if error_kind == "rate_limit":
            raise HTTPException(
                status_code=429,
                detail="LLM provider quota or rate limit exceeded. Please try again later.",
            )

        if error_kind == "transient":
            raise HTTPException(
                status_code=503,
                detail="LLM providers are temporarily unavailable. Please try again later.",
            )

        if error_kind == "invalid_request":
            raise HTTPException(
                status_code=400,
                detail="The LLM provider rejected the request.",
            )

        if error_kind == "fatal":
            raise HTTPException(
                status_code=502,
                detail="The configured LLM provider rejected the request.",
            )

        raise HTTPException(
            status_code=502,
            detail="LLM providers were unable to process the query.",
        )
    except Exception as error:  # noqa: BLE001, F841
        logger.exception("Unexpected query processing failure.")

        raise HTTPException(
            status_code=500,
            detail="Unable to process the query at the moment.",
        )

    elapsed_ms = round(
        (time.perf_counter() - start_time) * 1000,
        2,
    )

    logger.info(f"Request completed in {elapsed_ms} ms")

    return response


@app.post(
    "/verify",
    response_model=ClaimVerificationResponse,
    responses={
        400: {
            "description": "The LLM provider rejected the request.",
        },
        429: {
            "description": "LLM provider quota or rate limit exceeded.",
        },
        502: {
            "description": "The configured LLM provider rejected the request or all providers failed.",
        },
        503: {
            "description": "LLM providers are temporarily unavailable.",
        },
        500: {
            "description": "Unexpected claim verification failure.",
        },
    },
)
def verify_claim(
    request: ClaimVerificationRequest,
    raw_req: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    """Verify a user-provided claim against indexed documents."""
    if request.documents and len(request.documents) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 documents allowed for comparison or filtering.",
        )
    active_user, _ = resolve_authenticated_workspace(
        raw_req, authorization, x_session_token, client_user_id=request.user_id
    )

    start_time = time.perf_counter()

    try:
        response = rag_service.verify_claim(
            request.claim,
            user_id=active_user,
            documents=request.documents,
        )

    except RuntimeError as error:
        logger.exception("Claim verification failed.")

        error_kind = getattr(error, "error_kind", None)

        if error_kind == "rate_limit":
            raise HTTPException(
                status_code=429,
                detail="LLM provider quota or rate limit exceeded. Please try again later.",
            )

        if error_kind == "transient":
            raise HTTPException(
                status_code=503,
                detail="LLM providers are temporarily unavailable. Please try again later.",
            )

        if error_kind == "invalid_request":
            raise HTTPException(
                status_code=400,
                detail="The LLM provider rejected the request.",
            )

        if error_kind == "fatal":
            raise HTTPException(
                status_code=502,
                detail="The configured LLM provider rejected the request.",
            )

        raise HTTPException(
            status_code=502,
            detail="LLM providers were unable to verify the claim.",
        )

    except ValueError as error:
        logger.exception("Invalid claim verification response.")

        raise HTTPException(
            status_code=502,
            detail=str(error),
        )

    except Exception:  # noqa: BLE001
        logger.exception("Unexpected claim verification failure.")

        raise HTTPException(
            status_code=500,
            detail="Unable to verify the claim at the moment.",
        )

    elapsed_ms = round(
        (time.perf_counter() - start_time) * 1000,
        2,
    )

    logger.info(f"Claim verification request completed in {elapsed_ms} ms")

    return response


@app.post(
    "/discover-concept",
    response_model=ConceptDiscoveryResponse,
    responses={
        400: {
            "description": "Invalid concept description.",
        },
        429: {
            "description": "LLM provider quota or rate limit exceeded.",
        },
        502: {
            "description": "LLM providers failed to identify the concept.",
        },
        503: {
            "description": "LLM providers are temporarily unavailable.",
        },
        500: {
            "description": "Unexpected concept discovery failure.",
        },
    },
)
def discover_concept(
    request: ConceptDiscoveryRequest,
    raw_req: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    """Identify a technical concept from a natural-language description."""
    if request.documents and len(request.documents) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 documents allowed for comparison or filtering.",
        )
    active_user, _ = resolve_authenticated_workspace(
        raw_req, authorization, x_session_token, client_user_id=request.user_id
    )

    start_time = time.perf_counter()

    try:
        result = rag_service.discover_concept(
            request.description,
            user_id=active_user,
            documents=request.documents,
        )

        return ConceptDiscoveryResponse(
            description=result.description,
            concept=result.concept,
            confidence=result.confidence,
            explanation=result.explanation,
            evidence=result.evidence,
            source_chunk_ids=result.source_chunk_ids,
        )

    except ValueError as error:
        logger.exception("Concept discovery validation failed.")
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except RuntimeError as error:
        logger.exception("Concept discovery failed.")

        error_kind = getattr(error, "error_kind", None)

        if error_kind == "rate_limit":
            raise HTTPException(
                status_code=429,
                detail="LLM provider quota or rate limit exceeded. Please try again later.",
            ) from error

        if error_kind == "transient":
            raise HTTPException(
                status_code=503,
                detail="LLM providers are temporarily unavailable. Please try again later.",
            ) from error

        if error_kind == "invalid_request":
            raise HTTPException(
                status_code=400,
                detail="The LLM provider rejected the request.",
            ) from error

        if error_kind == "fatal":
            raise HTTPException(
                status_code=502,
                detail="The configured LLM provider rejected the request.",
            ) from error

        raise HTTPException(
            status_code=502,
            detail="LLM providers were unable to discover the concept.",
        ) from error

    except Exception as error:
        logger.exception("Unexpected concept discovery failure.")
        raise HTTPException(
            status_code=500,
            detail="Unable to discover the concept at the moment.",
        ) from error

    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Concept discovery endpoint completed in %.2f ms.",
            elapsed_ms,
        )


@app.post(
    "/contradictions",
    response_model=ContradictionResponse,
)
def contradictions(
    request: ContradictionRequest,
    raw_req: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    """
    Detect conflicting claims across retrieved document evidence.
    """
    if request.documents and len(request.documents) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 documents allowed for comparison or filtering.",
        )
    active_user, _ = resolve_authenticated_workspace(
        raw_req, authorization, x_session_token, client_user_id=request.user_id
    )

    start_time = time.perf_counter()

    try:
        report = rag_service.find_contradictions(
            request.query,
            user_id=active_user,
            documents=request.documents,
        )

        return ContradictionResponse(
            query=report.query,
            claims=[claim.model_dump() for claim in report.claims],  # type: ignore
            relationships=[
                relationship.model_dump() for relationship in report.relationships
            ],  # type: ignore
            contradictions_found=report.contradictions_found,
        )

    except Exception as error:
        logger.exception("Contradiction analysis failed.")

        error_kind = getattr(error, "error_kind", None)

        if error_kind == "rate_limit":
            raise HTTPException(
                status_code=429,
                detail=str(error),
            ) from error

        if error_kind == "transient":
            raise HTTPException(
                status_code=503,
                detail=str(error),
            ) from error

        if error_kind == "invalid_request":
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error

        if error_kind == "fatal":
            raise HTTPException(
                status_code=502,
                detail=str(error),
            ) from error

        if isinstance(error, ValueError):
            raise HTTPException(
                status_code=502,
                detail=str(error),
            ) from error

        raise HTTPException(
            status_code=500,
            detail="Contradiction analysis failed.",
        ) from error

    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"Contradiction endpoint completed in {elapsed_ms:.2f} ms.")


@app.post(
    "/compare",
    response_model=ResearchComparisonResponse,
)
def compare(
    request: ResearchComparisonRequest,
    raw_req: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    if request.documents and len(request.documents) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 documents allowed for comparison.",
        )
    active_user, _ = resolve_authenticated_workspace(
        raw_req, authorization, x_session_token, client_user_id=request.user_id
    )

    start_time = time.perf_counter()

    try:
        report = rag_service.compare_research(
            request.query,
            documents=request.documents,
            user_id=active_user,
        )

        return ResearchComparisonResponse(
            query=report.query,
            entities=report.entities,
            comparison=[aspect.model_dump() for aspect in report.comparison],  # type: ignore
            summary=report.summary,
            sources=report.sources,
        )

    except Exception as error:
        logger.exception("Research comparison failed.")

        error_kind = getattr(error, "error_kind", None)

        if error_kind == "rate_limit":
            raise HTTPException(status_code=429, detail=str(error)) from error

        if error_kind == "transient":
            raise HTTPException(status_code=503, detail=str(error)) from error

        if error_kind == "invalid_request":
            raise HTTPException(status_code=400, detail=str(error)) from error

        if error_kind == "fatal":
            raise HTTPException(status_code=502, detail=str(error)) from error

        if isinstance(error, ValueError):
            raise HTTPException(status_code=502, detail=str(error)) from error

        raise HTTPException(
            status_code=500,
            detail="Research comparison failed.",
        ) from error

    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"Research comparison endpoint completed in {elapsed_ms:.2f} ms.")


@app.post("/gaps", response_model=ResearchGapResponse)
def research_gaps(
    request: ResearchGapRequest,
    raw_req: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    if request.documents and len(request.documents) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 documents allowed for comparison or filtering.",
        )
    active_user, _ = resolve_authenticated_workspace(
        raw_req, authorization, x_session_token, client_user_id=request.user_id
    )

    start_time = time.perf_counter()

    try:
        report = rag_service.find_research_gaps(
            request.query,
            user_id=active_user,
            documents=request.documents,
        )  # type: ignore

        return ResearchGapResponse(
            query=report.query,
            research_area=report.research_area,
            existing_findings=report.existing_findings,
            reported_limitations=report.reported_limitations,
            gaps=[gap.model_dump() for gap in report.gaps],
            sources=report.sources,
        )

    except Exception as error:
        logger.exception("Research gap detection failed.")

        error_kind = getattr(error, "error_kind", None)

        if error_kind == "rate_limit":
            raise HTTPException(
                status_code=429,
                detail=str(error),
            ) from error

        if error_kind == "transient":
            raise HTTPException(
                status_code=503,
                detail=str(error),
            ) from error

        if error_kind == "invalid_request":
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error

        if error_kind == "fatal":
            raise HTTPException(
                status_code=502,
                detail=str(error),
            ) from error

        if isinstance(error, ValueError):
            raise HTTPException(
                status_code=502,
                detail=str(error),
            ) from error

        raise HTTPException(
            status_code=500,
            detail="Research gap detection failed.",
        ) from error

    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Research gap endpoint completed in %.2f ms.",
            elapsed_ms,
        )


@app.post("/debate", response_model=DebateResponse)
def debate(
    request: DebateRequest,
    raw_req: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    if request.documents and len(request.documents) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 documents allowed for comparison or filtering.",
        )
    active_user, _ = resolve_authenticated_workspace(
        raw_req, authorization, x_session_token, client_user_id=request.user_id
    )

    start_time = time.perf_counter()

    try:
        report = rag_service.run_debate(  # type: ignore
            query=request.query,
            position_a=request.position_a,
            position_b=request.position_b,
            user_id=active_user,
            documents=request.documents,
        )

        return DebateResponse(
            query=report.query,
            topic=report.topic,
            position_a=report.position_a,
            position_b=report.position_b,
            arguments=[argument.model_dump() for argument in report.arguments],
            rebuttals=[rebuttal.model_dump() for rebuttal in report.rebuttals],
            final_verdict=report.final_verdict,
            verdict_confidence=report.verdict_confidence,
            sources=report.sources,
        )

    except Exception as error:
        logger.exception("AI debate failed.")

        error_kind = getattr(error, "error_kind", None)

        if error_kind == "rate_limit":
            raise HTTPException(
                status_code=429,
                detail=str(error),
            ) from error

        if error_kind == "transient":
            raise HTTPException(
                status_code=503,
                detail=str(error),
            ) from error

        if error_kind == "invalid_request":
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error

        if error_kind == "fatal":
            raise HTTPException(
                status_code=502,
                detail=str(error),
            ) from error

        if isinstance(error, ValueError):
            raise HTTPException(
                status_code=502,
                detail=str(error),
            ) from error

        raise HTTPException(
            status_code=500,
            detail="AI debate failed.",
        ) from error

    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "AI debate endpoint completed in %.2f ms.",
            elapsed_ms,
        )


@app.post("/knowledge-dna", response_model=KnowledgeDNAResponse)
def knowledge_dna(
    request: KnowledgeDNARequest,
    raw_req: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    if request.documents and len(request.documents) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 documents allowed for comparison or filtering.",
        )
    active_user, _ = resolve_authenticated_workspace(
        raw_req, authorization, x_session_token, client_user_id=request.user_id
    )

    start_time = time.perf_counter()

    try:
        report = rag_service.generate_knowledge_dna(
            query=request.query,
            user_id=active_user,
            documents=request.documents,
        )

        if report is None:
            raise HTTPException(
                status_code=500,
                detail="Knowledge DNA generation returned no report.",
            )

        return KnowledgeDNAResponse(
            query=report.query,
            research_area=report.research_area,
            core_topics=report.core_topics,
            key_concepts=report.key_concepts,
            methods=report.methods,
            findings=report.findings,
            limitations=report.limitations,
            themes=report.themes,
            signals=[signal.model_dump() for signal in report.signals],  # type: ignore
            relationships=[
                relationship.model_dump() for relationship in report.relationships  # type: ignore
            ],
            sources=report.sources,
        )

    except Exception as error:
        logger.exception("Knowledge DNA generation failed.")

        error_kind = getattr(error, "error_kind", None)

        if error_kind == "rate_limit":
            raise HTTPException(
                status_code=429,
                detail=str(error),
            ) from error

        if error_kind == "transient":
            raise HTTPException(
                status_code=503,
                detail=str(error),
            ) from error

        if error_kind == "invalid_request":
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error

        if error_kind == "fatal":
            raise HTTPException(
                status_code=502,
                detail=str(error),
            ) from error

        if isinstance(error, ValueError):
            raise HTTPException(
                status_code=502,
                detail=str(error),
            ) from error

        raise HTTPException(
            status_code=500,
            detail="Knowledge DNA generation failed.",
        ) from error

    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Knowledge DNA endpoint completed in %.2f ms.",
            elapsed_ms,
        )


@app.post(
    "/knowledge-mind-map",
    response_model=KnowledgeMindMapResponse,
)
def knowledge_mind_map(
    request: KnowledgeMindMapRequest,
    raw_req: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    if request.documents and len(request.documents) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 documents allowed for comparison or filtering.",
        )
    active_user, _ = resolve_authenticated_workspace(
        raw_req, authorization, x_session_token, client_user_id=request.user_id
    )

    start_time = time.perf_counter()

    try:
        report = rag_service.generate_knowledge_mind_map(  # type: ignore
            query=request.query,
            user_id=active_user,
            documents=request.documents,
        )

        return KnowledgeMindMapResponse(
            query=report.query,
            research_area=report.research_area,
            nodes=[node.model_dump() for node in report.nodes],
            edges=[edge.model_dump() for edge in report.edges],
            sources=report.sources,
        )

    except Exception as error:
        logger.exception("Knowledge mind map generation failed.")

        error_kind = getattr(error, "error_kind", None)

        if error_kind == "rate_limit":
            raise HTTPException(
                status_code=429,
                detail=str(error),
            ) from error

        if error_kind == "transient":
            raise HTTPException(
                status_code=503,
                detail=str(error),
            ) from error

        if error_kind == "invalid_request":
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error

        if error_kind == "fatal":
            raise HTTPException(
                status_code=502,
                detail=str(error),
            ) from error

        if isinstance(error, ValueError):
            raise HTTPException(
                status_code=502,
                detail=str(error),
            ) from error

        raise HTTPException(
            status_code=500,
            detail="Knowledge mind map generation failed.",
        ) from error

    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Knowledge mind map endpoint completed in %.2f ms.",
            elapsed_ms,
        )


@app.post(
    "/adaptive-answer",
    response_model=AdaptiveAnswerResponse,
)
def adaptive_answer(request: AdaptiveAnswerRequest):
    start_time = time.perf_counter()

    try:
        mode = rag_service.determine_answer_mode(  # type: ignore
            query=request.query,
        )

        return AdaptiveAnswerResponse(
            query=request.query,
            mode=mode.value,
        )

    except ValueError as error:
        logger.exception("Adaptive answer mode failed.")
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        logger.exception("Adaptive answer mode failed.")
        raise HTTPException(
            status_code=500,
            detail="Adaptive answer mode failed.",
        ) from error

    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Adaptive answer endpoint completed in %.2f ms.",
            elapsed_ms,
        )


@app.post(
    "/visual-answer",
    response_model=VisualAnswerResponse,
)
def visual_answer(
    request: VisualAnswerRequest,
    raw_req: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    if request.documents and len(request.documents) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 documents allowed for comparison or filtering.",
        )
    active_user, _ = resolve_authenticated_workspace(
        raw_req, authorization, x_session_token, client_user_id=request.user_id
    )

    start_time = time.perf_counter()

    try:
        result = rag_service.generate_visual_answer(
            query=request.query,
            user_id=active_user,
            documents=request.documents,
        )

        return VisualAnswerResponse(
            query=result.query,
            visual_type=result.visual_type.value,
            title=result.title,
            description=result.description,
            data=[item.model_dump() for item in result.data],
            elements=[item.model_dump() for item in result.elements],
            edges=[item.model_dump() for item in result.edges],
            sources=result.sources,
        )

    except ValueError as error:
        logger.exception("Visual answer generation failed.")
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        logger.exception("Visual answer generation failed.")
        raise HTTPException(
            status_code=500,
            detail="Visual answer generation failed.",
        ) from error

    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Visual answer endpoint completed in %.2f ms.",
            elapsed_ms,
        )


@app.post(
    "/reason",
    response_model=ReasoningResponse,
    responses={
        400: {"description": "Invalid reasoning query."},
        500: {"description": "Reasoning pipeline failure."},
    },
)
def reason(
    request: ReasoningRequest,
    raw_req: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    """Execute Srinidhi's multi-step reasoning pipeline with workspace scoping."""
    if request.documents and len(request.documents) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 documents allowed for comparison or filtering.",
        )
    active_user, _ = resolve_authenticated_workspace(
        raw_req, authorization, x_session_token, client_user_id=request.user_id
    )

    start_time = time.perf_counter()
    try:
        res = rag_service.reason(
            request.query,
            doc_filter=request.documents,
            user_id=active_user,
        )
        sources = [
            Source(
                rank=s.get("rank", 0),
                document=s.get("document", "Unknown"),
                page=s.get("page", "N/A"),
                chunk_id=s.get("chunk_id", "N/A"),
                hybrid_score=float(s.get("hybrid_score", 0.0)),
                bm25_score=float(s.get("bm25_score", 0.0)),
                faiss_score=float(s.get("faiss_score", 0.0)),
            )
            for s in res.get("sources", [])
        ]
        return ReasoningResponse(
            query=res.get("query", request.query),
            subquestions=res.get("subquestions", []),
            answer=res.get("answer", ""),
            sources=sources,
        )
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.exception("Reasoning endpoint failed.")
        raise HTTPException(
            status_code=500,
            detail=f"Reasoning processing failed: {error}",
        ) from error
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"Reasoning endpoint completed in {elapsed_ms:.2f} ms.")


@app.post(
    "/query-assistant",
    response_model=QueryAssistantResponse,
    responses={
        400: {"description": "Invalid query."},
        500: {"description": "Query Assistant processing failure."},
    },
)
def query_assistant(
    request: QueryAssistantRequest,
    raw_req: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
):
    """Improve research queries and suggest the best UNKNOWN tool."""
    active_user, _ = resolve_authenticated_workspace(
        raw_req, authorization, x_session_token, client_user_id=request.user_id
    )
    try:
        res = rag_service.query_assistant(request.query, task=request.task)
        return QueryAssistantResponse(
            original_query=res.get("original_query", request.query),
            refined_query=res.get("refined_query", request.query),
            suggested_task=res.get("suggested_task", "Research Assistant"),
            explanation=res.get("explanation", ""),
            alternative_queries=res.get("alternative_queries", []),
            tips=res.get("tips", []),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.exception("Query Assistant failed.")
        raise HTTPException(
            status_code=500,
            detail=f"Query Assistant failed: {error}",
        ) from error
