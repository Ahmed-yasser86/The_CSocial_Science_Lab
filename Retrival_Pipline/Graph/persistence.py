"""SQLite persistence + external file storage for intelligence runs.

Sessions, reports, sources, and step snapshots are stored in a SQLite database
located in an external data directory (outside the code repository) so that
runs can be resumed and inspected later.

Override locations via environment variables:
    INTEL_DATA_DIR  - directory where runs/ and the DB live (default: <workspace>/intelligence_data)
    INTEL_DB_PATH   - explicit path to the SQLite file (overrides INTEL_DATA_DIR)
"""
import os
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_DATA_DIR = os.environ.get("INTEL_DATA_DIR", os.path.join(WORKSPACE_ROOT, "intelligence_data"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id                TEXT PRIMARY KEY,
    subject           TEXT,
    thread_id         TEXT,
    status            TEXT DEFAULT 'running',
    report_plan       TEXT,
    completed_reports TEXT DEFAULT '[]',
    run_folder        TEXT,
    created_at        TEXT,
    updated_at        TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT,
    report_type   TEXT,
    path          TEXT,
    summary       TEXT,
    sources_count INTEGER DEFAULT 0,
    costs         REAL DEFAULT 0,
    completed     INTEGER DEFAULT 1,
    created_at    TEXT
);

CREATE TABLE IF NOT EXISTS sources (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id  INTEGER,
    url        TEXT,
    title      TEXT,
    note       TEXT
);

CREATE TABLE IF NOT EXISTS steps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT,
    step        TEXT,
    path        TEXT,
    created_at  TEXT
);
"""


def get_data_dir() -> str:
    path = os.environ.get("INTEL_DB_PATH", "")
    base = os.path.dirname(path) if path else DEFAULT_DATA_DIR
    os.makedirs(base, exist_ok=True)
    return base


def get_db_path() -> str:
    return os.environ.get("INTEL_DB_PATH", os.path.join(DEFAULT_DATA_DIR, "intelligence.db"))


class IntelligenceStore:
    """Thin SQLite wrapper for persisting intelligence run metadata and reports."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_db_path()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as c:
            c.executescript(SCHEMA)

    # -- sessions ---------------------------------------------------------
    def create_session(self, session_id: str, subject: str, thread_id: Optional[str] = None,
                       report_plan: Optional[List[str]] = None, run_folder: Optional[str] = None) -> Dict[str, Any]:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO sessions "
                "(id, subject, thread_id, status, report_plan, completed_reports, run_folder, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (session_id, subject, thread_id, "running",
                 _json(report_plan or ["subject", "audience", "ecosystem"]),
                 _json([]), run_folder, now, now),
            )
        return self.get_session(session_id)

    def update_session(self, session_id: str, **fields) -> None:
        if not fields:
            return
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cols = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [now, session_id]
        with self._conn() as c:
            c.execute(f"UPDATE sessions SET {cols}, updated_at=? WHERE id=?", vals)

    def mark_completed(self, session_id: str, report_type: str) -> None:
        session = self.get_session(session_id) or {}
        completed = set(_from_json(session.get("completed_reports", "[]")))
        completed.add(report_type)
        self.update_session(session_id, status="running", completed_reports=_json(sorted(completed)))

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        return dict(row) if row else None

    # -- reports ----------------------------------------------------------
    def add_report(self, session_id: str, report_type: str, path: str,
                   summary: str = "", sources_count: int = 0, costs: float = 0.0,
                   completed: bool = True, sources: Optional[List[Dict[str, str]]] = None) -> int:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO reports (session_id, report_type, path, summary, sources_count, costs, completed, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (session_id, report_type, path, summary, sources_count, costs, int(completed), now),
            )
            report_id = cur.lastrowid
            for src in (sources or []):
                c.execute(
                    "INSERT INTO sources (report_id, url, title, note) VALUES (?,?,?,?)",
                    (report_id, src.get("url", ""), src.get("title", ""), src.get("note", "")),
                )
        if completed:
            self.mark_completed(session_id, report_type)
        return report_id

    def get_report(self, session_id: str, report_type: str) -> Optional[Dict[str, Any]]:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM reports WHERE session_id=? AND report_type=? ORDER BY id DESC LIMIT 1",
                (session_id, report_type),
            ).fetchone()
            if not row:
                return None
            rec = dict(row)
            rec["sources"] = [dict(s) for s in c.execute(
                "SELECT url, title, note FROM sources WHERE report_id=?", (rec["id"],)).fetchall()]
            return rec

    def list_reports(self, session_id: str) -> List[Dict[str, Any]]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT report_type, path, sources_count, costs, completed FROM reports WHERE session_id=?",
                (session_id,)).fetchall()]

    # -- steps ------------------------------------------------------------
    def save_step(self, session_id: str, step: str, path: str) -> None:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._conn() as c:
            c.execute(
                "INSERT INTO steps (session_id, step, path, created_at) VALUES (?,?,?,?)",
                (session_id, step, path, now),
            )

    def list_steps(self, session_id: str) -> List[Dict[str, Any]]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT step, path, created_at FROM steps WHERE session_id=? ORDER BY id",
                (session_id,)).fetchall()]


def _json(value: Any) -> str:
    import json
    return json.dumps(value)


def _from_json(text: str) -> Any:
    import json
    try:
        return json.loads(text)
    except Exception:
        return []


# Module-level default store (cheap; SQLite opens lazily per call).
_store: Optional[IntelligenceStore] = None


def get_store() -> IntelligenceStore:
    global _store
    if _store is None:
        _store = IntelligenceStore()
    return _store


def new_session_id() -> str:
    return "run_" + uuid.uuid4().hex[:12]
