---
phase: 02-projection-engine-recruiter-chatbot
plan: 03
subsystem: api,chatbot
tags: [hono, cloudflare-workers, openai, mongodb, octokit, streaming, audit, node-test, typescript]

requires:
  - phase: 02-projection-engine-recruiter-chatbot
    plan: 02
    provides: chatbot-worker scaffold with Hono, wrangler.toml (nodejs_compat_v2), Env types, authMiddleware (Bearer token to projection name)
  - phase: 02-projection-engine-recruiter-chatbot
    plan: 01
    provides: projection engine design and applyProjection() patterns

provides:
  - POST /chat route streaming OpenAI gpt-4o-mini responses grounded in MongoDB identity data
  - System prompt constraining chatbot to role-fit/experience/logistics; salary and personal data refused
  - GitHub JSONL audit trail (non-blocking) appended via waitUntil after each query
  - getDb() MongoDB Worker-compatible connection with M0 reconnect logic
  - getIdentityForProjection() with inline projection filter (fail-closed)
  - buildSystemPrompt() + createChatStream() OpenAI helpers
  - appendAuditEntry() with optional Octokit override for testability; 5 passing unit tests

affects:
  - 02-04 (static recruiter UI — fetches POST /chat, reads streaming text response)
  - 02-05 (deployment and e2e validation — wrangler deploy, smoke tests)

tech-stack:
  added: []
  patterns:
    - "Inline PROJECTIONS constant in Worker identity module — Worker can't read filesystem at runtime, projection definitions embedded as TypeScript constants"
    - "waitUntil(appendAuditEntry(...)) pattern — audit write dispatched as background task after streaming response starts; never blocks first token"
    - "Optional octokitOverride parameter on appendAuditEntry — enables unit testing via dependency injection without module mocking"
    - "atob/btoa polyfill via Object.defineProperty in test files — Workers globals not available in tsx test runner"
    - "sha256 via crypto.subtle.digest — no Node crypto needed; works in Workers and tsx test runner"

key-files:
  created:
    - chatbot-worker/src/lib/db.ts
    - chatbot-worker/src/lib/identity.ts
    - chatbot-worker/src/lib/openai.ts
    - chatbot-worker/src/lib/audit.ts
    - chatbot-worker/src/lib/audit.test.ts
    - chatbot-worker/src/routes/chat.ts
  modified:
    - chatbot-worker/src/index.ts

key-decisions:
  - "Inline PROJECTIONS constant in identity.ts — wrangler esbuild cannot read filesystem at Worker runtime; embedding projection definitions as TypeScript constants is the correct Worker pattern"
  - "waitUntil for audit — Cloudflare Workers ctx.waitUntil() keeps Worker alive to complete background task after response is sent; this is the idiomatic non-blocking pattern for Workers"
  - "gpt-4o-mini — chosen per RESEARCH.md recommendation; owner can override model name in one env var if quality is insufficient"
  - "Optional octokitOverride in appendAuditEntry — cleanest testability solution without module-level mocking; production path creates Octokit from env"

requirements-completed: [RCTR-01, RCTR-02, RCTR-03, RCTR-05]

duration: 3min
completed: 2026-03-26
---

# Phase 02 Plan 03: Chatbot Backend — Chat Route and Audit Trail Summary

**POST /chat route streaming gpt-4o-mini responses grounded in MongoDB identity projection data, with non-blocking GitHub JSONL audit trail via Cloudflare Workers waitUntil**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-26T10:00:03Z
- **Completed:** 2026-03-26T10:02:28Z
- **Tasks:** 2 (both auto)
- **Files modified:** 7

## Accomplishments

