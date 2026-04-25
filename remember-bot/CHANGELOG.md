# remember-bot CHANGELOG

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

