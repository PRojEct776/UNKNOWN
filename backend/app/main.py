"""
UNKNOWN Project - FastAPI Application

Exposes the verified UNKNOWN RAG pipeline through HTTP APIs.
"""

import json
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, File, UploadFile, Request, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles

from app.auth import (
    SessionCreateRequest,
    SessionResponse,
    is_demo_account,
    resolve_authenticated_workspace,
    session_manager,
)
from app.rag.document_eligibility import (
    get_user_authorized_documents,
    is_test_document,
)

from app.api.schemas import (
    DocumentOverviewResponse,
    ConceptGraphResponse,
    DocumentDNAResponse,
    DNACompareRequest,
    DNACompareResponse,
    SmartQueryRequest,
    SmartQueryResponse,
    AutocompleteResponse,
    FeedbackRequest,
    FeedbackResponse,
    ExportRequest,
    AnswerRequest,
    AnswerResponse,
    AdaptiveAnswerRequest,
    AdaptiveAnswerResponse,
    ComparisonPair,
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
    QueryAssistantRequest,
    QueryAssistantResponse,
)
from app.rag.config import settings
from app.rag.confidence import build_sources
from app.rag.logger import logger
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
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
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
# AUTHENTICATION & WORKSPACE SESSION
# ============================================================


@app.post("/auth/session", response_model=SessionResponse)
def create_session(payload: SessionCreateRequest | None = None):
    """Create or register an authenticated workspace session."""
    workspace = payload.workspace_id if payload else None
    session_data = session_manager.create_session(workspace_id=workspace)
    return SessionResponse(**session_data)


@app.get("/auth/session")
def get_current_session(
    request: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
    x_user_id: str | None = Header(None),
):
    """Retrieve current workspace session identity and disclosure."""
    active_user, is_auth = resolve_authenticated_workspace(
        request, authorization, x_session_token, x_user_id=x_user_id
    )
    return {
        "user_id": active_user,
        "is_authenticated": is_auth,
        "is_demo_account": is_demo_account(active_user),
        "security_level": "token_authenticated" if is_auth else "local_workspace_isolation",
        "notice": "Workspace identity enforced at API gateway. Local prototype session without external IdP.",
    }


def resolve_effective_documents(
    request: Request,
    authorization: str | None = None,
    x_session_token: str | None = None,
    x_user_id: str | None = None,
    requested_documents: list[str] | None = None,
) -> tuple[str, list[str]]:
    """
    Resolve active user and enforce strict workspace document authorization.
    Returns (active_user, scoped_documents).
    """
    from app.rag.document_eligibility import get_user_authorized_documents

    active_user, _ = resolve_authenticated_workspace(
        request, authorization, x_session_token, x_user_id=x_user_id
    )
    authorized_docs = get_user_authorized_documents(active_user, include_test_docs=True)

    if requested_documents is not None:
        scoped = [d for d in requested_documents if d in authorized_docs]
    else:
        scoped = list(authorized_docs)

    return active_user, scoped


# ============================================================
# DOCUMENT MANAGEMENT ENDPOINTS
# ============================================================


@app.get("/documents")
def list_documents(
    request: Request,
    user_id: str | None = None,
    include_test_docs: bool = False,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
    x_user_id: str | None = Header(None),
):
    """
    List indexed research documents.
    Supports workspace scoping, test-fixture filtering, and Document IQ metadata.
    """
    from app.rag.utils import list_supported_documents
    from app.services.document_service import (
        count_document_chunks,
        load_document_json,
    )
    from app.rag.document_eligibility import get_user_authorized_documents

    active_user, _ = resolve_authenticated_workspace(
        request, authorization, x_session_token, x_user_id=x_user_id, client_user_id=user_id
    )
    authorized_docs = get_user_authorized_documents(active_user, include_test_docs=include_test_docs)

    documents = []
    for paper_path in list_supported_documents(settings.PAPERS_DIR):
        doc_name = paper_path.name
        if doc_name not in authorized_docs:
            continue

        try:
            doc_data = load_document_json(doc_name)
            chunks = count_document_chunks(doc_name)
            documents.append(
                {
                    "name": doc_name,
                    "document": doc_name,
                    "title": doc_data.get("title", doc_name),
                    "document_type": doc_data.get("document_type", paper_path.suffix),
                    "total_pages": doc_data.get("total_pages", 1),
                    "total_words": doc_data.get("total_words", 0),
                    "chunks_count": chunks,
                    "status": "indexed",
                    "user_id": doc_data.get("user_id", "default_user"),
                }
            )
        except Exception:
            documents.append(
                {
                    "name": doc_name,
                    "document": doc_name,
                    "title": doc_name,
                    "document_type": paper_path.suffix,
                    "total_pages": 1,
                    "total_words": 0,
                    "chunks_count": 0,
                    "status": "stored",
                    "user_id": "default_user",
                }
            )

    return {"documents": documents, "total": len(documents)}


