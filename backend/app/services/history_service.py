"""
History Database Service for UNKNOWN RAG

Manages persistent query and feature execution history using SQLite.
Table schema:
{id, user, workspace, document_ids, scope, query, feature, result_snapshot, created_at}
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.rag.config import settings
from app.rag.logger import logger

DB_PATH = settings.BASE_DIR / "app" / "data" / "history.db"


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the history SQLite table and indexes."""
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id TEXT PRIMARY KEY,
                user TEXT NOT NULL,
                workspace TEXT NOT NULL,
                document_ids TEXT NOT NULL,
                scope TEXT NOT NULL,
                query TEXT NOT NULL,
                feature TEXT NOT NULL,
                result_snapshot TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON history(user);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_workspace ON history(workspace);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_feature ON history(feature);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_created_at ON history(created_at);")
        conn.commit()


# Auto-init on module import
init_db()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    raw_doc_ids = row["document_ids"]
    try:
        doc_ids = json.loads(raw_doc_ids) if raw_doc_ids else []
    except Exception:
        doc_ids = [raw_doc_ids] if raw_doc_ids else []

    raw_snapshot = row["result_snapshot"]
    try:
        snapshot = json.loads(raw_snapshot) if raw_snapshot else {}
    except Exception:
        snapshot = {"raw": raw_snapshot}

    return {
        "id": row["id"],
        "user": row["user"],
        "workspace": row["workspace"],
        "document_ids": doc_ids,
        "scope": row["scope"],
        "query": row["query"],
        "feature": row["feature"],
        "result_snapshot": snapshot,
        "created_at": row["created_at"],
    }


def create_history_entry(
    user: str = "default_user",
    workspace: str = "default_workspace",
    document_ids: Optional[list[str]] = None,
    scope: str = "collection",
    query: str = "",
    feature: str = "query",
    result_snapshot: Optional[Any] = None,
    entry_id: Optional[str] = None,
) -> dict[str, Any]:
    """Insert a new history record and return it."""
    record_id = entry_id or str(uuid.uuid4())
    doc_ids_list = document_ids if isinstance(document_ids, list) else ([document_ids] if document_ids else [])
    doc_ids_json = json.dumps(doc_ids_list)
    created_at = datetime.now(timezone.utc).isoformat()

    snapshot_json = json.dumps(result_snapshot or {}, default=str)

    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO history (id, user, workspace, document_ids, scope, query, feature, result_snapshot, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                user or "default_user",
                workspace or "default_workspace",
                doc_ids_json,
                scope or "collection",
                query or "",
                feature or "query",
                snapshot_json,
                created_at,
            ),
        )
        conn.commit()

    return {
        "id": record_id,
        "user": user or "default_user",
        "workspace": workspace or "default_workspace",
        "document_ids": doc_ids_list,
        "scope": scope or "collection",
        "query": query or "",
        "feature": feature or "query",
        "result_snapshot": result_snapshot or {},
        "created_at": created_at,
    }


def list_history_entries(
    user: Optional[str] = None,
    workspace: Optional[str] = None,
    feature: Optional[str] = None,
    document_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List and filter history records ordered by created_at DESC."""
    query = "SELECT * FROM history WHERE 1=1"
    params: list[Any] = []

    if user:
        query += " AND user = ?"
        params.append(user)
    if workspace:
        query += " AND workspace = ?"
        params.append(workspace)
    if feature:
        query += " AND feature = ?"
        params.append(feature)

    query += " ORDER BY created_at DESC"

    with _get_connection() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    items = [_row_to_dict(r) for r in rows]

    # In-memory document_id filter for precision with JSON list
    if document_id:
        doc_name = Path(document_id).name
        stem = Path(doc_name).stem
        items = [
            item for item in items
            if any(doc_name == d or stem == Path(d).stem for d in item["document_ids"])
        ]

    return items[offset : offset + limit]


def get_history_entry(history_id: str) -> Optional[dict[str, Any]]:
    """Get a single history record by ID."""
    with _get_connection() as conn:
        cursor = conn.execute("SELECT * FROM history WHERE id = ?", (history_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return _row_to_dict(row)


def delete_history_entry(history_id: str) -> bool:
    """Delete a history record by ID. Returns True if found and deleted."""
    with _get_connection() as conn:
        cursor = conn.execute("DELETE FROM history WHERE id = ?", (history_id,))
        conn.commit()
        return cursor.rowcount > 0


def clear_history_entries(
    user: Optional[str] = None,
    workspace: Optional[str] = None,
) -> int:
    """Clear all history records, optionally filtered by user and workspace."""
    query = "DELETE FROM history WHERE 1=1"
    params: list[Any] = []
    if user:
        query += " AND user = ?"
        params.append(user)
    if workspace:
        query += " AND workspace = ?"
        params.append(workspace)

    with _get_connection() as conn:
        cursor = conn.execute(query, params)
        conn.commit()
        return cursor.rowcount


def delete_history_for_document(document_name: str) -> int:
    """
    Delete history records that are tied *only* to this document.
    Does not delete multi-document queries or general collection queries.
    """
    safe_name = Path(document_name).name
    stem = Path(safe_name).stem

    with _get_connection() as conn:
        cursor = conn.execute("SELECT id, document_ids FROM history")
        rows = cursor.fetchall()

        ids_to_delete = []
        for row in rows:
            raw = row["document_ids"]
            try:
                doc_ids = json.loads(raw) if raw else []
            except Exception:
                doc_ids = [raw] if raw else []

            # Check if tied ONLY to this document
            if len(doc_ids) == 1:
                single_doc = doc_ids[0]
                if single_doc == safe_name or Path(single_doc).name == safe_name or Path(single_doc).stem == stem:
                    ids_to_delete.append(row["id"])

        if not ids_to_delete:
            return 0

        placeholders = ",".join("?" for _ in ids_to_delete)
        del_cursor = conn.execute(f"DELETE FROM history WHERE id IN ({placeholders})", ids_to_delete)
        conn.commit()
        logger.info(f"Purged {del_cursor.rowcount} history records tied solely to document {safe_name}")
        return del_cursor.rowcount
