#!/usr/bin/env python3
"""
remember-bot server — conversation memory, audit, and crash-recovery for NickBot.
Universal context layer for the breakfast-club: any AI can plug in via /context.
Runs on http://127.0.0.1:8766
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel

DB_PATH = Path(__file__).parent / "remember.db"
MEMORY_DIR = Path("/Users/kees/.nick/memory")

# ── DB init ────────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    claude_session_id TEXT,
    title TEXT,
    summary TEXT,
    end_reason TEXT,
    error_details TEXT,
    tags TEXT,
    status TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    ts TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    token_estimate INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dev_work (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    action TEXT NOT NULL,
    description TEXT NOT NULL,
    file_path TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    content TEXT NOT NULL,
    category TEXT DEFAULT 'idea',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS crashes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    ts TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT,
    context_before TEXT,
    recovery_prompt TEXT,
    recovered INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS context_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    source TEXT NOT NULL,
    context_version INTEGER,
    context_tokens INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    observation_type TEXT NOT NULL,
    detail TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    action_taken TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
""")
    conn.commit()

    # Additive migration: add source column to turns if not already present
    cols = [row[1] for row in conn.execute("PRAGMA table_info(turns)").fetchall()]
    if "source" not in cols:
        conn.execute("ALTER TABLE turns ADD COLUMN source TEXT")
        conn.commit()

    conn.close()


init_db()

# ── Session helpers ────────────────────────────────────────────────────────────

def get_active_session_id(conn) -> Optional[int]:
    row = conn.execute(
        "SELECT id FROM sessions WHERE status='active' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row["id"] if row else None


def create_session(conn) -> int:
    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        "INSERT INTO sessions (started_at, status) VALUES (?, 'active')",
        (now,)
    )
    conn.commit()
    return cur.lastrowid


def ensure_active_session(conn) -> int:
    sid = get_active_session_id(conn)
    if sid is None:
        sid = create_session(conn)
    return sid


def get_session_token_estimate(conn, session_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(token_estimate), 0) as total FROM turns WHERE session_id=?",
        (session_id,)
    ).fetchone()
    return row["total"] if row else 0


def add_tag_to_session(conn, session_id: int, tag: str):
    row = conn.execute("SELECT tags FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        return
    tags = json.loads(row["tags"]) if row["tags"] else []
    if tag not in tags:
        tags.append(tag)
        conn.execute("UPDATE sessions SET tags=? WHERE id=?", (json.dumps(tags), session_id))
        conn.commit()


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="remember-bot", version="1.0.0")


# ── Models ─────────────────────────────────────────────────────────────────────

class TurnIn(BaseModel):
    role: str
    content: str
    session_id: Optional[int] = None
    claude_session_id: Optional[str] = None
    source: Optional[str] = None


class SessionCloseIn(BaseModel):
    reason: str
    error_details: Optional[str] = None


class SessionNewIn(BaseModel):
    claude_session_id: Optional[str] = None


class ActiveClaudeIdIn(BaseModel):
    claude_session_id: str


