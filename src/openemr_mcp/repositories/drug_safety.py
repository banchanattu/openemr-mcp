"""
Drug Safety Flag repository — SQLite-backed CRUD for patient-specific drug safety alerts.

Storage: SQLite (no external dependencies; works in mock mode and production).
         Database file: ~/.openemr_mcp/drug_safety_flags.db (created automatically).
         Falls back to in-memory store when filesystem is read-only.
"""

import atexit
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from openemr_mcp.schemas import (
    DrugSafetyFlag,
    DrugSafetyFlagCreate,
    DrugSafetyFlagListResponse,
    DrugSafetyFlagUpdate,
)

_log = logging.getLogger("openemr_mcp")

_DB_DIR = Path.home() / ".openemr_mcp"
_DB_PATH = _DB_DIR / "drug_safety_flags.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS drug_safety_flags (
    id          TEXT PRIMARY KEY,
    patient_id  TEXT NOT NULL,
    drug_name   TEXT NOT NULL,
    flag_type   TEXT NOT NULL DEFAULT 'adverse_event',
    severity    TEXT NOT NULL DEFAULT 'MODERATE',
    source      TEXT NOT NULL DEFAULT 'AGENT',
    description TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    created_by  TEXT NOT NULL DEFAULT 'agent'
);
CREATE INDEX IF NOT EXISTS idx_patient_id ON drug_safety_flags (patient_id);
CREATE INDEX IF NOT EXISTS idx_drug_name  ON drug_safety_flags (drug_name);
CREATE INDEX IF NOT EXISTS idx_status     ON drug_safety_flags (status);
"""


def _get_connection() -> sqlite3.Connection:
    try:
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_DB_PATH))
    except OSError:
        _log.warning("Cannot write to %s — using in-memory SQLite", _DB_PATH)
        conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return _track_connection(conn)


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_CREATE_TABLE_SQL)
    conn.commit()


_conn: sqlite3.Connection | None = None
_open_connections: list[sqlite3.Connection] = []


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _get_connection()
        _init_db(_conn)
    return _conn


def _track_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
    _open_connections.append(conn)
    return conn


def close_db() -> None:
    """Close all cached SQLite connections and clear module state."""
    global _conn
    seen: set[int] = set()
    for conn in [*_open_connections, _conn]:
        if conn is None:
            continue
        conn_id = id(conn)
        if conn_id in seen:
            continue
        seen.add(conn_id)
        try:
            conn.close()
        except Exception:
            pass
    _open_connections.clear()
    _conn = None


atexit.register(close_db)


def reset_for_tests() -> None:
    """Drop and recreate the table. Used by test fixtures to ensure isolation."""
    global _conn
    if _conn:
        _conn.execute("DROP TABLE IF EXISTS drug_safety_flags")
        _conn.commit()
        _init_db(_conn)
    else:
        _conn = _get_connection()
        _init_db(_conn)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_flag(row: sqlite3.Row) -> DrugSafetyFlag:
    return DrugSafetyFlag(
        id=row["id"],
        patient_id=row["patient_id"],
        drug_name=row["drug_name"],
        flag_type=row["flag_type"],
        severity=row["severity"],
        source=row["source"],
        description=row["description"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        created_by=row["created_by"],
    )


def create_flag(payload: DrugSafetyFlagCreate) -> DrugSafetyFlag:
    """Create a new drug safety flag for a patient. Returns the created flag."""
    now = _now_iso()
    flag_id = str(uuid.uuid4())
    db = _db()
    db.execute(
        """
        INSERT INTO drug_safety_flags
            (id, patient_id, drug_name, flag_type, severity, source,
             description, status, created_at, updated_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
        """,
        (
            flag_id,
            payload.patient_id,
            payload.drug_name,
            payload.flag_type,
            payload.severity,
            payload.source,
            payload.description,
            now,
            now,
            payload.created_by,
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM drug_safety_flags WHERE id = ?", (flag_id,)).fetchone()
    return _row_to_flag(row)


def get_flags(patient_id: str, status_filter: str | None = None) -> DrugSafetyFlagListResponse:
    """Return all drug safety flags for a patient."""
    db = _db()
    if status_filter:
        rows = db.execute(
            "SELECT * FROM drug_safety_flags WHERE patient_id = ? AND status = ? ORDER BY created_at DESC",
            (patient_id, status_filter),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM drug_safety_flags WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()
    flags = [_row_to_flag(r) for r in rows]
    active_count = sum(1 for f in flags if f.status == "active")
    high_severity_count = sum(1 for f in flags if f.severity == "HIGH" and f.status == "active")
    return DrugSafetyFlagListResponse(
        patient_id=patient_id,
        flags=flags,
        active_count=active_count,
        high_severity_count=high_severity_count,
    )


def get_flag_by_id(flag_id: str) -> DrugSafetyFlag | None:
    """Return a single flag by its ID, or None if not found."""
    row = _db().execute("SELECT * FROM drug_safety_flags WHERE id = ?", (flag_id,)).fetchone()
    return _row_to_flag(row) if row else None


def update_flag(flag_id: str, payload: DrugSafetyFlagUpdate) -> DrugSafetyFlag | None:
    """Update a flag's severity, description, or status."""
    existing = get_flag_by_id(flag_id)
    if existing is None:
        return None
    updates: dict = {}
    if payload.severity is not None:
        updates["severity"] = payload.severity
    if payload.description is not None:
        updates["description"] = payload.description
    if payload.status is not None:
        updates["status"] = payload.status
    if not updates:
        return existing
    now = _now_iso()
    updates["updated_at"] = now
    set_clause = ", ".join(f"{col} = ?" for col in updates)
    values = list(updates.values()) + [flag_id]
    db = _db()
    db.execute(f"UPDATE drug_safety_flags SET {set_clause} WHERE id = ?", values)
    db.commit()
    return get_flag_by_id(flag_id)


def delete_flag(flag_id: str) -> bool:
    """Delete a drug safety flag by ID. Returns True if deleted."""
    db = _db()
    cursor = db.execute("DELETE FROM drug_safety_flags WHERE id = ?", (flag_id,))
    db.commit()
    return cursor.rowcount > 0
