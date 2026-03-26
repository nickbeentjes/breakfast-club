---
phase: 01-foundation
plan: 05
subsystem: identity
tags: [skill.md, token-budget, mcp, identity, portability, typescript]

# Dependency graph
requires:
  - phase: 01-foundation-03
    provides: "MCP tool names registered: identity_context, projects_list"
  - phase: 01-foundation-04
    provides: "MCP tool names registered: identity_query, verify_integrity"

provides:
  - "SKILL.md at repo root — AI-agnostic instruction file for any model to use the identity store"
  - "scripts/count-tokens.ts — token budget verification script with word-count heuristic"
  - "npm run count-tokens — verified SKILL.md is 349 estimated tokens (under 600 budget)"

affects:
  - "Phase 02 (projection engine) — SKILL.md Projection Rules section provides the placeholder guidance"
  - "Phase 04 (memory search) — SKILL.md Memory Search section provides the placeholder guidance"
  - "All future AI integrations — SKILL.md is the portability layer for every provider"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SKILL.md format: <identity> XML wrapper for cross-model compatibility; entire content wrapped in single XML tag"
    - "Token budget measurement: words x 1.3 heuristic (Math.ceil) — no tiktoken dependency; ~450 words is safe proxy for 600 tokens"
    - "count-tokens.ts outputs only to console.error() for consistency with MCP-07 stderr-only rule"

key-files:
  created:
    - "SKILL.md — production identity instruction file; 268 words, 349 estimated tokens, <identity> wrapped, all 4 MCP tools referenced"
    - "scripts/count-tokens.ts — token counting script; reads file from argv, applies 1.3 multiplier, reports PASS/FAIL, exits 0/1"
  modified:
    - "package.json — added count-tokens script entry"

key-decisions:
  - "SKILL.md uses static checked-in file (not runtime-generated) — simpler, survives MCP server restarts, inspectable"
  - "Token budget heuristic: words x 1.3 — sufficient without tiktoken; 600-token ceiling has enough margin for word-count precision"
  - "Memory search and projection sections use placeholder guidance for Phase 4 — not premature implementation"

requirements-completed: [SKIL-01, SKIL-02, SKIL-03, SKIL-04]

# Metrics
duration: ~3min
completed: 2026-03-26
---

# Phase 01 Plan 05: SKILL.md and Token Counting Script Summary

**SKILL.md portability layer with <identity> XML wrapper, all four MCP tool references, and verified 349-token budget via count-tokens.ts script**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-26T03:00:00Z
- **Completed:** 2026-03-26T03:03:00Z
- **Tasks:** 2 of 2 complete
- **Files modified:** 3

## Accomplishments

- `SKILL.md` at repo root: 268 words, 349 estimated tokens (well under 600-token budget), wrapped in `<identity>` XML tag, references all four MCP tools (`identity_context`, `identity_query`, `projects_list`, `verify_integrity`), includes Projection Rules and Memory Search sections
- `scripts/count-tokens.ts` reads a file path from argv, applies `Math.ceil(words * 1.3)` heuristic, reports PASS/FAIL with full metrics, exits 0 on pass — runs clean with `npx tsx scripts/count-tokens.ts SKILL.md`
- `package.json` updated with `"count-tokens": "tsx scripts/count-tokens.ts"` script entry

## Task Commits

Each task was committed atomically:

1. **Task 1: Write production SKILL.md with identity XML wrapper under 600-token budget** — `0dbe269` (feat)
2. **Task 2: Create token counting verification script** — `7574ee4` (feat)

## Files Created/Modified

- `SKILL.md` — Production AI instruction file; 268 words, 349 estimated tokens; `<identity>` XML wrapper; references identity_context, identity_query, projects_list, verify_integrity; Projection Rules and Memory Search sections
- `scripts/count-tokens.ts` — Token counting verification script; word-count x 1.3 heuristic; 600-token budget check; exit 0 on pass, exit 1 on fail; all output via console.error()
- `package.json` — Added `count-tokens` script

## Decisions Made

- **Static SKILL.md**: Checked into repo rather than runtime-generated. Survives MCP server restarts, is inspectable by humans, and can be version-controlled alongside code changes.
- **Word-count heuristic**: `Math.ceil(words * 1.3)` from RESEARCH.md Pattern 5. No tiktoken dependency required — the 600-token ceiling has enough margin that ±10% precision is fine.
- **Placeholder sections**: Memory Search and Projection Rules sections provide correct guidance structure now; implementation wired in Phase 4 (memory) and Phase 2 (projections).

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — SKILL.md is fully wired. The Memory Search section correctly directs users to call `identity_query`, which is implemented in Plan 01-04. The Projection Rules section is intentionally generic for Phase 1 — Phase 2 will add specific projection configuration.

## Issues Encountered

None.

## Next Phase Readiness

- SKILL.md is the complete portability layer — any AI provider can inject it as a system prompt prefix and immediately know how to use the identity store
- Claude Desktop can be configured to include SKILL.md content; or it is read on-demand via MCP tool
- Phase 01 foundation is complete: schema, MongoDB seeding, MCP server, identity_context, projects_list, identity_query, verify_integrity, SKILL.md, and token verification

## Self-Check: PASSED

- FOUND: SKILL.md
- FOUND: scripts/count-tokens.ts
- FOUND: package.json with count-tokens script
- FOUND: commit 0dbe269 (Task 1)
- FOUND: commit 7574ee4 (Task 2)

---
*Phase: 01-foundation*
*Completed: 2026-03-26*