@app.get("/documents/{document_name}")
def get_document_detail(
    document_name: str,
    request: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
    x_user_id: str | None = Header(None),
):
    """Retrieve metadata and parsed text preview of an indexed paper."""
    from app.services.document_service import (
        count_document_chunks,
        load_document_json,
    )
    from app.rag.document_eligibility import get_user_authorized_documents

    safe_name = Path(document_name).name
    active_user, _ = resolve_authenticated_workspace(
        request, authorization, x_session_token, x_user_id=x_user_id
    )
    authorized_docs = get_user_authorized_documents(active_user, include_test_docs=True)
    if safe_name not in authorized_docs:
        raise HTTPException(
            status_code=404, detail=f"Document '{safe_name}' not found"
        )

    paper_path = settings.PAPERS_DIR / safe_name
    if not paper_path.exists() or not paper_path.is_file():
        raise HTTPException(
            status_code=404, detail=f"Document '{safe_name}' not found"
        )

    try:
        doc_data = load_document_json(safe_name)
        chunks = count_document_chunks(safe_name)
        pages = doc_data.get("pages", [])
        if pages:
            text_content = "\n\n".join(
                f"[Page {p.get('page_number', i+1)}]\n{p.get('text', '').strip()}"
                for i, p in enumerate(pages)
                if p.get("text", "").strip()
            )
        else:
            text_content = doc_data.get("text", "")

        return {
            "name": safe_name,
            "title": doc_data.get("title", safe_name),
            "document_type": doc_data.get("document_type", paper_path.suffix),
            "total_pages": doc_data.get("total_pages", len(pages) or 1),
            "total_words": doc_data.get("total_words", 0),
            "chunks_count": chunks,
            "content": text_content,
            "preview": text_content[:4000] if text_content else "No text preview available.",
            "has_original_file": True,
            "download_url": f"/documents/download/{safe_name}",
        }
    except Exception as e:
        logger.warning("Failed to load document json for %s: %s", safe_name, e)
        return {
            "name": safe_name,
            "title": safe_name,
            "document_type": paper_path.suffix,
            "total_pages": 1,
            "total_words": 0,
            "chunks_count": 0,
            "content": "",
            "preview": "Preview not available for this document.",
            "has_original_file": True,
            "download_url": f"/documents/download/{safe_name}",
        }



@app.get("/documents/{document_name}/overview", response_model=DocumentOverviewResponse)
def get_document_overview(
    document_name: str,
    request: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
    x_user_id: str | None = Header(None),
):
    """
    Return (or generate and cache) the full document overview.
    First call: makes LLM calls, caches result by file hash.
    Subsequent calls: returns from cache — zero LLM calls.
    """
    from app.rag.document_eligibility import get_user_authorized_documents
    from app.services.overview_service import generate_document_overview

    safe_name = Path(document_name).name
    active_user, _ = resolve_authenticated_workspace(
        request, authorization, x_session_token, x_user_id=x_user_id
    )
    authorized_docs = get_user_authorized_documents(active_user, include_test_docs=True)
    if safe_name not in authorized_docs:
        raise HTTPException(status_code=404, detail=f"Document '{safe_name}' not found")

    paper_path = settings.PAPERS_DIR / safe_name
    if not paper_path.exists() or not paper_path.is_file():
        raise HTTPException(status_code=404, detail=f"Document '{safe_name}' not found")

    def _llm_fn(prompt: str, temperature: float = 0.0) -> str:
        resp = rag_service.llm.generate_grounded(prompt) if temperature == 0.0 else rag_service.llm.generate(prompt)
        if not resp.success:
            raise RuntimeError(resp.error or "LLM failed")
        return resp.answer

    try:
        overview = generate_document_overview(
            document_name=safe_name,
            llm_fn=_llm_fn,
            retriever=rag_service.retriever,
        )
        return DocumentOverviewResponse(**overview)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Overview generation failed for %s", safe_name)
        raise HTTPException(status_code=500, detail=f"Overview generation failed: {exc}") from exc

@app.get("/documents/download/{document_name}")
def download_document(
    document_name: str,
    request: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
    x_user_id: str | None = Header(None),
):
    """Serve or download the original research paper file."""
    from app.rag.document_eligibility import get_user_authorized_documents

    safe_name = Path(document_name).name
    active_user, _ = resolve_authenticated_workspace(
        request, authorization, x_session_token, x_user_id=x_user_id
    )
    authorized_docs = get_user_authorized_documents(active_user, include_test_docs=True)
    if safe_name not in authorized_docs:
        raise HTTPException(
            status_code=404, detail=f"File '{safe_name}' not found on server"
        )

    paper_path = settings.PAPERS_DIR / safe_name
    if not paper_path.exists() or not paper_path.is_file():
        raise HTTPException(
            status_code=404, detail=f"File '{safe_name}' not found on server"
        )

    suffix = paper_path.suffix.lower()
    media_types = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".txt": "text/plain",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=str(paper_path),
        media_type=media_type,
        filename=safe_name,
        content_disposition_type="inline" if suffix in (".pdf", ".txt") else "attachment",
    )


