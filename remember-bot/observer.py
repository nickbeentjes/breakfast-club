#!/usr/bin/env python3
"""
remember-bot observer — daily analysis script.
Runs at 6am via launchd. Read-only to codebase — only writes to observations table.

Detects:
  - repeat_topic: phrases appearing in 3+ separate sessions in last 7 days
  - context_gap: sessions where kees sent a file in first 3 turns (re-explain signal)
  - project_thread: topics spanning 5+ sessions (candidate for project_state file)
  - source_diversity: which AI sources have been using /context
"""

import json
import sqlite3
import re
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

RB_BASE = "http://127.0.0.1:8766"
DB_PATH = Path(__file__).parent / "remember.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def rb_post(path: str, data: dict):
    try:
        payload = json.dumps(data).encode()
        req = urllib.request.Request(
            f"{RB_BASE}{path}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[rb_post] {path} failed: {e}")


def log_observation(observation_type: str, detail: str, severity: str = "info", action_taken: str = None):
    """Post an observation to the DB via the API."""
    rb_post("/observations", {
        "observation_type": observation_type,
        "detail": detail,
        "severity": severity,
        "action_taken": action_taken,
    })
    print(f"[observer] {observation_type}: {detail[:100]}")


def extract_ngrams(text: str, n: int = 3) -> list:
    """Extract word n-grams from text, lowercased, stripped of punctuation."""
    text = re.sub(r"[^\w\s]", " ", text.lower())
    words = [w for w in text.split() if len(w) > 3]
    if len(words) < n:
        return words
    return [" ".join(words[i:i+n]) for i in range(len(words) - n + 1)]


def detect_repeat_topics(conn, since: datetime):
    """Find phrases/topics appearing in 3+ separate sessions in last 7 days."""
    print("[observer] Detecting repeat topics...")

    since_iso = since.isoformat()
    rows = conn.execute(
        """SELECT t.content, t.session_id
           FROM turns t
           JOIN sessions s ON t.session_id = s.id
           WHERE t.ts > ? AND t.role = 'user'
           ORDER BY t.session_id""",
        (since_iso,)
    ).fetchall()

    # Map phrase -> set of session_ids
    phrase_sessions: dict = defaultdict(set)
    for row in rows:
        ngrams = extract_ngrams(row["content"], n=3)
        for phrase in ngrams:
            phrase_sessions[phrase].add(row["session_id"])

    # Find phrases in 3+ separate sessions
    repeated = {p: sids for p, sids in phrase_sessions.items() if len(sids) >= 3}

    if not repeated:
        print("[observer] No repeat topics found")
        return

    # Sort by frequency and take top 10
    top = sorted(repeated.items(), key=lambda x: len(x[1]), reverse=True)[:10]

    for phrase, session_ids in top:
        detail = f'"{phrase}" appeared in {len(session_ids)} sessions (ids: {sorted(session_ids)})'
        log_observation("repeat_topic", detail, severity="info")


def detect_context_gaps(conn, since: datetime):
    """Detect sessions where kees sent a file in first 3 turns — re-explain signal."""
    print("[observer] Detecting context gaps...")

    since_iso = since.isoformat()
    session_rows = conn.execute(
        "SELECT id FROM sessions WHERE started_at > ?",
        (since_iso,)
    ).fetchall()

    gap_sessions = []
    for srow in session_rows:
        sid = srow["id"]
        # Get first 3 user turns
        turns = conn.execute(
            """SELECT content FROM turns
               WHERE session_id = ? AND role = 'user'
               ORDER BY id ASC LIMIT 3""",
            (sid,)
        ).fetchall()

        for turn in turns:
            content = turn["content"]
            # Signals of file sending or context re-explanation
            if re.search(r"Saved:\s*files/", content) or re.search(r"\.(py|md|json|txt|swift)\b", content):
                gap_sessions.append(sid)
                break

    if gap_sessions:
        detail = f"Context gap detected: {len(gap_sessions)} sessions started with file references in first 3 turns (session ids: {gap_sessions[:20]})"
        log_observation("context_gap", detail, severity="warn")
    else:
        print("[observer] No context gaps found")


def detect_project_threads(conn, since_long: datetime):
    """Find topics spanning 5+ sessions — candidate for dedicated project_state file."""
    print("[observer] Detecting project threads...")

    since_iso = since_long.isoformat()
    rows = conn.execute(
        """SELECT t.content, t.session_id
           FROM turns t
           JOIN sessions s ON t.session_id = s.id
           WHERE t.ts > ? AND t.role = 'user'""",
        (since_iso,)
    ).fetchall()

    phrase_sessions: dict = defaultdict(set)
    for row in rows:
        ngrams = extract_ngrams(row["content"], n=2)
        for phrase in ngrams:
            phrase_sessions[phrase].add(row["session_id"])

    # Phrases spanning 5+ sessions
    threads = {p: sids for p, sids in phrase_sessions.items() if len(sids) >= 5}

    if not threads:
        print("[observer] No project threads found")
        return

    top = sorted(threads.items(), key=lambda x: len(x[1]), reverse=True)[:5]
    for phrase, session_ids in top:
        # Check if a project_state file already exists for this
        sanitized = re.sub(r"[^\w]", "_", phrase.lower())
        project_file = Path("/Users/kees/.nick/memory") / f"project_state_{sanitized}.md"
        already_exists = project_file.exists()

        detail = (
            f'Project thread: "{phrase}" spans {len(session_ids)} sessions. '
            f'project_state_{sanitized}.md {"already exists" if already_exists else "does not exist — candidate for creation"}.'
        )
        log_observation("project_thread", detail, severity="info")


def detect_source_diversity(conn):
    """Note which AI sources have been using the /context endpoint."""
    print("[observer] Checking source diversity...")

    rows = conn.execute(
        """SELECT source, COUNT(*) as cnt, MAX(created_at) as last_seen
           FROM context_log
           GROUP BY source
           ORDER BY cnt DESC"""
    ).fetchall()

    if not rows:
        print("[observer] No context_log entries found")
        return

    lines = [f"{row['source']}: {row['cnt']} calls, last seen {row['last_seen'][:10]}" for row in rows]
    detail = "Context endpoint usage by source: " + " | ".join(lines)
    log_observation("source_diversity", detail, severity="info")

    # Also check turns source diversity
    turn_rows = conn.execute(
        """SELECT source, COUNT(*) as cnt
           FROM turns
           WHERE source IS NOT NULL
           GROUP BY source
           ORDER BY cnt DESC"""
    ).fetchall()

    if turn_rows:
        turn_lines = [f"{r['source']}: {r['cnt']} turns" for r in turn_rows]
        turn_detail = "Turn sources: " + " | ".join(turn_lines)
        log_observation("source_diversity", turn_detail, severity="info")


def main():
    print(f"[observer] Starting at {datetime.utcnow().isoformat()}")

    # Check if server is up
    try:
        req = urllib.request.Request(f"{RB_BASE}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            health = json.loads(resp.read())
        if health.get("status") != "ok":
            print("[observer] Server not healthy, exiting")
            return
    except Exception as e:
        print(f"[observer] Server not reachable: {e}")
        return

    conn = get_db()
    try:
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        detect_repeat_topics(conn, since=seven_days_ago)
        detect_context_gaps(conn, since=seven_days_ago)
        detect_project_threads(conn, since_long=thirty_days_ago)
        detect_source_diversity(conn)
    finally:
        conn.close()

    print("[observer] Done")


if __name__ == "__main__":
    main()
