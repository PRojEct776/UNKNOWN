"""
UNKNOWN X – Feedback Service (Task P2-1)
Logs and persists user feedback (thumbs up, thumbs down, report wrong answer)
including the query, answer, and retrieved sources.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.rag.config import settings
from app.rag.logger import logger

FEEDBACK_FILE = settings.CACHE_DIR / "feedback.json"


def record_feedback(
    query: str,
    answer: str,
    sources: list[dict[str, Any] | Any],
    feedback_type: str = "thumbs_up",
    comment: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Log and persist a feedback record.
    """
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    if FEEDBACK_FILE.exists():
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception as exc:
            logger.warning("Could not read feedback file: %s", exc)
            records = []

    # Clean sources to serializable dicts
    clean_sources: list[dict[str, Any]] = []
    for s in sources:
        if isinstance(s, dict):
            clean_sources.append(s)
        elif hasattr(s, "model_dump"):
            clean_sources.append(s.model_dump())
        elif hasattr(s, "__dict__"):
            clean_sources.append(s.__dict__)
        else:
            clean_sources.append({"raw": str(s)})

    record_id = f"fb_{uuid.uuid4().hex[:12]}"
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    new_record = {
        "id": record_id,
        "query": query,
        "answer": answer,
        "sources": clean_sources,
        "feedback_type": feedback_type,
        "comment": comment or "",
        "user_id": user_id or "anonymous",
        "created_at": created_at,
    }

    records.append(new_record)

    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    logger.info("Feedback recorded: %s (type=%s, query=%s)", record_id, feedback_type, query[:40])
    return new_record


def get_feedback_records(user_id: str | None = None) -> list[dict[str, Any]]:
    """Retrieve stored feedback records."""
    if not FEEDBACK_FILE.exists():
        return []
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            records = json.load(f)
            if user_id:
                return [r for r in records if r.get("user_id") == user_id]
            return records
    except Exception as exc:
        logger.warning("Could not read feedback file: %s", exc)
        return []
