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
CREATE TABLE IF NOT EXISTS lrc (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    lrc_type TEXT NOT NULL DEFAULT 'project',
    description TEXT,
    state TEXT,
    known_fixes TEXT DEFAULT '[]',
    priority INTEGER DEFAULT 5,
    always_inject INTEGER DEFAULT 1,
    confirmed_by TEXT DEFAULT 'user',
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lrc_sessions (
    lrc_id INTEGER NOT NULL REFERENCES lrc(id),
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    relevance_note TEXT,
    PRIMARY KEY (lrc_id, session_id)
);

CREATE TABLE IF NOT EXISTS lrc_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    session_count INTEGER DEFAULT 1,
    first_seen TEXT,
    last_seen TEXT,
    suggested_type TEXT DEFAULT 'project',
    promoted INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

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

CREATE TABLE IF NOT EXISTS lrc_ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lrc_id INTEGER NOT NULL REFERENCES lrc(id),
    content TEXT NOT NULL,
    source TEXT DEFAULT 'bot',
    created_at TEXT DEFAULT (datetime('now'))
);
""")
    conn.commit()

    # Additive migration: add source column to turns if not already present
    cols = [row[1] for row in conn.execute("PRAGMA table_info(turns)").fetchall()]
    if "source" not in cols:
        conn.execute("ALTER TABLE turns ADD COLUMN source TEXT")
        conn.commit()

    # Additive migration: add end_date and end_condition to lrc
    migrate_lrc_lifespan(conn)

    conn.close()


def migrate_lrc_lifespan(conn):
    """Add end_date and end_condition columns if not present."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(lrc)").fetchall()]
    if "end_date" not in cols:
        conn.execute("ALTER TABLE lrc ADD COLUMN end_date TEXT")
    if "end_condition" not in cols:
        conn.execute("ALTER TABLE lrc ADD COLUMN end_condition TEXT")
    conn.commit()


def seed_lrcs():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM lrc").fetchone()[0]
    if count == 0:
        now = datetime.utcnow().isoformat()
        conn.executemany(
            "INSERT INTO lrc (name, lrc_type, description, priority, confirmed_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("NickHQ", "project", "Core iOS dashboard app + FastAPI backend. Everything kees builds is either part of NickHQ or feeds into it. Plugins: TimeTracker, Marketplace, Scrap Trading.", 10, "user", now, now),
                ("voice_latency", "issue", "Twilio voice call latency issue. Attempts made: Google TTS (8-20s latency, too slow), Deepgram STT integration (pending), ElevenLabs upgrade (pending). Core bottleneck is Twilio+Google TTS pipeline.", 8, "deduction", now, now),
            ]
        )
        conn.commit()
    conn.close()


init_db()
seed_lrcs()

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


class LRCIn(BaseModel):
    name: str
    lrc_type: str = "project"
    description: Optional[str] = None
    state: Optional[str] = None
    priority: int = 5
    confirmed_by: str = "user"


class LRCUpdateIn(BaseModel):
    description: Optional[str] = None
    state: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    known_fixes: Optional[list] = None
    end_date: Optional[str] = None
    end_condition: Optional[str] = None


class LRCIdeaIn(BaseModel):
    content: str
    source: str = "bot"


class LRCFixIn(BaseModel):
    fix_description: str
    outcome: str  # 'failed', 'partial', 'unknown'
    tried_at: Optional[str] = None


class LRCCandidatePromoteIn(BaseModel):
    lrc_type: str = "project"
    confirmed_by: str = "user"


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

        # ── Active LRCs (always injected, ordered by priority) ───────────────
        lrc_rows = conn.execute(
            "SELECT * FROM lrc WHERE status='active' AND always_inject=1 ORDER BY priority DESC"
        ).fetchall()
        lrcs = []
        for row in lrc_rows:
            d = dict(row)
            if d.get("known_fixes"):
                try:
                    d["known_fixes"] = json.loads(d["known_fixes"])
                except (json.JSONDecodeError, TypeError):
                    d["known_fixes"] = []
            else:
                d["known_fixes"] = []
            idea_rows = conn.execute(
                "SELECT content, created_at FROM lrc_ideas WHERE lrc_id=? ORDER BY created_at DESC LIMIT 10",
                (d["id"],)
            ).fetchall()
            d["recent_ideas"] = [dict(r) for r in idea_rows]
            lrcs.append(d)

        # ── Rough token estimate ──────────────────────────────────────────────
        payload_text = profile + " ".join(preferences) + json.dumps(recent_sessions) + json.dumps(active_projects) + json.dumps(lrcs)
        token_estimate = len(payload_text) // 4

        # ── Truncate preferences if over max_tokens ───────────────────────────
        if token_estimate > max_tokens and preferences:
            # Keep trimming preferences until under budget
            while token_estimate > max_tokens and len(preferences) > 1:
                preferences = preferences[:-5]
                payload_text = profile + " ".join(preferences) + json.dumps(recent_sessions) + json.dumps(lrcs)
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
            "lrcs": lrcs,
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


# ── LRC endpoints ─────────────────────────────────────────────────────────────

@app.get("/lrc/candidates")
def list_lrc_candidates():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM lrc_candidates WHERE promoted=0 ORDER BY session_count DESC"
        ).fetchall()
        return {"candidates": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.get("/lrc")
def list_lrcs():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM lrc WHERE status='active' ORDER BY priority DESC"
        ).fetchall()
        lrcs = []
        for row in rows:
            d = dict(row)
            if d.get("known_fixes"):
                try:
                    d["known_fixes"] = json.loads(d["known_fixes"])
                except (json.JSONDecodeError, TypeError):
                    d["known_fixes"] = []
            else:
                d["known_fixes"] = []
            lrcs.append(d)
        return {"lrcs": lrcs}
    finally:
        conn.close()


