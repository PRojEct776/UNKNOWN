"""
UNKNOWN Research Platform — Secure Conversation Sharing Service

Generates cryptographically secure, revocable share tokens for conversations.
Enforces strict sanitization to prevent leaking server paths, credentials, or private metadata.
"""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import Any, Dict, Optional

from app.rag.config import settings

SHARES_DIR = settings.BASE_DIR / "app" / "data" / "shares"


def _ensure_shares_dir() -> Path:
    SHARES_DIR.mkdir(parents=True, exist_ok=True)
    return SHARES_DIR


def sanitize_conversation_for_sharing(
    conversation: Dict[str, Any],
    include_doc_content: bool = False,
) -> Dict[str, Any]:
    """Strip internal server paths, credentials, and sensitive metadata from conversation."""
    sanitized: Dict[str, Any] = {
        "title": conversation.get("title", "Shared Research Conversation"),
        "createdAt": conversation.get("createdAt", ""),
        "messages": [],
    }

    for msg in conversation.get("messages", []):
        s_msg: Dict[str, Any] = {
            "id": msg.get("id"),
            "sender": msg.get("sender"),
            "timestamp": msg.get("timestamp"),
            "text": msg.get("text"),
            "feature": msg.get("feature"),
        }

        if msg.get("sender") == "overview" and msg.get("overview"):
            ov = msg["overview"]
            s_msg["overview"] = {
                "title": ov.get("title", "Document Overview"),
                "executive_summary": ov.get("executive_summary"),
                "main_findings": ov.get("main_findings"),
                "methods_and_investigations": ov.get("methods_and_investigations"),
                "questions_it_can_answer": ov.get("questions_it_can_answer"),
                "document_iq": ov.get("document_iq"),
            }

        if msg.get("result"):
            res = msg["result"]
            s_res: Dict[str, Any] = {
                "answer": res.get("answer", ""),
                "detailedAnswer": res.get("detailedAnswer", ""),
                "confidence": res.get("confidence"),
                "doc_section": res.get("doc_section"),
                "web_section": res.get("web_section"),
                "sources": [],
            }
            # Sanitize sources
            for src in res.get("sources", []):
                s_res["sources"].append({
                    "title": src.get("title") or src.get("name") or "Source",
                    "page": src.get("page"),
                    "domain": src.get("domain"),
                    "url": src.get("url"),
                })
            s_msg["result"] = s_res

        sanitized["messages"].append(s_msg)

    return sanitized


def create_share(
    user_id: str,
    conversation_data: Dict[str, Any],
    include_doc_content: bool = False,
    expires_in_hours: int = 72,
) -> Dict[str, Any]:
    """Create a new revocable share token with optional expiry."""
    dir_path = _ensure_shares_dir()
    token = secrets.token_urlsafe(32)
    created_at = time.time()
    expires_at = created_at + (expires_in_hours * 3600) if expires_in_hours > 0 else None

    sanitized_data = sanitize_conversation_for_sharing(
        conversation_data,
        include_doc_content=include_doc_content,
    )

    record = {
        "token": token,
        "owner_user_id": user_id,
        "created_at": created_at,
        "expires_at": expires_at,
        "is_active": True,
        "conversation": sanitized_data,
    }

    file_path = dir_path / f"{token}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    return {
        "share_token": token,
        "share_url": f"/shared/{token}",
        "expires_at": expires_at,
        "is_active": True,
    }


def get_shared(token: str) -> Optional[Dict[str, Any]]:
    """Retrieve shared conversation if token is valid, active, and unexpired."""
    dir_path = _ensure_shares_dir()
    safe_token = Path(token).name
    file_path = dir_path / f"{safe_token}.json"

    if not file_path.exists():
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            record = json.load(f)

        if not record.get("is_active", False):
            return None

        expires_at = record.get("expires_at")
        if expires_at and time.time() > expires_at:
            return None

        return record.get("conversation")
    except Exception:
        return None


def revoke_share(token: str, user_id: str) -> bool:
    """Revoke a share link so it can no longer be accessed."""
    dir_path = _ensure_shares_dir()
    safe_token = Path(token).name
    file_path = dir_path / f"{safe_token}.json"

    if not file_path.exists():
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            record = json.load(f)

        if record.get("owner_user_id") != user_id:
            return False

        record["is_active"] = False
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)

        return True
    except Exception:
        return False
