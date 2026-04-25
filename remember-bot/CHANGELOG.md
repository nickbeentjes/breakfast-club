# remember-bot CHANGELOG

## 2026-04-25 — LRC lifespan, auto-demotion, and idea capture

### What was built
- `end_date` + `end_condition` columns added to `lrc` table via safe ALTER TABLE migration
- `lrc_ideas` table for freeform idea capture against any LRC (with source tracking)
- `POST /lrc/{id}/idea` and `POST /lrc/by-name/{name}/idea` endpoints
- `GET /lrc/{id}` now returns ideas array
- `PATCH /lrc/{id}` now accepts `end_date` and `end_condition`
- `/context` endpoint includes `recent_ideas` (last 10) per LRC in payload
- `observer.py`: `check_lrc_expirations()` — archives LRCs past `end_date`, logs observation, Telegrams kees with extend hint; runs first in `main()` after health check
- `bot.py`: `/lrc done <name>` — manual archive; `/lrc until <name> <date/condition>` — set expiry; `/lrc idea <name> <text>` — capture idea; `/lrc add` supports inline `until <date>`; `/lrc list` shows end_date and end_condition
- `bot.py`: LRC block in `build_memory_context()` includes end info and captured ideas

### Problem solved
LRCs were permanent with no lifecycle. Now they can have a natural expiry date ("preparing for keynote — ends 2026-05-25") and auto-archive when done. Ideas can be captured against an LRC mid-session without spinning up Claude, keeping fleeting thoughts attached to the right context.

---

## 2026-04-25 — LRC (Long Running Contexts)

### What was built
- `lrc`, `lrc_sessions`, `lrc_candidates` tables in DB
- Seeded two LRCs on init: NickHQ (project, priority 10), voice_latency (issue, priority 8)
- `/lrc` endpoints: list, get, create, patch, add fix, list candidates, promote, dismiss
- `/context` now returns `lrcs` at top of payload — always injected before session summaries
- `observer.py`: `detect_lrc_candidates()` — flags topics in 3+ sessions (14d window) as candidates; issue-loop detection for fix/error language; `detect_nickhq_membership()` auto-links sessions with NickHQ keywords via `lrc_sessions`
- `tuner.py`: `promote_lrc_candidates()` — uses Claude to type/describe candidates with 5+ sessions; `update_lrc_states()` — weekly state refresh for project LRCs active this week
- `bot.py`: LRC block injected FIRST in `build_memory_context()` with known attempts prominently listed; `/lrc` command with subcommands: list, add, issue, fix, candidates, promote

### Problem solved
Sessions re-investigating the same issue (voice latency, broken feature) without knowing prior attempts. LRCs ensure every session starts with always-on context for persistent projects and issue loops — the `known_fixes` list explicitly tells future sessions what has already been tried and failed.

---

## 2026-04-25 — initial breakfast-club build

### What was built
- `/context` endpoint: universal context API any AI can call on startup to get fully loaded
- `context_log` table: tracks who calls `/context` and how many tokens were served
- `observations` table: stores pattern detections from observer.py
- `source` column on `turns` table: tracks which AI wrote each turn
- `observer.py`: daily script detecting repeat topics, context gaps, project threads, source diversity
- `tuner.py`: weekly script acting on observations — updates MEMORY.md, generates project_state files, prunes old entries, commits to git, Telegrams kees
- `bot.py`: `build_memory_context()` now calls `/context` first, falls back to flat files if remember-bot is down
- `bot.py`: turn logging now includes `source="nickbot"`
- `mcp_server.py`: added `get_context`, `log_turn`, `search_memory`, `remember_fact` tools
- launchd plists: `com.nick.remember-observer` (daily 6am), `com.nick.remember-tuner` (Sundays 7am)

### Problem solved
kees had to re-explain the same project spec 4 times in 18 hours because each session
started nearly blind. The DB had rich summaries but nothing fed back in. Now any AI
calling `/context` gets: profile, memory, last 5 session summaries, recent dev work,
and the last turn — before saying a word.

---