@app.get("/lrc/{lrc_id}")
def get_lrc(lrc_id: int):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM lrc WHERE id=?", (lrc_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="LRC not found")
        d = dict(row)
        if d.get("known_fixes"):
            try:
                d["known_fixes"] = json.loads(d["known_fixes"])
            except (json.JSONDecodeError, TypeError):
                d["known_fixes"] = []
        else:
            d["known_fixes"] = []
        # Linked sessions
        session_rows = conn.execute(
            """SELECT ls.relevance_note, s.id, s.title, s.started_at, s.ended_at
               FROM lrc_sessions ls JOIN sessions s ON ls.session_id=s.id
               WHERE ls.lrc_id=? ORDER BY s.id DESC LIMIT 20""",
            (lrc_id,)
        ).fetchall()
        d["sessions"] = [dict(r) for r in session_rows]
        # Ideas
        idea_rows = conn.execute(
            "SELECT * FROM lrc_ideas WHERE lrc_id=? ORDER BY created_at DESC",
            (lrc_id,)
        ).fetchall()
        d["ideas"] = [dict(r) for r in idea_rows]
        return d
    finally:
        conn.close()


@app.post("/lrc")
def create_lrc(body: LRCIn):
    conn = get_db()
    try:
        now = datetime.utcnow().isoformat()
        cur = conn.execute(
            """INSERT INTO lrc (name, lrc_type, description, state, priority, confirmed_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (body.name, body.lrc_type, body.description, body.state, body.priority, body.confirmed_by, now, now)
        )
        conn.commit()
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


@app.patch("/lrc/{lrc_id}")
def update_lrc(lrc_id: int, body: LRCUpdateIn):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM lrc WHERE id=?", (lrc_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="LRC not found")
        now = datetime.utcnow().isoformat()
        updates = {"updated_at": now}
        if body.description is not None:
            updates["description"] = body.description
        if body.state is not None:
            updates["state"] = body.state
        if body.priority is not None:
            updates["priority"] = body.priority
        if body.status is not None:
            updates["status"] = body.status
        if body.known_fixes is not None:
            updates["known_fixes"] = json.dumps(body.known_fixes)
        if body.end_date is not None:
            updates["end_date"] = body.end_date
        if body.end_condition is not None:
            updates["end_condition"] = body.end_condition
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [lrc_id]
        conn.execute(f"UPDATE lrc SET {set_clause} WHERE id=?", values)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.post("/lrc/{lrc_id}/fix")
def add_lrc_fix(lrc_id: int, body: LRCFixIn):
    conn = get_db()
    try:
        row = conn.execute("SELECT known_fixes FROM lrc WHERE id=?", (lrc_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="LRC not found")
        try:
            fixes = json.loads(row["known_fixes"]) if row["known_fixes"] else []
        except (json.JSONDecodeError, TypeError):
            fixes = []
        fixes.append({
            "description": body.fix_description,
            "outcome": body.outcome,
            "tried_at": body.tried_at or datetime.utcnow().isoformat(),
        })
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE lrc SET known_fixes=?, updated_at=? WHERE id=?",
            (json.dumps(fixes), now, lrc_id)
        )
        conn.commit()
        return {"ok": True, "fix_count": len(fixes)}
    finally:
        conn.close()


@app.post("/lrc/{lrc_id}/idea")
def add_lrc_idea(lrc_id: int, body: LRCIdeaIn):
    conn = get_db()
    try:
        row = conn.execute("SELECT id, name FROM lrc WHERE id=?", (lrc_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="LRC not found")
        conn.execute(
            "INSERT INTO lrc_ideas (lrc_id, content, source) VALUES (?, ?, ?)",
            (lrc_id, body.content, body.source)
        )
        conn.commit()
        return {"ok": True, "lrc_name": row["name"]}
    finally:
        conn.close()


@app.post("/lrc/by-name/{name}/idea")
def add_idea_by_name(name: str, body: LRCIdeaIn):
    conn = get_db()
    try:
        row = conn.execute("SELECT id, name FROM lrc WHERE LOWER(name)=LOWER(?)", (name,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"LRC '{name}' not found")
        conn.execute(
            "INSERT INTO lrc_ideas (lrc_id, content, source) VALUES (?, ?, ?)",
            (row["id"], body.content, body.source)
        )
        conn.commit()
        return {"ok": True, "lrc_id": row["id"], "lrc_name": row["name"]}
    finally:
        conn.close()


@app.post("/lrc/candidates/{candidate_id}/promote")
def promote_lrc_candidate(candidate_id: int, body: LRCCandidatePromoteIn):
    conn = get_db()
    try:
        cand = conn.execute(
            "SELECT * FROM lrc_candidates WHERE id=?", (candidate_id,)
        ).fetchone()
        if not cand:
            raise HTTPException(status_code=404, detail="Candidate not found")
        now = datetime.utcnow().isoformat()
        cur = conn.execute(
            """INSERT OR IGNORE INTO lrc (name, lrc_type, confirmed_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (cand["topic"], body.lrc_type, body.confirmed_by, now, now)
        )
        conn.execute(
            "UPDATE lrc_candidates SET promoted=1 WHERE id=?", (candidate_id,)
        )
        conn.commit()
        return {"ok": True, "lrc_id": cur.lastrowid}
    finally:
        conn.close()


@app.post("/lrc/candidates/{candidate_id}/dismiss")
def dismiss_lrc_candidate(candidate_id: int):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE lrc_candidates SET promoted=2 WHERE id=?", (candidate_id,)
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8766)