@app.post("/documents/upload")
@app.post("/upload", include_in_schema=False)
async def upload_document(file: UploadFile = File(...)):
    """Upload a research document (.pdf, .docx, .txt) and index it."""
    from app.rag.document_loader import DocumentLoader
    from app.rag.utils import list_supported_documents

    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in settings.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{file_ext}'. Supported formats: {', '.join(settings.SUPPORTED_EXTENSIONS)}",
        )

    file_name = Path(file.filename or "upload").name
    save_path = settings.PAPERS_DIR / file_name

    existing_docs = [
        d for d in list_supported_documents(settings.PAPERS_DIR)
        if not is_test_document(d.name)
    ]
    existing_names = {d.name for d in existing_docs}
    if len(existing_docs) >= settings.MAX_COLLECTION_PAPERS and file_name not in existing_names:
        raise HTTPException(
            status_code=400,
            detail=f"Collection limit of {settings.MAX_COLLECTION_PAPERS} papers reached. Please delete a paper before uploading another.",
        )

    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(content) > settings.MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
            )

        import hashlib
        content_hash = hashlib.sha256(content).hexdigest()
        if settings.METADATA_DIR.exists():
            for meta_p in settings.METADATA_DIR.glob("*_metadata.json"):
                try:
                    with open(meta_p, "r", encoding="utf-8") as mf:
                        m_data = json.load(mf)
                        if m_data.get("document_hash") == content_hash:
                            raise HTTPException(
                                status_code=400,
                                detail=f"Duplicate document detected: content matches existing document '{m_data.get('document')}'",
                            )
                except HTTPException:
                    raise
                except Exception:
                    pass

        with open(save_path, "wb") as f:
            f.write(content)

        loader = DocumentLoader()
        doc_json = loader.create_document_json(save_path)
        loader.save_document_json(doc_json)

        from app.services.document_service import build_document_metadata, save_document_metadata
        from app.rag.scoring import calculate_document_iq
        metadata = build_document_metadata(file_name)
        iq_report = calculate_document_iq(metadata)
        metadata["document_iq"] = iq_report
        save_document_metadata(metadata)

        # Automatically re-chunk and build BM25 & FAISS indexes
        from app.rag.chunker import DocumentChunker
        from app.rag.bm25_index_builder import BM25IndexBuilder
        from app.rag.faiss_index_builder import FAISSIndexBuilder

        chunker = DocumentChunker()
        all_chunks = chunker.create_chunks()

        bm25_builder = BM25IndexBuilder()
        bm25_builder.build_index()

        faiss_builder = FAISSIndexBuilder()
        faiss_builder.build_index()

        rag_service.reload_indexes()

        # Generate document overview on upload and cache by document hash
        try:
            from app.services.overview_service import generate_document_overview

            def _llm_fn_upload(prompt: str, temperature: float = 0.0) -> str:
                resp = rag_service.llm.generate_grounded(prompt) if temperature == 0.0 else rag_service.llm.generate(prompt)
                if not resp.success:
                    raise RuntimeError(resp.error or "LLM failed")
                return resp.answer

            generate_document_overview(
                document_name=file_name,
                llm_fn=_llm_fn_upload,
                retriever=rag_service.retriever,
            )
        except Exception as o_err:
            logger.warning("Overview generation on upload warning: %s", o_err)

        doc_chunks = sum(1 for c in all_chunks if c.get("document") == file_name)

        return {
            "status": "success",
            "filename": file_name,
            "total_pages": doc_json.get("total_pages", 1),
            "total_words": doc_json.get("total_words", 0),
            "chunks_count": doc_chunks or len(all_chunks),
            "message": f"Successfully ingested and indexed {file_name} into retrieval pipeline.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Document upload processing failed.")
        from app.rag.exceptions import EmptyDocumentError
        if isinstance(exc, EmptyDocumentError):
            raise HTTPException(
                status_code=400,
                detail=f"Uploaded file '{file_name}' contains no readable or extractable text. If this is a PDF, ensure it contains clear readable text or scanned pages.",
            ) from exc
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {exc}",
        ) from exc


