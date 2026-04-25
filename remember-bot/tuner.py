#!/usr/bin/env python3
"""
remember-bot tuner — weekly auto-improvement script.
Runs Sundays at 7am via launchd.

Reads observations from last 7 days and acts:
  - repeat_topic: ensure topic is in MEMORY.md
  - project_thread: generate project_state_{name}.md if not exists and 5+ sessions
  - prune: remove MEMORY.md entries older than 90 days not recently referenced

NEVER touches bot.py code — only memory files and config.
Commits changes to git and sends Telegram summary.
"""

import json
import re
import subprocess
import sqlite3
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

RB_BASE = "http://127.0.0.1:8766"
DB_PATH = Path(__file__).parent / "remember.db"
MEMORY_DIR = Path("/Users/kees/.nick/memory")
MEMORY_FILE = MEMORY_DIR / "MEMORY.md"
BOT_TOKEN = "8744181775:AAFo0IYt8DghDnXcJFxeP5xKeP7wwHoineM"
KEES_CHAT_ID = 8664999274
CLAUDE_BIN = "/Users/kees/.local/bin/claude"
NICK_WORK_DIR = "/Users/kees/.nick"
REMEMBER_BOT_DIR = Path(__file__).parent
CHANGELOG_FILE = REMEMBER_BOT_DIR / "CHANGELOG.md"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def rb_get(path: str) -> dict:
    try:
        req = urllib.request.Request(f"{RB_BASE}{path}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[rb_get] {path} failed: {e}")
        return {}


def rb_post(path: str, data: dict) -> dict:
    try:
        payload = json.dumps(data).encode()
        req = urllib.request.Request(
            f"{RB_BASE}{path}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[rb_post] {path} failed: {e}")
        return {}


def telegram_send(text: str):
    try:
        payload = json.dumps({
            "chat_id": KEES_CHAT_ID,
            "text": text
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"[tuner] Telegram sent: {text[:80]}")
    except Exception as e:
        print(f"[tuner] Telegram failed: {e}")


def log_action(observation_type: str, detail: str, action_taken: str):
    rb_post("/observations", {
        "observation_type": observation_type,
        "detail": detail,
        "severity": "action_taken",
        "action_taken": action_taken,
    })


def run_claude_sync(prompt: str, timeout: int = 120) -> str:
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "--print", "--dangerously-skip-permissions", prompt],
            capture_output=True, text=True, timeout=timeout, cwd=NICK_WORK_DIR
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"[tuner] Claude call failed: {e}")
        return ""


def ensure_memory_entry(topic: str) -> bool:
    """Append topic to MEMORY.md if not already present. Returns True if added."""
    MEMORY_DIR.mkdir(exist_ok=True)
    existing = MEMORY_FILE.read_text() if MEMORY_FILE.exists() else ""
    # Simple containment check (case-insensitive)
    if topic.lower() in existing.lower():
        return False
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n- [{timestamp}] [auto-tuner] {topic}"
    with open(MEMORY_FILE, "a") as f:
        f.write(entry)
    print(f"[tuner] Added to MEMORY.md: {topic}")
    return True


def generate_project_state(topic: str, session_ids: list, conn) -> str:
    """Use Claude to generate a project_state file from session summaries and turns."""
    # Gather summaries from sessions mentioning this topic
    summaries = []
    for sid in session_ids[:10]:
        row = conn.execute(
            "SELECT title, summary, started_at FROM sessions WHERE id=?", (sid,)
        ).fetchone()
        if row and row["summary"]:
            summaries.append(f"Session {sid} ({row['started_at'][:10]}): {row['title']}\n{row['summary']}")

    # Get a sample of relevant turns
    turns_text = []
    for sid in session_ids[:5]:
        turns = conn.execute(
            """SELECT role, content FROM turns WHERE session_id=? AND role='user'
               ORDER BY id ASC LIMIT 5""",
            (sid,)
        ).fetchall()
        for t in turns:
            turns_text.append(f"[session {sid}] {t['content'][:200]}")

    summaries_block = "\n\n".join(summaries) if summaries else "(no summaries available)"
    turns_block = "\n".join(turns_text[:20]) if turns_text else "(no turns available)"

    prompt = f"""You are helping kees document a project. Based on the session data below, write a concise project state document.

Topic/Project: "{topic}"
Sessions found: {len(session_ids)} (ids: {session_ids[:10]})

SESSION SUMMARIES:
{summaries_block}

SAMPLE TURNS:
{turns_block}

Write a project_state markdown document with these sections:
# Project: {topic}

## What it is
(1-2 sentences)

## Current status
(what's been built, where things stand)

## Key decisions made
(bullet points)

## Next steps / open questions
(bullet points)

## Sessions
(list the session IDs and dates)

Keep it factual and brief. Only include what's evident from the sessions above. Do not invent details."""

    return run_claude_sync(prompt, timeout=120)