- MongoDB Worker connection in db.ts with maxPoolSize:1, minPoolSize:0, serverSelectionTimeoutMS:5000 and M0 idle reconnect logic
- Identity retrieval in identity.ts with inline PROJECTIONS constant (public, professional) and fail-closed filter (`if (!projection) return []`)
- OpenAI helpers in openai.ts: buildSystemPrompt() with constrained scope/refusal text; createChatStream() using gpt-4o-mini with 10-message history cap
- GitHub JSONL audit writer in audit.ts: sha256-hashed query, 80-char preview, [skip ci] commit message, error swallowed (non-fatal)
- 5 audit tests covering: new file creation, append-to-existing with SHA pass-through, entry shape validation, preview truncation, and 409 conflict swallowing
- POST /chat route in routes/chat.ts: input validation, getIdentityForProjection(), buildSystemPrompt(), createChatStream(), waitUntil(appendAuditEntry()), Hono streamText()
- index.ts updated to mount chatRoute at /chat; placeholder comment removed

## Task Commits

1. **Task 1: MongoDB Worker connection, identity retrieval, and OpenAI streaming helpers** — `9e66789`
2. **Task 2: Chat route with audit trail and Worker integration** — `7e9d09d`

## Files Created/Modified

- `chatbot-worker/src/lib/db.ts` — getDb() with M0 reconnect logic and Worker-safe pool settings
- `chatbot-worker/src/lib/identity.ts` — getIdentityForProjection() with inline PROJECTIONS constant and fail-closed applyProjectionFilter()
- `chatbot-worker/src/lib/openai.ts` — buildSystemPrompt() with refusal scope; createChatStream() using gpt-4o-mini
- `chatbot-worker/src/lib/audit.ts` — appendAuditEntry() writing JSONL to GitHub via Octokit; errors swallowed
- `chatbot-worker/src/lib/audit.test.ts` — 5 unit tests using node:test and Octokit dependency injection
- `chatbot-worker/src/routes/chat.ts` — POST /chat handler with streaming and non-blocking audit
- `chatbot-worker/src/index.ts` — added chatRoute mount at /chat

## Decisions Made

- Inline PROJECTIONS constant in identity.ts: wrangler esbuild bundles Workers without filesystem access at runtime; projection definitions must be embedded as TypeScript constants, not loaded from JSON files
- waitUntil for audit: Cloudflare Workers `ctx.waitUntil()` is the idiomatic pattern for background tasks after response is sent — keeps Worker alive without blocking first token delivery
- gpt-4o-mini: RESEARCH.md recommendation; 15x cheaper than gpt-4o; sufficient for professional projection Q&A with structured identity context
- Optional octokitOverride in appendAuditEntry: cleanest testability approach without module mocking; test passes mock Octokit directly; production creates Octokit from env.GITHUB_TOKEN

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed unused @ts-expect-error directives in audit.test.ts polyfills**
- **Found during:** Task 2 verification (npx tsc --noEmit)
- **Issue:** TypeScript 6 TS2578 error — `@ts-expect-error` on globalThis.atob/btoa assignments that were already type-safe
- **Fix:** Replaced `@ts-expect-error` comments with `Object.defineProperty` pattern which is type-safe
- **Files modified:** chatbot-worker/src/lib/audit.test.ts
- **Verification:** npx tsc --noEmit exits 0 after fix
- **Committed in:** 7e9d09d (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in generated test code)
**Impact on plan:** Minor fix to test file polyfill pattern; no behavior change. No scope creep.

## Issues Encountered

None beyond the TS2578 deviation above.

## User Setup Required

None — no external service configuration required for this plan. Cloudflare account, GITHUB_TOKEN, and Worker secrets will be configured in Plan 02-05 when the chatbot is deployed.

## Next Phase Readiness

- POST /chat backend is fully functional; ready for Plan 02-04 to add the static HTML recruiter UI
- All TypeScript compiles cleanly under strict mode with @cloudflare/workers-types
- 5 audit tests pass — audit behavior verified including error swallowing
- Chat route uses authMiddleware set in Plan 02-02 — no changes needed to auth layer
- Worker is ready for `wrangler dev` local testing once MONGODB_URI and OPENAI_API_KEY are set in .dev.vars

---
*Phase: 02-projection-engine-recruiter-chatbot*
*Completed: 2026-03-26*