@app.post("/documents/upload-batch")
async def upload_batch_documents(files: list[UploadFile] = File(...)):
    """Upload up to 25 research documents in a batch and index them."""
    from app.rag.document_loader import DocumentLoader
    from app.rag.utils import list_supported_documents
    from app.rag.chunker import DocumentChunker
    from app.rag.bm25_index_builder import BM25IndexBuilder
    from app.rag.faiss_index_builder import FAISSIndexBuilder

    if not files:
        raise HTTPException(status_code=400, detail="No files provided in batch upload.")

    existing_docs = [
        d for d in list_supported_documents(settings.PAPERS_DIR)
        if not is_test_document(d.name)
    ]
    existing_names = {d.name for d in existing_docs}

    new_files = [f for f in files if Path(f.filename or "").name not in existing_names]
    if len(existing_docs) + len(new_files) > settings.MAX_COLLECTION_PAPERS:
        available_slots = max(0, settings.MAX_COLLECTION_PAPERS - len(existing_docs))
        raise HTTPException(
            status_code=400,
            detail=f"Cannot upload {len(new_files)} new file(s). Maximum collection capacity is {settings.MAX_COLLECTION_PAPERS} papers (currently {len(existing_docs)} papers, {available_slots} slot(s) remaining).",
        )

    results = []
    loader = DocumentLoader()
    any_success = False

    for file in files:
        file_name = Path(file.filename or "upload").name
        file_ext = Path(file.filename or "").suffix.lower()

        if file_ext not in settings.SUPPORTED_EXTENSIONS:
            results.append({
                "filename": file_name,
                "status": "failed",
                "error": f"Unsupported format '{file_ext}'. Supported: {settings.SUPPORTED_EXTENSIONS}",
                "total_pages": 0,
                "total_words": 0,
                "chunks_count": 0,
            })
            continue

        save_path = settings.PAPERS_DIR / file_name

        try:
            content = await file.read()
            if len(content) > settings.MAX_FILE_SIZE_BYTES:
                results.append({
                    "filename": file_name,
                    "status": "failed",
                    "error": f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
                    "total_pages": 0,
                    "total_words": 0,
                    "chunks_count": 0,
                })
                continue

            with open(save_path, "wb") as f:
                f.write(content)

            doc_json = loader.create_document_json(save_path)
            loader.save_document_json(doc_json)
            any_success = True
            results.append({
                "filename": file_name,
                "status": "ready",
                "error": None,
                "total_pages": doc_json.get("total_pages", 1),
                "total_words": doc_json.get("total_words", 0),
                "chunks_count": 0,
            })
        except Exception as exc:
            logger.exception("Failed to process file in batch: %s", file_name)
            results.append({
                "filename": file_name,
                "status": "failed",
                "error": str(exc),
                "total_pages": 0,
                "total_words": 0,
                "chunks_count": 0,
            })

    if any_success:
        chunker = DocumentChunker()
        all_chunks = chunker.create_chunks()

        bm25_builder = BM25IndexBuilder()
        bm25_builder.build_index()

        faiss_builder = FAISSIndexBuilder()
        faiss_builder.build_index()

        rag_service.reload_indexes()

        chunk_counts_by_doc = {}
        for c in all_chunks:
            d_name = c.get("document", "")
            chunk_counts_by_doc[d_name] = chunk_counts_by_doc.get(d_name, 0) + 1

        for r in results:
            if r["status"] == "ready":
                r["chunks_count"] = chunk_counts_by_doc.get(r["filename"], 0)

    successful = [r for r in results if r["status"] == "ready"]
    failed = [r for r in results if r["status"] == "failed"]

    return {
        "status": "completed" if not failed else ("partial_success" if successful else "failed"),
        "total": len(files),
        "successful": len(successful),
        "failed": len(failed),
        "results": results,
    }


@app.delete("/documents/{document_name}")
def delete_document(document_name: str, undo_window: float = 10.0):
    """Soft-delete a document with a 10-second undo window, removing chunks and indexes."""
    from app.services.document_service import soft_delete_document

    safe_name = Path(document_name).name
    try:
        result = soft_delete_document(safe_name, undo_window_seconds=undo_window)
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to delete document: %s", safe_name)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {exc}",
        ) from exc


@app.post("/documents/{document_name}/undo")
def undo_delete_document_endpoint(document_name: str):
    """Restore a soft-deleted document within the undo window."""
    from app.services.document_service import undo_delete_document

    safe_name = Path(document_name).name
    try:
        result = undo_delete_document(safe_name)
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to restore document: %s", safe_name)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restore document: {exc}",
        ) from exc


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
def query(request: QueryRequest):
    """Execute the complete UNKNOWN RAG pipeline."""

    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty.",
        )

    start_time = time.perf_counter()

    try:
        response = rag_service.query(request.query, document_names=request.document_names)
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

    try:
        from app.services.history_service import create_history_entry
        create_history_entry(
            user=active_user,
            workspace=active_user,
            document_ids=doc_filter or [],
            scope="document" if doc_filter else "collection",
            query=request.query,
            feature="query",
            result_snapshot=response.model_dump() if hasattr(response, "model_dump") else response.dict(),
        )
    except Exception:
        logger.exception("Failed to record query history")

    return response


