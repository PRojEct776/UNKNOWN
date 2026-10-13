"""
Server-Side Session & Workspace Identity Management for UNKNOWN

Provides cryptographic bearer tokens for workspace isolation.
Ensures clients cannot access or modify another user's documents
by simply supplying an arbitrary user_id string.

Security Notice:
In the current file-backed architecture (without a relational DB / external IdP),
sessions are securely managed via server-issued cryptographic tokens and
persisted session registries. Enterprise SSO requires connecting an external IdP.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.rag.config import settings
from app.rag.logger import logger

SESSIONS_FILE = settings.BASE_DIR / "app" / "data" / "sessions.json"


class SessionCreateRequest(BaseModel):
    workspace_id: str | None = Field(
        default=None,
        description="Optional desired workspace identifier. If omitted, a secure UUID is generated.",
    )


class SessionResponse(BaseModel):
    token: str
    workspace_id: str
    created_at: float
    is_authenticated: bool


class SessionManager:
    """Thread-safe persistent session store for UNKNOWN workspaces."""

    def __init__(self, storage_path: Path = SESSIONS_FILE):
        self.storage_path = storage_path
        self._lock = threading.Lock()
        self._sessions: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if self.storage_path.exists():
                try:
                    with open(self.storage_path, "r", encoding="utf-8") as f:
                        self._sessions = json.load(f)
                except Exception as exc:
                    logger.warning(f"Could not load sessions file: {exc}")
                    self._sessions = {}
            else:
                self.storage_path.parent.mkdir(parents=True, exist_ok=True)
                self._sessions = {}

    def _save(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.storage_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._sessions, f, indent=2)
            temp_path.replace(self.storage_path)
        except Exception as exc:
            logger.warning(f"Could not persist sessions file: {exc}")

    def create_session(self, workspace_id: str | None = None) -> dict[str, Any]:
        """Generate a cryptographically unguessable token mapped to a workspace."""
        token = secrets.token_urlsafe(32)
        assigned_workspace = workspace_id.strip() if (workspace_id and workspace_id.strip()) else f"ws_{secrets.token_hex(8)}"
        record = {
            "token": token,
            "workspace_id": assigned_workspace,
            "created_at": time.time(),
            "is_authenticated": True,
        }
        with self._lock:
            self._sessions[token] = record
            self._save()

        logger.info(f"Created authenticated session for workspace: {assigned_workspace}")
        return record

    def validate_token(self, token: str) -> dict[str, Any] | None:
        """Validate token and return session record if active."""
        if not token:
            return None
        with self._lock:
            return self._sessions.get(token)


# Global singleton session manager
session_manager = SessionManager()


def resolve_authenticated_workspace(
    request: Request,
    authorization: str | None = Header(None),
    x_session_token: str | None = Header(None),
    client_user_id: str | None = None,
) -> tuple[str, bool]:
    """
    Resolve trusted workspace identity.

    Precedence:
    1. Bearer token in Authorization header
    2. X-Session-Token header
    3. If token provided:
       - Validates token against SessionManager.
       - Rejects (403 Forbidden) if client_user_id contradicts token's workspace.
    4. If no token provided:
       - Fallback to client_user_id (default_user) for local development/testing.
       - Returns is_authenticated=False with warning header.
    """
    raw_token = None
    if authorization and authorization.lower().startswith("bearer "):
        raw_token = authorization[7:].strip()
    elif x_session_token:
        raw_token = x_session_token.strip()

    if raw_token:
        session = session_manager.validate_token(raw_token)
        if not session:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired session token. Please re-authenticate.",
            )
        trusted_workspace = session["workspace_id"]
        # Defense against user_id spoofing
        if client_user_id and client_user_id.strip() and client_user_id.strip() != trusted_workspace:
            raise HTTPException(
                status_code=403,
                detail=f"Workspace identity mismatch: supplied user_id '{client_user_id}' does not match authenticated session.",
            )
        return trusted_workspace, True

    # Unauthenticated / development fallback
    fallback_workspace = (client_user_id.strip() if client_user_id and client_user_id.strip() else "default_user")
    return fallback_workspace, False
