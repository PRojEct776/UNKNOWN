"""
UNKNOWN Project - FastAPI Application

Exposes the verified UNKNOWN RAG pipeline through HTTP APIs.
"""

import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.schemas import (
    ClaimVerificationRequest,
    ClaimVerificationResponse,
    ContradictionRequest,
    ContradictionResponse,
    DebateRequest,
    DebateResponse,
    QueryRequest,
    QueryResponse,
    ResearchComparisonRequest,
    ResearchComparisonResponse,
    ResearchGapRequest,
    ResearchGapResponse,
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

    start_time = time.perf_counter()

    try:
        response = rag_service.query(request.query)
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
def verify_claim(request: ClaimVerificationRequest):
    """Verify a user-provided claim against indexed documents."""

    start_time = time.perf_counter()

    try:
        response = rag_service.verify_claim(request.claim)

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
    "/contradictions",
    response_model=ContradictionResponse,
)
def contradictions(request: ContradictionRequest):
    """
    Detect conflicting claims across retrieved document evidence.
    """

    start_time = time.perf_counter()

    try:
        report = rag_service.find_contradictions(request.query)

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
        report = rag_service.compare_research(request.query)

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
        report = rag_service.find_research_gaps(request.query)  # type: ignore

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
