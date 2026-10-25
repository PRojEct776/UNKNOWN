# =============================================================================
# Stage 1: Build Frontend Single-Page Application (SPA)
# =============================================================================
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# =============================================================================
# Stage 2: Production Python Backend + Pre-downloaded ML Models + Static Assets
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/cache/sentence_transformers \
    PYTHONPATH=/app/backend

# Install OS dependencies for PyMuPDF, ReportLab fonts, and curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    fonts-dejavu \
    fonts-indic \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Pre-install spaCy language model
RUN python -m spacy download en_core_web_sm

# Copy scripts and pre-download all ML models into image cache during build
COPY scripts/ /app/scripts/
COPY backend/scripts/ /app/backend/scripts/
RUN python scripts/download_models.py

# Copy backend application source and datasets
COPY backend/app /app/backend/app
COPY backend/datasets /app/backend/datasets
COPY backend/vector_store /app/backend/vector_store
COPY backend/pytest.ini /app/backend/pytest.ini

# Copy built frontend production dist
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

# Setup non-root appuser and writable directories
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/backend/logs /app/backend/app/data/cache /app/backend/app/data/metadata /app/cache \
    && chown -R appuser:appuser /app

USER appuser

WORKDIR /app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
