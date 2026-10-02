"""
UNKNOWN Project - FastAPI Application

Exposes the verified UNKNOWN RAG pipeline through HTTP APIs.
"""

import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.schemas import QueryRequest, QueryResponse
from app.rag.logger import logger
from app.services.rag_service import RAGService

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
    allow_origins=["*"],
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
# QUERY ENDPOINT
# ============================================================


@app.post(
    "/query",
    response_model=QueryResponse,
    responses={
        429: {
            "description": "LLM provider quota or rate limit exceeded.",
        },
        500: {
            "description": "Unexpected query processing failure.",
        },
    },
)
def query(request: QueryRequest):
    """Execute the complete UNKNOWN RAG pipeline."""

    start_time = time.perf_counter()

    try:
        response = rag_service.query(request.query)
    except RuntimeError as error:
        logger.exception(f"Query processing failed: {error}")

        error_message = str(error)

        if "429" in error_message or "RESOURCE_EXHAUSTED" in error_message:
            raise HTTPException(
                status_code=429,
                detail="LLM provider quota or rate limit exceeded. Please try again later.",
            )

        raise HTTPException(
            status_code=500,
            detail="Unable to process the query at the moment.",
        )
    except Exception as error:  # noqa: BLE001
        logger.exception(f"Unexpected query processing failure: {error}")

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