@app.post(
    "/reason",
    response_model=ReasoningResponse,
)
def reason(request: ReasoningRequest):
    """Execute multi-step query decomposition and reasoning."""
    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty.",
        )
    start_time = time.perf_counter()
    try:
        result = rag_service.reason(request.query, document_names=request.document_names)
        sources = build_sources(result.get("sources", []))
        return ReasoningResponse(
            query=result["query"],
            subquestions=result.get("subquestions", []),
            answer=result["answer"],
            sources=sources,
        )
    except Exception as error:
        logger.exception("Reasoning endpoint failed.")
        raise HTTPException(
            status_code=500,
            detail=f"Reasoning analysis failed: {error}",
        ) from error
    finally:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(f"Reasoning request completed in {elapsed_ms} ms")


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
def verify_claim(request: ClaimVerificationRequest):
    """Verify a user-provided claim against indexed documents."""

    start_time = time.perf_counter()

    try:
        response = rag_service.verify_claim(request.claim, document_names=request.document_names)

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
def discover_concept(request: ConceptDiscoveryRequest):
    """Identify a technical concept from a natural-language description."""

    start_time = time.perf_counter()

    try:
        result = rag_service.discover_concept(request.description, document_names=request.document_names)

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
def contradictions(request: ContradictionRequest):
    """
    Detect conflicting claims across retrieved document evidence.
    """

    start_time = time.perf_counter()

    try:
        report = rag_service.find_contradictions(request.query, document_names=request.document_names)

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
def compare(request: ResearchComparisonRequest):
    if request.document_names and len(request.document_names) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 documents allowed for comparison or filtering.",
        )
    start_time = time.perf_counter()

    try:
        report = rag_service.compare_research(request.query, document_names=request.document_names)

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
def research_gaps(request: ResearchGapRequest):
    start_time = time.perf_counter()

    try:
        report = rag_service.find_research_gaps(request.query, document_names=request.document_names)  # type: ignore

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
def debate(request: DebateRequest):
    start_time = time.perf_counter()

    try:
        report = rag_service.run_debate(  # type: ignore
            query=request.query,
            position_a=request.position_a,
            position_b=request.position_b,
            document_names=request.document_names,
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
def knowledge_dna(request: KnowledgeDNARequest):
    start_time = time.perf_counter()

    try:
        report = rag_service.generate_knowledge_dna(
            query=request.query,
            document_names=request.document_names,
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
def knowledge_mind_map(request: KnowledgeMindMapRequest):
    start_time = time.perf_counter()

    try:
        report = rag_service.generate_knowledge_mind_map(  # type: ignore
            query=request.query,
            document_names=request.document_names,
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
    "/answer",
    response_model=AnswerResponse,
    responses={
        400: {"description": "Invalid query."},
        500: {"description": "Dual-retrieval failed."},
    },
)
def answer(request: AnswerRequest):
    """
    Dual-retrieval answer endpoint (Task A8).

    Retrieves evidence from user documents (respecting doc_only scope) and from
    live web connectors separately.  Produces:
      - doc_section: grounded paragraph with page/chunk citations
      - web_section: grounded paragraph with live URLs (retrieved_at set now)
      - comparison[]: per-sub-question pairs labelled agree/disagree/not_addressed
      - summary: max 3 sentences
      - detail: full combined answer

    When doc_only=True, connectors are never invoked.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    start_time = time.perf_counter()
    try:
        from app.rag.source_mode import resolve_source_mode
        doc_only_eff, names_eff = resolve_source_mode(
            getattr(request, "source_mode", None),
            request.doc_only,
            request.document_names,
        )
        result = rag_service.answer(
            query=request.query,
            document_names=names_eff,
            doc_only=doc_only_eff,
            scope=getattr(request, "scope", None),
        )
        return result
    except ValueError as error:
        logger.exception("Answer endpoint: invalid request.")
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.exception("Answer endpoint: unexpected failure.")
        raise HTTPException(status_code=500, detail="Dual-retrieval answer failed.") from error
    finally:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info("Answer endpoint completed in %.2f ms.", elapsed_ms)


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
def visual_answer(request: VisualAnswerRequest):
    start_time = time.perf_counter()

    try:
        result = rag_service.generate_visual_answer(
            query=request.query,
            document_names=request.document_names,
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


# ============================================================
# SINGLE-URL FRONTEND SPA SERVING
# ============================================================

import os

_FRONTEND_DIST_DIR = Path(
    os.getenv(
        "FRONTEND_DIST_DIR",
        str(Path(__file__).resolve().parents[2] / "frontend" / "dist"),
    )
)

if (_FRONTEND_DIST_DIR / "assets").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND_DIST_DIR / "assets")),
        name="frontend-assets",
    )







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
            explanation=res.get("explanation", "Research Assistant"),
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



# ============================================================
# HISTORY ENDPOINTS
# ============================================================


@app.get("/history")
def list_history(
    user: str | None = None,
    workspace: str | None = None,
    feature: str | None = None,
    document_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List and filter execution history records."""
    from app.services.history_service import list_history_entries
    return list_history_entries(
        user=user,
        workspace=workspace,
        feature=feature,
        document_id=document_id,
        limit=limit,
        offset=offset,
    )


@app.get("/history/{history_id}")
def get_history_item(history_id: str):
    """Open and retrieve a single history record."""
    from app.services.history_service import get_history_entry
    item = get_history_entry(history_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"History record '{history_id}' not found.")
    return item


@app.post("/history/{history_id}/rerun")
def rerun_history_item(history_id: str):
    """Rerun an existing history query and record the updated result."""
    from app.services.history_service import get_history_entry, create_history_entry
    item = get_history_entry(history_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"History record '{history_id}' not found.")

    query = item["query"]
    feature = item["feature"]
    doc_ids = item["document_ids"]

    try:
        if feature == "knowledge-dna":
            report = rag_service.generate_knowledge_dna(topic=query, document_names=doc_ids or None)
            snapshot = report.model_dump() if hasattr(report, "model_dump") else report.dict()
        elif feature == "knowledge-mind-map":
            report = rag_service.generate_knowledge_mind_map(topic=query, document_names=doc_ids or None)
            snapshot = report.model_dump() if hasattr(report, "model_dump") else report.dict()
        elif feature == "reason":
            snapshot = rag_service.reason(query, document_names=doc_ids or None)
        else:
            resp = rag_service.query(query, document_names=doc_ids or None)
            snapshot = resp.model_dump() if hasattr(resp, "model_dump") else resp.dict() if hasattr(resp, "dict") else resp

        new_record = create_history_entry(
            user=item["user"],
            workspace=item["workspace"],
            document_ids=doc_ids,
            scope=item["scope"],
            query=query,
            feature=feature,
            result_snapshot=snapshot,
        )
        return new_record
    except Exception as exc:
        logger.exception("Failed to rerun history item: %s", history_id)
        raise HTTPException(status_code=500, detail=f"Failed to rerun query: {exc}") from exc


@app.delete("/history/{history_id}")
def delete_single_history(history_id: str):
    """Delete a single history record."""
    from app.services.history_service import delete_history_entry
    success = delete_history_entry(history_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"History record '{history_id}' not found.")
    return {"status": "deleted", "id": history_id}


@app.delete("/history")
def clear_history(
    user: str | None = None,
    workspace: str | None = None,
):
    """Clear all history records or filtered by user/workspace."""
    from app.services.history_service import clear_history_entries
    count = clear_history_entries(user=user, workspace=workspace)
    return {"status": "cleared", "deleted_count": count}



# ===========================================================================
# Task P1-5: Concept Graph, Knowledge DNA, and Smart Router Endpoints
# ===========================================================================

@app.get("/documents/{document_name}/concept-graph", response_model=ConceptGraphResponse)
@app.get("/concept-graph/{document_name}", response_model=ConceptGraphResponse, include_in_schema=False)
def get_concept_graph(
    document_name: str,
    request: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
    x_user_id: str | None = Header(None),
):
    """
    Return concept graph (nodes, edges) extracted from chunks.
    Drops any unsupported nodes or edges. Caches per document.
    """
    from app.rag.document_eligibility import get_user_authorized_documents
    from app.services.smart_router_service import extract_concept_graph

    safe_name = Path(document_name).name
    active_user, _ = resolve_authenticated_workspace(
        request, authorization, x_session_token, x_user_id=x_user_id
    )
    authorized_docs = get_user_authorized_documents(active_user, include_test_docs=True)
    if safe_name not in authorized_docs:
        raise HTTPException(status_code=404, detail=f"Document '{safe_name}' not found")

    def _llm_fn(prompt: str, temperature: float = 0.0) -> str:
        resp = rag_service.llm.generate_grounded(prompt) if temperature == 0.0 else rag_service.llm.generate(prompt)
        if not resp.success:
            raise RuntimeError(resp.error or "LLM failed")
        return resp.answer

    try:
        data = extract_concept_graph(
            document_name=safe_name,
            llm_fn=_llm_fn,
            retriever=rag_service.retriever,
        )
        return ConceptGraphResponse(**data)
    except Exception as exc:
        logger.exception("Failed to extract concept graph for %s", safe_name)
        raise HTTPException(status_code=500, detail=f"Failed to extract concept graph: {exc}") from exc


@app.get("/documents/{document_name}/dna", response_model=DocumentDNAResponse)
@app.get("/dna/{document_name}", response_model=DocumentDNAResponse, include_in_schema=False)
def get_document_dna(document_name: str):
    """
    Return Knowledge DNA: concepts, entities, methods, claims, difficulty, novelty.
    Caches per document.
    """
    from app.services.smart_router_service import extract_knowledge_dna_for_doc

    safe_name = Path(document_name).name
    def _llm_fn(prompt: str, temperature: float = 0.0) -> str:
        resp = rag_service.llm.generate_grounded(prompt) if temperature == 0.0 else rag_service.llm.generate(prompt)
        if not resp.success:
            raise RuntimeError(resp.error or "LLM failed")
        return resp.answer

    try:
        data = extract_knowledge_dna_for_doc(
            document_name=safe_name,
            llm_fn=_llm_fn,
            retriever=rag_service.retriever,
        )
        return DocumentDNAResponse(**data)
    except Exception as exc:
        logger.exception("Failed to extract DNA for %s", safe_name)
        raise HTTPException(status_code=500, detail=f"Failed to extract DNA: {exc}") from exc


@app.post("/documents/dna/compare", response_model=DNACompareResponse)
@app.post("/dna/compare", response_model=DNACompareResponse, include_in_schema=False)
def compare_document_dna(request: DNACompareRequest):
    """Compare Knowledge DNA between two documents."""
    from app.services.smart_router_service import compare_two_document_dna

    def _llm_fn(prompt: str, temperature: float = 0.0) -> str:
        resp = rag_service.llm.generate_grounded(prompt) if temperature == 0.0 else rag_service.llm.generate(prompt)
        if not resp.success:
            raise RuntimeError(resp.error or "LLM failed")
        return resp.answer

    try:
        data = compare_two_document_dna(
            doc_a=request.document_a,
            doc_b=request.document_b,
            llm_fn=_llm_fn,
            retriever=rag_service.retriever,
        )
        return DNACompareResponse(**data)
    except Exception as exc:
        logger.exception("Failed to compare DNA: %s and %s", request.document_a, request.document_b)
        raise HTTPException(status_code=500, detail=f"Failed to compare DNA: {exc}") from exc


@app.post("/smart-query")
async def post_smart_query(
    request: SmartQueryRequest,
    http_request: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
    x_user_id: str | None = Header(None),
):
    """
    POST /smart-query:
    - Fuzzy match document names using rapidfuzz.
    - Detect feature keyword with synonym map and fallback classifier.
    - If a feature is found, run ONLY it.
    - Else (or if stream=True / run_all=True), stream progress events.
    - Return rewritten query and clarification options when ambiguous.
    """
    from app.rag.utils import list_supported_documents
    from app.services.smart_router_service import (
        smart_route_query,
        stream_run_all_features,
        extract_concept_graph,
        extract_knowledge_dna_for_doc,
    )
    from app.services.overview_service import generate_document_overview
    from app.rag.document_eligibility import get_user_authorized_documents

    active_user, _ = resolve_authenticated_workspace(
        http_request, authorization, x_session_token, x_user_id=x_user_id
    )
    authorized_docs = get_user_authorized_documents(active_user, include_test_docs=True)

    requested_ids = [Path(str(d)).name for d in (request.document_ids or [])]
    denied = [d for d in requested_ids if d not in authorized_docs]
    if denied:
        raise HTTPException(status_code=404, detail=f"Document '{denied[0]}' not found")

    docs = [
        d.name
        for d in list_supported_documents(settings.PAPERS_DIR)
        if d.name in authorized_docs
    ]
    
    routing = smart_route_query(
        text=request.text,
        document_ids=requested_ids or None,
        available_docs=docs,
        run_all=request.run_all or ("run all" in request.text.lower()),
    )

    def _llm_fn(prompt: str, temperature: float = 0.0) -> str:
        resp = rag_service.llm.generate_grounded(prompt) if temperature == 0.0 else rag_service.llm.generate(prompt)
        if not resp.success:
            raise RuntimeError(resp.error or "LLM failed")
        return resp.answer

    if request.stream or (routing["run_all"] and not routing["detected_feature"]):
        return StreamingResponse(
            stream_run_all_features(
                query=routing["rewritten_query"],
                document_names=routing["matched_documents"],
                rag_service=rag_service,
            ),
            media_type="text/event-stream",
        )

    detected = routing["detected_feature"]
    executed_result = None
    if detected:
        if detected in ("mindmap", "dna", "summary", "overview") and not routing["matched_documents"]:
            return SmartQueryResponse(
                original_query=routing["original_query"],
                rewritten_query=routing["rewritten_query"],
                matched_documents=[],
                detected_feature=detected,
                executed_feature=None,
                run_all=routing["run_all"],
                is_ambiguous=True,
                clarification_options=routing["clarification_options"],
                result={"error": "Select a document for this feature; none was matched."},
            )
        target_doc = routing["matched_documents"][0] if routing["matched_documents"] else ""
        if detected == "mindmap":
            executed_result = extract_concept_graph(target_doc, _llm_fn, rag_service.retriever) if target_doc else {}
        elif detected == "dna":
            executed_result = extract_knowledge_dna_for_doc(target_doc, _llm_fn, rag_service.retriever) if target_doc else {}
        elif detected in ("summary", "overview"):
            executed_result = generate_document_overview(target_doc, _llm_fn, rag_service.retriever) if target_doc else {}
        elif detected == "qa":
            qa_scope = routing["matched_documents"] or docs
            if not qa_scope:
                executed_result = {"error": "No accessible documents to answer from"}
            else:
                try:
                    ans = rag_service.query(routing["rewritten_query"], document_names=qa_scope)
                    executed_result = ans.model_dump() if hasattr(ans, "model_dump") else ans
                except Exception as exc:
                    executed_result = {"error": str(exc)}
        else:
            executed_result = {"status": "executed", "feature": detected, "target_documents": routing["matched_documents"]}

    return SmartQueryResponse(
        original_query=routing["original_query"],
        rewritten_query=routing["rewritten_query"],
        matched_documents=routing["matched_documents"],
        detected_feature=detected,
        executed_feature=detected,
        run_all=routing["run_all"],
        is_ambiguous=routing["is_ambiguous"],
        clarification_options=routing["clarification_options"],
        result=executed_result,
    )


@app.get("/smart-query/autocomplete", response_model=AutocompleteResponse)
@app.get("/autocomplete", response_model=AutocompleteResponse, include_in_schema=False)
def autocomplete_query(q: str = ""):
    """Autocomplete documents and features based on prefix."""
    from app.rag.utils import list_supported_documents
    from app.services.smart_router_service import autocomplete_smart_query

    docs = [d.name for d in list_supported_documents(settings.PAPERS_DIR)]
    result = autocomplete_smart_query(q, docs)
    return AutocompleteResponse(**result)



# ===========================================================================
# Task P2-1: User Feedback Endpoint
# ===========================================================================

@app.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest):
    """Log and store user feedback on answers."""
    from app.services.feedback_service import record_feedback

    record = record_feedback(
        query=request.query,
        answer=request.answer,
        sources=request.sources,
        feedback_type=request.feedback_type,
        comment=request.comment,
        user_id=request.user_id,
    )
    return FeedbackResponse(
        status="recorded",
        id=record["id"],
        feedback_type=record["feedback_type"],
        recorded_at=record["created_at"],
    )


@app.get("/feedback")
def list_feedback(user_id: str | None = None):
    """Retrieve logged feedback records."""
    from app.services.feedback_service import get_feedback_records

    return get_feedback_records(user_id=user_id)



# ===========================================================================
# Task P2-2: Export Endpoint (PDF, DOCX, Markdown, HTML, Image ZIP)
# ===========================================================================

@app.post("/export/{export_format}")
@app.post("/export")
def export_result(
    export_format: str = "pdf",
    request: ExportRequest = None,
):
    """
    Export query results in PDF, DOCX, Markdown, HTML, or Image ZIP format.
    Includes full text, headings, sources, confidence, and figures/tables placed beside passages.
    """
    from app.services.export_service import (
        export_result_pdf,
        export_result_docx,
        export_result_markdown,
        export_result_html,
        export_result_images_zip,
    )

    req_data = request.model_dump() if request else {}
    fmt = export_format.lower().strip()

    if fmt == "pdf":
        pdf_bytes = export_result_pdf(req_data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="unknown_report.pdf"'},
        )
    elif fmt in ("docx", "doc", "word"):
        docx_bytes = export_result_docx(req_data)
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": 'attachment; filename="unknown_report.docx"'},
        )
    elif fmt in ("markdown", "md"):
        md_text = export_result_markdown(req_data)
        return Response(
            content=md_text.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="unknown_report.md"'},
        )
    elif fmt in ("html", "htm"):
        html_text = export_result_html(req_data)
        return Response(
            content=html_text.encode("utf-8"),
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="unknown_report.html"'},
        )
    elif fmt in ("zip", "images", "images-zip", "image-zip"):
        zip_bytes = export_result_images_zip(req_data)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="unknown_figures.zip"'},
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{export_format}'. Supported formats: pdf, docx, markdown, html, zip",
        )