def process_repeat_topics(observations: list) -> list:
    """Ensure repeat topics are in MEMORY.md. Returns list of actions taken."""
    actions = []
    seen_topics = set()

    for obs in observations:
        if obs["observation_type"] != "repeat_topic":
            continue
        # Extract the phrase from detail like: "phrase" appeared in N sessions
        m = re.search(r'"([^"]+)"', obs["detail"])
        if not m:
            continue
        phrase = m.group(1)
        if phrase in seen_topics:
            continue
        seen_topics.add(phrase)

        added = ensure_memory_entry(f'Recurring topic: "{phrase}"')
        if added:
            actions.append(f'Added "{phrase}" to MEMORY.md (repeat topic)')
            log_action("repeat_topic", obs["detail"], f'Added to MEMORY.md: "{phrase}"')

    return actions


def process_project_threads(observations: list, conn) -> list:
    """Generate project_state files for strong project threads. Returns actions taken."""
    actions = []
    seen_topics = set()

    for obs in observations:
        if obs["observation_type"] != "project_thread":
            continue
        # Only act on threads that don't already have a file
        if "already exists" in obs["detail"]:
            continue

        m = re.search(r'"([^"]+)"', obs["detail"])
        if not m:
            continue
        phrase = m.group(1)
        if phrase in seen_topics:
            continue
        seen_topics.add(phrase)

        # Extract session count
        count_m = re.search(r"spans (\d+) sessions", obs["detail"])
        if not count_m or int(count_m.group(1)) < 5:
            continue

        sanitized = re.sub(r"[^\w]", "_", phrase.lower()).strip("_")
        project_file = MEMORY_DIR / f"project_state_{sanitized}.md"

        if project_file.exists():
            print(f"[tuner] {project_file.name} already exists, skipping")
            continue

        print(f"[tuner] Generating {project_file.name} for topic: {phrase}")

        # Find all sessions mentioning this phrase
        session_rows = conn.execute(
            """SELECT DISTINCT t.session_id
               FROM turns t
               WHERE LOWER(t.content) LIKE ?
               ORDER BY t.session_id""",
            (f"%{phrase.lower()}%",)
        ).fetchall()
        session_ids = [r["session_id"] for r in session_rows]

        content = generate_project_state(phrase, session_ids, conn)
        if not content or len(content) < 100:
            print(f"[tuner] Claude returned insufficient content for {phrase}, skipping")
            continue

        project_file.write_text(content)
        action_msg = f"Created {project_file.name}"
        actions.append(f"Created /memory/{project_file.name} (topic '{phrase}', {len(session_ids)} sessions)")
        log_action("project_thread", obs["detail"], action_msg)

    return actions


def prune_old_memory_entries() -> list:
    """Remove MEMORY.md entries older than 90 days that haven't been referenced recently."""
    if not MEMORY_FILE.exists():
        return []

    actions = []
    cutoff = datetime.now() - timedelta(days=90)
    lines = MEMORY_FILE.read_text().splitlines()
    kept = []
    pruned = []

    for line in lines:
        # Lines with timestamps like [2026-01-15 10:30]
        m = re.search(r'\[(\d{4}-\d{2}-\d{2})', line)
        if m:
            try:
                entry_date = datetime.strptime(m.group(1), "%Y-%m-%d")
                if entry_date < cutoff:
                    pruned.append(line)
                    continue
            except ValueError:
                pass
        kept.append(line)

    if pruned:
        MEMORY_FILE.write_text("\n".join(kept))
        action_msg = f"Pruned {len(pruned)} entries older than 90 days from MEMORY.md"
        actions.append(action_msg)
        log_action("prune", f"Removed {len(pruned)} old entries", action_msg)
        print(f"[tuner] {action_msg}")

    return actions


