---
phase: 02-projection-engine-recruiter-chatbot
plan: 05
subsystem: mcp,tooling
tags: [health-check, mcp-tool, demo, streaming, validation]

requires:
  - phase: 02-projection-engine-recruiter-chatbot
    plan: 04
    provides: Recruiter chat UI served as Cloudflare Worker static asset

provides:
  - breakfast_club_status MCP tool checking MongoDB, projection engine, and chatbot Worker health
  - scripts/demo-prep.ts three-interaction demo validation script
  - Pre-built TypeScript in build/ directory

affects: []

tech-stack:
  added: []
  patterns:
    - "registerXxxTool(server: McpServer) pattern — new tool follows established registration convention"
    - "Dynamic import inside tool handler for projection engine check — avoids module-level side effects"
    - "AbortSignal.timeout(5000) for Worker health fetch — prevents hanging on unresponsive endpoint"
    - "Streaming response consumption via ReadableStream + TextDecoder in demo script"

key-files:
  created:
    - src/tools/breakfast-club-status.ts
    - scripts/demo-prep.ts
  modified:
    - src/index.ts
    - package.json

key-decisions:
  - "Dynamic import for loadProjections inside tool handler — avoids circular import risk and keeps projection check self-contained"
  - "Refusal patterns array in demo script includes 'not able to share' — matches exact text in buildSystemPrompt OUT OF SCOPE response"

requirements-completed: [RCTR-02, RCTR-03]

duration: 4min
completed: 2026-03-26
---

# Phase 02 Plan 05: Demo Preparation Summary

**breakfast_club_status MCP tool + demo-prep script giving a single-command health check and three-interaction narrative validation before the James MacDonald demo**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-26T10:08:14Z
- **Completed:** 2026-03-26T10:12:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `src/tools/breakfast-club-status.ts` — `breakfast_club_status` MCP tool with three checks: MongoDB (`countDocuments` on identity collection), projection engine (`loadProjections` from projections/ dir), and optional chatbot Worker (`GET /health`)
- Registered tool in `src/index.ts` after existing tools — follows `registerXxxTool(server)` pattern
- Created `scripts/demo-prep.ts` — runs three scripted POST /chat interactions with streaming response consumption
  - Interaction 1: role-fit question — expects > 50 chars
  - Interaction 2: technical skills question — expects > 30 chars
  - Interaction 3: salary question — expects refusal containing "not able to share" (matches `buildSystemPrompt` OUT OF SCOPE text)
- Added `"demo-prep": "tsx scripts/demo-prep.ts"` to `package.json` scripts
- `npm run build` succeeds — `build/` is current and pre-built for deployment

## Task Commits

1. **Task 1: breakfast_club_status health-check MCP tool** — `db2ef8f`
2. **Task 2: Demo preparation script with three-interaction narrative** — `03d5a6d`

## Files Created/Modified

- `src/tools/breakfast-club-status.ts` — 104-line health-check tool
- `src/index.ts` — added import and registration of breakfast_club_status
- `scripts/demo-prep.ts` — 107-line demo validation script
- `package.json` — added demo-prep npm script

## Decisions Made

- Dynamic import for `loadProjections` inside tool handler: avoids module-level side effects and circular import risk; projection check is fully self-contained
- Refusal pattern "not able to share" in demo script: matches exact wording in `buildSystemPrompt()` OUT OF SCOPE clause — salary refusal detection is reliable

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — the health-check tool makes live checks against real services. The demo script requires a deployed Worker (CHATBOT_URL env var) to run; it is not a stub but a validation tool that requires the deployment step.

## Issues Encountered

None.

## User Setup Required

Before running `npm run demo-prep`, set:
- `CHATBOT_URL` — deployed Worker URL (e.g. `https://breakfast-club-chatbot.workers.dev`)
- `CHATBOT_TOKEN` — optional; omit for public projection, provide for professional projection

## Phase 02 Complete

All five plans executed. The full stack is built and pre-compiled:
- Projection engine (02-01)
- Cloudflare Worker chatbot backend (02-02, 02-03)
- Recruiter chat UI (02-04)
- Health check + demo validation (02-05)

Remaining step: `wrangler deploy` in the chatbot-worker directory with secrets set (MONGODB_URI, OPENAI_API_KEY, TOKEN_MAP, GITHUB_TOKEN).

---
*Phase: 02-projection-engine-recruiter-chatbot*
*Completed: 2026-03-26*