# ===========================================================================
# Task Phase 3: Secure Conversation Sharing Endpoints
# ===========================================================================

@app.post("/share")
def create_share_link(
    payload: dict,
    request: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
    x_user_id: str | None = Header(None),
):
    """Create a revocable, read-only share link for a conversation."""
    active_user, _ = resolve_authenticated_workspace(
        request, authorization, x_session_token, x_user_id=x_user_id
    )
    from app.services.share_service import create_share

    conv = payload.get("conversation", {})
    include_docs = payload.get("include_doc_content", False)
    expires = payload.get("expires_in_hours", 72)
    return create_share(
        active_user,
        conv,
        include_doc_content=include_docs,
        expires_in_hours=expires,
    )


@app.get("/share/{token}")
def get_shared_conversation_link(token: str):
    """Retrieve a shared conversation using its secure token."""
    from app.services.share_service import get_shared

    data = get_shared(token)
    if not data:
        raise HTTPException(
            status_code=404,
            detail="Shared conversation not found, expired, or revoked.",
        )
    return data


@app.delete("/share/{token}")
def revoke_shared_conversation_link(
    token: str,
    request: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
    x_user_id: str | None = Header(None),
):
    """Revoke a shared conversation link."""
    active_user, _ = resolve_authenticated_workspace(
        request, authorization, x_session_token, x_user_id=x_user_id
    )
    from app.services.share_service import revoke_share

    success = revoke_share(token, active_user)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Share token not found or unauthorized.",
        )
    return {"status": "revoked", "token": token}


@app.get("/", include_in_schema=False)
async def serve_root():
    """Serve the frontend SPA directly on the root URL."""
    index_file = _FRONTEND_DIST_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(str(index_file))
    return {
        "status": "healthy",
        "service": "UNKNOWN AI",
        "version": "1.0.0",
    }


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa_fallback(full_path: str):
    """Client-side routing fallback for the single-page application."""
    if full_path.startswith("api/") or full_path in ("docs", "redoc", "openapi.json"):
        raise HTTPException(status_code=404, detail="Not Found")

    target_file = _FRONTEND_DIST_DIR / full_path
    if target_file.is_file():
        return FileResponse(str(target_file))

    index_file = _FRONTEND_DIST_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(str(index_file))

    raise HTTPException(status_code=404, detail="Not Found")