class SummaryIn(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[list] = None
    end_reason: Optional[str] = None


class DevWorkIn(BaseModel):
    action: str
    description: str
    file_path: Optional[str] = None


class IdeaIn(BaseModel):
    content: str
    category: str = "idea"


class CrashIn(BaseModel):
    error_type: str
    error_message: Optional[str] = None
    context_before: Optional[str] = None
    recovery_prompt: Optional[str] = None
    session_id: Optional[int] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/turns")
def post_turn(body: TurnIn):
    conn = get_db()
    try:
        if body.session_id:
            session_id = body.session_id
        else:
            session_id = ensure_active_session(conn)

        # If claude_session_id provided, update session
        if body.claude_session_id:
            conn.execute(
                "UPDATE sessions SET claude_session_id=? WHERE id=?",
                (body.claude_session_id, session_id)
            )

        token_estimate = len(body.content) // 4
        now = datetime.utcnow().isoformat()

        conn.execute(
            "INSERT INTO turns (session_id, ts, role, content, token_estimate, source) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, now, body.role, body.content, token_estimate, body.source)
        )
        conn.commit()

        # Check cumulative token estimate
        total_tokens = get_session_token_estimate(conn, session_id)
        if total_tokens > 80000:
            add_tag_to_session(conn, session_id, "near-context-limit")

        return {"ok": True, "session_id": session_id, "token_estimate": token_estimate, "session_tokens": total_tokens}
    finally:
        conn.close()


@app.post("/sessions/new")
def new_session(body: SessionNewIn = None):
    conn = get_db()
    try:
        # Close any active session first
        active = get_active_session_id(conn)
        if active:
            conn.execute(
                "UPDATE sessions SET status='closed', ended_at=?, end_reason='superseded' WHERE id=?",
                (datetime.utcnow().isoformat(), active)
            )
            conn.commit()

        now = datetime.utcnow().isoformat()
        claude_id = (body.claude_session_id if body else None)
        cur = conn.execute(
            "INSERT INTO sessions (started_at, status, claude_session_id) VALUES (?, 'active', ?)",
            (now, claude_id)
        )
        conn.commit()
        return {"ok": True, "session_id": cur.lastrowid}
    finally:
        conn.close()


@app.post("/sessions/close")
def close_session(body: SessionCloseIn):
    conn = get_db()
    try:
        active = get_active_session_id(conn)
        if not active:
            return {"ok": False, "message": "No active session"}
        conn.execute(
            "UPDATE sessions SET status='closed', ended_at=?, end_reason=?, error_details=? WHERE id=?",
            (datetime.utcnow().isoformat(), body.reason, body.error_details, active)
        )
        conn.commit()
        return {"ok": True, "closed_session_id": active}
    finally:
        conn.close()


@app.patch("/sessions/active-claude-id")
def update_active_claude_id(body: ActiveClaudeIdIn):
    conn = get_db()
    try:
        active = get_active_session_id(conn)
        if not active:
            # Create a session if none exists
            active = create_session(conn)
        conn.execute(
            "UPDATE sessions SET claude_session_id=? WHERE id=?",
            (body.claude_session_id, active)
        )
        conn.commit()
        return {"ok": True, "session_id": active}
    finally:
        conn.close()


@app.get("/sessions")
def list_sessions(limit: int = 20):
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT s.*,
               (SELECT COUNT(*) FROM turns WHERE session_id=s.id) as turn_count
               FROM sessions s ORDER BY s.id DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        return {"sessions": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.get("/sessions/active")
def get_active_session():
    conn = get_db()
    try:
        active = get_active_session_id(conn)
        if not active:
            return {"session": None}
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (active,)).fetchone()
        turns = conn.execute(
            "SELECT * FROM turns WHERE session_id=? ORDER BY id DESC LIMIT 20",
            (active,)
        ).fetchall()
        return {
            "session": dict(row),
            "recent_turns": [dict(t) for t in reversed(turns)]
        }
    finally:
        conn.close()


@app.get("/sessions/{session_id}")
def get_session(session_id: int):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        turns = conn.execute(
            "SELECT * FROM turns WHERE session_id=? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        dev_work = conn.execute(
            "SELECT * FROM dev_work WHERE session_id=? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        ideas = conn.execute(
            "SELECT * FROM ideas WHERE session_id=? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        return {
            "session": dict(row),
            "turns": [dict(t) for t in turns],
            "dev_work": [dict(d) for d in dev_work],
            "ideas": [dict(i) for i in ideas],
        }
    finally:
        conn.close()


@app.put("/sessions/{session_id}/summary")
def set_summary(session_id: int, body: SummaryIn):
    conn = get_db()
    try:
        row = conn.execute("SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        tags_json = json.dumps(body.tags) if body.tags else None
        conn.execute(
            """UPDATE sessions SET title=COALESCE(?, title), summary=COALESCE(?, summary),
               tags=COALESCE(?, tags), end_reason=COALESCE(?, end_reason), status='closed'
               WHERE id=?""",
            (body.title, body.summary, tags_json, body.end_reason, session_id)
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.post("/sessions/{session_id}/dev_work")
def add_dev_work(session_id: int, body: DevWorkIn):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO dev_work (session_id, action, description, file_path) VALUES (?, ?, ?, ?)",
            (session_id, body.action, body.description, body.file_path)
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.post("/sessions/{session_id}/ideas")
def add_idea(session_id: int, body: IdeaIn):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO ideas (session_id, content, category) VALUES (?, ?, ?)",
            (session_id, body.content, body.category)
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.get("/summary/{session_id}")
def get_summary(session_id: int):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"session_id": session_id, "title": row["title"], "summary": row["summary"]}
    finally:
        conn.close()


@app.post("/crashes")
def log_crash(body: CrashIn):
    conn = get_db()
    try:
        now = datetime.utcnow().isoformat()
        session_id = body.session_id
        if session_id is None:
            session_id = get_active_session_id(conn)
        cur = conn.execute(
            "INSERT INTO crashes (session_id, ts, error_type, error_message, context_before, recovery_prompt) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, now, body.error_type, body.error_message, body.context_before, body.recovery_prompt)
        )
        conn.commit()
        return {"ok": True, "crash_id": cur.lastrowid}
    finally:
        conn.close()


@app.get("/crashes")
def list_crashes(limit: int = 50, unrecovered_only: bool = False):
    conn = get_db()
    try:
        if unrecovered_only:
            rows = conn.execute(
                "SELECT * FROM crashes WHERE recovered=0 ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM crashes ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return {"crashes": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.patch("/crashes/{crash_id}/recovered")
def mark_crash_recovered(crash_id: int):
    conn = get_db()
    try:
        conn.execute("UPDATE crashes SET recovered=1 WHERE id=?", (crash_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.get("/search")
def search(q: str = Query(..., min_length=1), limit: int = 20):
    conn = get_db()
    try:
        pattern = f"%{q}%"

        # Search turns
        turns = conn.execute(
            """SELECT t.*, s.started_at, s.title as session_title, s.status as session_status
               FROM turns t JOIN sessions s ON t.session_id=s.id
               WHERE t.content LIKE ? ORDER BY t.id DESC LIMIT ?""",
            (pattern, limit)
        ).fetchall()

        # Search dev_work
        dev_rows = conn.execute(
            """SELECT d.*, s.started_at, s.title as session_title
               FROM dev_work d JOIN sessions s ON d.session_id=s.id
               WHERE d.description LIKE ? ORDER BY d.id DESC LIMIT ?""",
            (pattern, limit)
        ).fetchall()

        # Search ideas
        idea_rows = conn.execute(
            """SELECT i.*, s.started_at, s.title as session_title
               FROM ideas i JOIN sessions s ON i.session_id=s.id
               WHERE i.content LIKE ? ORDER BY i.id DESC LIMIT ?""",
            (pattern, limit)
        ).fetchall()

        # Group turns by session
        by_session = {}
        for t in turns:
            td = dict(t)
            sid = td["session_id"]
            if sid not in by_session:
                by_session[sid] = {
                    "session_id": sid,
                    "started_at": td["started_at"],
                    "session_title": td["session_title"],
                    "session_status": td["session_status"],
                    "turns": []
                }
            by_session[sid]["turns"].append({
                "id": td["id"],
                "ts": td["ts"],
                "role": td["role"],
                "content": td["content"][:500]
            })

        return {
            "query": q,
            "turn_sessions": list(by_session.values()),
            "dev_work": [dict(r) for r in dev_rows],
            "ideas": [dict(r) for r in idea_rows],
        }
    finally:
        conn.close()


@app.get("/context")
def get_context(source: str = "unknown", max_tokens: int = 4000):
    """
    Universal context endpoint — any AI calls this on startup to get fully loaded.
    Returns profile, memory, recent session summaries, active projects, and last turn.
    """
    conn = get_db()
    try:
        now = datetime.utcnow().isoformat()

        # ── Read flat memory files ─────────────────────────────────────────────
        profile = ""
        user_file = MEMORY_DIR / "USER.md"
        if user_file.exists():
            profile = user_file.read_text().strip()

        preferences = []
        memory_file = MEMORY_DIR / "MEMORY.md"
        if memory_file.exists():
            for line in memory_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    preferences.append(line)

        # ── Recent closed sessions (last 5 with summaries) ────────────────────
        session_rows = conn.execute(
            """SELECT id, title, summary, tags, ended_at, started_at, end_reason
               FROM sessions
               WHERE status='closed' AND summary IS NOT NULL
               ORDER BY id DESC LIMIT 5"""
        ).fetchall()

        recent_sessions = []
        for row in reversed(session_rows):  # chronological order
            tags = json.loads(row["tags"]) if row["tags"] else []
            recent_sessions.append({
                "id": row["id"],
                "title": row["title"],
                "summary": row["summary"],
                "tags": tags,
                "ended_at": row["ended_at"],
                "started_at": row["started_at"],
            })

        # ── Active session if any ─────────────────────────────────────────────
        active_row = conn.execute(
            "SELECT * FROM sessions WHERE status='active' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        active_session = None
        if active_row:
            tags = json.loads(active_row["tags"]) if active_row["tags"] else []
            active_session = {
                "id": active_row["id"],
                "started_at": active_row["started_at"],
                "tags": tags,
                "status": "active",
            }
            recent_sessions.append(active_session)

        # ── Recent dev work (last 20 distinct file_paths/actions) ─────────────
        dw_rows = conn.execute(
            """SELECT DISTINCT d.action, d.description, d.file_path, d.created_at
               FROM dev_work d
               JOIN sessions s ON d.session_id = s.id
               ORDER BY d.id DESC LIMIT 20"""
        ).fetchall()
        active_projects = [dict(r) for r in dw_rows]

        # ── Last turn across all sessions ─────────────────────────────────────
        last_turn_row = conn.execute(
            "SELECT role, content, ts FROM turns ORDER BY id DESC LIMIT 1"
        ).fetchone()
        last_turn = dict(last_turn_row) if last_turn_row else None

        # ── Rough token estimate ──────────────────────────────────────────────
        payload_text = profile + " ".join(preferences) + json.dumps(recent_sessions) + json.dumps(active_projects)
        token_estimate = len(payload_text) // 4

        # ── Truncate preferences if over max_tokens ───────────────────────────
        if token_estimate > max_tokens and preferences:
            # Keep trimming preferences until under budget
            while token_estimate > max_tokens and len(preferences) > 1:
                preferences = preferences[:-5]
                payload_text = profile + " ".join(preferences) + json.dumps(recent_sessions)
                token_estimate = len(payload_text) // 4

        # ── Log this retrieval ────────────────────────────────────────────────
        conn.execute(
            "INSERT INTO context_log (ts, source, context_version, context_tokens) VALUES (?, ?, ?, ?)",
            (now, source, 1, token_estimate)
        )
        conn.commit()

        return {
            "generated_at": now,
            "source": source,
            "profile": profile,
            "preferences": preferences,
            "recent_sessions": recent_sessions,
            "active_projects": active_projects,
            "last_turn": last_turn,
            "context_tokens_estimate": token_estimate,
        }
    finally:
        conn.close()


@app.get("/observations")
def list_observations(limit: int = 50, observation_type: Optional[str] = None):
    conn = get_db()
    try:
        if observation_type:
            rows = conn.execute(
                "SELECT * FROM observations WHERE observation_type=? ORDER BY id DESC LIMIT ?",
                (observation_type, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM observations ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return {"observations": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.post("/observations")
def post_observation(body: dict):
    conn = get_db()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO observations (ts, observation_type, detail, severity, action_taken) VALUES (?, ?, ?, ?, ?)",
            (now, body.get("observation_type"), body.get("detail"), body.get("severity", "info"), body.get("action_taken"))
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8766)