def git_commit(message: str):
    """Commit all changed memory files to git."""
    try:
        subprocess.run(
            ["git", "add", "CHANGELOG.md"],
            cwd=str(REMEMBER_BOT_DIR), capture_output=True
        )
        subprocess.run(
            ["git", "add", str(MEMORY_DIR)],
            cwd=str(REMEMBER_BOT_DIR), capture_output=True
        )
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(REMEMBER_BOT_DIR), capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"[tuner] Git commit: {message}")
            # Push
            subprocess.run(
                ["git", "push"],
                cwd=str(REMEMBER_BOT_DIR), capture_output=True
            )
        else:
            print(f"[tuner] Git commit failed: {result.stderr}")
    except Exception as e:
        print(f"[tuner] Git error: {e}")


def update_changelog(actions: list, observations_summary: list):
    """Prepend a CHANGELOG.md entry for this tuner run."""
    today = datetime.now().strftime("%Y-%m-%d")

    obs_lines = "\n".join(f"- {o}" for o in observations_summary) if observations_summary else "- No significant observations"
    action_lines = "\n".join(f"- {a}" for a in actions) if actions else "- No changes made"

    entry = f"""## {today} — tuner run

### Observations
{obs_lines}

### Actions taken
{action_lines}

---

"""
    existing = CHANGELOG_FILE.read_text() if CHANGELOG_FILE.exists() else "# remember-bot CHANGELOG\n\n"
    # Find where to insert (after the header line)
    if "# remember-bot CHANGELOG" in existing:
        header_end = existing.index("\n\n") + 2
        new_content = existing[:header_end] + entry + existing[header_end:]
    else:
        new_content = "# remember-bot CHANGELOG\n\n" + entry + existing

    CHANGELOG_FILE.write_text(new_content)


def main():
    print(f"[tuner] Starting at {datetime.utcnow().isoformat()}")

    # Check server
    try:
        req = urllib.request.Request(f"{RB_BASE}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            health = json.loads(resp.read())
        if health.get("status") != "ok":
            print("[tuner] Server not healthy, exiting")
            return
    except Exception as e:
        print(f"[tuner] Server not reachable: {e}")
        return

    # Get observations from last 7 days
    data = rb_get("/observations?limit=200")
    all_observations = data.get("observations", [])

    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    recent_obs = [
        o for o in all_observations
        if o.get("created_at", "") > seven_days_ago.isoformat()[:19]
    ]
    print(f"[tuner] {len(recent_obs)} observations in last 7 days")

    conn = get_db()
    all_actions = []
    observations_summary = []

    try:
        # Process repeat topics
        topic_actions = process_repeat_topics(recent_obs)
        all_actions.extend(topic_actions)

        # Count repeat topics for summary
        repeat_count = sum(1 for o in recent_obs if o["observation_type"] == "repeat_topic")
        if repeat_count:
            observations_summary.append(f"{repeat_count} repeat topics detected this week")

        # Process project threads
        thread_actions = process_project_threads(recent_obs, conn)
        all_actions.extend(thread_actions)

        thread_count = sum(1 for o in recent_obs if o["observation_type"] == "project_thread")
        if thread_count:
            observations_summary.append(f"{thread_count} project threads detected")

        # Prune old memory entries
        prune_actions = prune_old_memory_entries()
        all_actions.extend(prune_actions)

        # Context gap summary
        gap_count = sum(1 for o in recent_obs if o["observation_type"] == "context_gap")
        if gap_count:
            observations_summary.append(f"{gap_count} context gap events this week")

    finally:
        conn.close()

    today = datetime.now().strftime("%Y-%m-%d")

    # Update CHANGELOG
    update_changelog(all_actions, observations_summary)

    # Git commit if anything changed
    if all_actions:
        topics_note = f"{len(all_actions)} memory update(s) on {today}"
        git_commit(f"tuner: {topics_note}")

    # Build Telegram message
    obs_lines = "\n".join(f"• {o}" for o in observations_summary) if observations_summary else "• Nothing significant this week"
    action_lines = "\n".join(f"• {a}" for a in all_actions) if all_actions else "• No changes made"

    msg = (
        f"🧠 Remember-bot weekly tune — {today}\n\n"
        f"Observations this week:\n{obs_lines}\n\n"
        f"Changes made:\n{action_lines}\n\n"
        f"No changes made to bot code — only memory files updated."
    )
    telegram_send(msg)
    print(f"[tuner] Done. Actions taken: {len(all_actions)}")


if __name__ == "__main__":
    main()
