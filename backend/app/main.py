"""
UNKNOWN Project - FastAPI Application

Exposes the verified UNKNOWN RAG pipeline through HTTP APIs.
"""

import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
# DOCUMENT MANAGEMENT ENDPOINTS
# ============================================================


@app.get("/documents")
def list_documents():
    """List indexed research documents."""
    from app.rag.utils import list_supported_documents
    from app.services.document_service import (
        count_document_chunks,
        load_document_json,
    )

    documents = []
    for paper_path in list_supported_documents(settings.PAPERS_DIR):
        doc_name = paper_path.name
        try:
            doc_data = load_document_json(doc_name)
            chunks = count_document_chunks(doc_name)
            documents.append(
                {
                    "name": doc_name,
                    "title": doc_data.get("title", doc_name),
                    "document_type": doc_data.get("document_type", paper_path.suffix),
                    "total_pages": doc_data.get("total_pages", 1),
                    "total_words": doc_data.get("total_words", 0),
                    "chunks_count": chunks,
                    "status": "indexed",
                }
            )
        except Exception:
            documents.append(
                {
                    "name": doc_name,
                    "title": doc_name,
                    "document_type": paper_path.suffix,
                    "total_pages": 1,
                    "total_words": 0,
                    "chunks_count": 0,
                    "status": "stored",
                }
            )

    return {"documents": documents, "total": len(documents)}


@app.get("/documents/{document_name}")
def get_document_detail(document_name: str):
    """Retrieve metadata and parsed text preview of an indexed paper."""
    from app.services.document_service import (
        count_document_chunks,
        load_document_json,
    )

    safe_name = Path(document_name).name
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


@app.get("/documents/download/{document_name}")
def download_document(document_name: str):
    """Serve or download the original research paper file."""
    safe_name = Path(document_name).name
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
async def upload_document(file: UploadFile = File(...)):
    """Upload a research document (.pdf, .docx, .txt) and index it."""
    from app.rag.document_loader import DocumentLoader
    from app.rag.utils import list_supported_documents

    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in settings.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{file_ext}'. Supported: {settings.SUPPORTED_EXTENSIONS}",
        )

    file_name = Path(file.filename or "upload").name
    save_path = settings.PAPERS_DIR / file_name

    existing_docs = list_supported_documents(settings.PAPERS_DIR)
    existing_names = {d.name for d in existing_docs}
    if len(existing_docs) >= settings.MAX_COLLECTION_PAPERS and file_name not in existing_names:
        raise HTTPException(
            status_code=400,
            detail=f"Collection limit of {settings.MAX_COLLECTION_PAPERS} papers reached. Please delete a paper before uploading another.",
        )

    try:
        content = await file.read()
        if len(content) > settings.MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
            )

        with open(save_path, "wb") as f:
            f.write(content)

        loader = DocumentLoader()
        doc_json = loader.create_document_json(save_path)
        loader.save_document_json(doc_json)

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

    existing_docs = list_supported_documents(settings.PAPERS_DIR)
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
def delete_document(document_name: str):
    """Delete a research paper and remove it from the retrieval index."""
    safe_name = Path(document_name).name
    paper_path = settings.PAPERS_DIR / safe_name

    if not paper_path.exists() or not paper_path.is_file():
        raise HTTPException(
            status_code=404, detail=f"Document '{safe_name}' not found"
        )

    try:
        # 1. Remove original paper file
        paper_path.unlink(missing_ok=True)

        # 2. Remove extracted JSON
        json_path = settings.JSON_DIR / f"{paper_path.stem}.json"
        json_path.unlink(missing_ok=True)

        # 3. Remove metadata report
        metadata_path = settings.BASE_DIR / "app" / "data" / "metadata" / f"{paper_path.stem}_metadata.json"
        metadata_path.unlink(missing_ok=True)

        # 4. Re-chunk remaining documents
        from app.rag.chunker import DocumentChunker
        from app.rag.bm25_index_builder import BM25IndexBuilder
        from app.rag.faiss_index_builder import FAISSIndexBuilder

        chunker = DocumentChunker()
        all_chunks = chunker.create_chunks()

        # 5. Re-build BM25 & FAISS indexes
        bm25_builder = BM25IndexBuilder()
        bm25_builder.build_index()

        faiss_builder = FAISSIndexBuilder()
        faiss_builder.build_index()

        # 6. Reload in-memory indexes
        rag_service.reload_indexes()

        return {
            "status": "deleted",
            "document_name": safe_name,
            "remaining_chunks": len(all_chunks),
            "message": f"Successfully deleted {safe_name} and rebuilt retrieval indexes.",
        }
    except Exception as exc:
        logger.exception("Failed to delete document: %s", safe_name)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {exc}",
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
        sources = [
            Source(
                rank=s.get("rank", idx),
                document=s.get("document", "Unknown"),
                page=s.get("page", 1),
                chunk_id=s.get("chunk_id", f"chunk_{idx}"),
                hybrid_score=float(s.get("hybrid_score", 0.0)),
                bm25_score=float(s.get("bm25_score", 0.0)),
                faiss_score=float(s.get("faiss_score", 0.0)),
            )
            for idx, s in enumerate(result.get("sources", []), start=1)
        ]
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
