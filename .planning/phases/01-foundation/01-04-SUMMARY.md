---
phase: 01-foundation
plan: 04
subsystem: mcp-server
tags: [typescript, mcp, mongodb, vector-search, openai, embeddings, child_process]

# Dependency graph
requires:
  - phase: 01-foundation-02
    provides: "getDb() MongoDB singleton, identity_vector_index on Atlas, 4 identity documents seeded"
  - phase: 01-foundation-03
    provides: "McpServer entry point (src/index.ts), tool registration pattern, embedText() from src/embed.ts"

provides:
  - "identity_query tool — natural-language vector search over identity collection via MongoDB Atlas $vectorSearch"
  - "verify_integrity tool — git tree SHA retrieval via execSync('git rev-parse HEAD') with Phase 3 attestation note"
  - "All four MCP tools registered in src/index.ts: identity_context, projects_list, identity_query, verify_integrity"

affects:
  - "Claude Desktop — all four tools now visible via tools/list once server is registered"
  - "Phase 3 — verify_integrity attestation chain check is stub returning pending note; Phase 3 must implement full cross-verification"

# Tech tracking
tech-stack:
  added:
    - "node:child_process execSync — synchronous git command execution for SHA retrieval"
  patterns:
    - "MongoDB $vectorSearch aggregation: index=identity_vector_index, path=embedding, numCandidates=50, filter={doc_type:identity}"
    - "Pre-filter doc_type=identity in $vectorSearch — excludes future Phase 4 memory chunks at query time, not post-filter"
    - "Limit clamping: Math.max(1, Math.min(10, limit)) — defensive bounds enforcement regardless of Zod defaults"
    - "execSync try/catch with human-readable fallback — tool never throws when git fails; returns descriptive error message"

key-files:
  created:
    - "src/tools/identity-query.ts — identity_query tool; embedText() at call time; $vectorSearch with doc_type pre-filter; formats results with section/score/sensitivity/content"
    - "src/tools/verify-integrity.ts — verify_integrity tool; execSync git rev-parse HEAD; Phase 3 attestation pending note; graceful git failure fallback"
  modified:
    - "src/index.ts — added imports and registration calls for identity_query and verify_integrity; all four tools now registered"

key-decisions:
  - "doc_type pre-filter in $vectorSearch (not post-filter): filter runs inside Atlas ANN pass, excluding memory chunks before scoring; more efficient and correct"
  - "execSync over exec for git SHA: single synchronous command is simpler and appropriate for MCP tool handler — no callback/promise plumbing needed"
  - "Phase 3 attestation as informational note (not error): RESEARCH.md recommends returning pending status rather than failing — keeps tool useful from day one"
  - "limit clamped to 1-10 with Zod default 5: defensive bounds prevent absurdly large Atlas queries while Zod provides schema-level documentation"

# Metrics
duration: ~2min
completed: 2026-03-26
---

# Phase 01 Plan 04: Vector Search and Integrity Tools Summary

**identity_query performs MongoDB Atlas $vectorSearch with OpenAI embedding and doc_type pre-filter; verify_integrity returns git tree SHA via execSync; all four MCP tools registered in src/index.ts; server builds and starts with zero stdout contamination**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-26T02:53:28Z
- **Completed:** 2026-03-26T02:54:45Z
- **Tasks:** 2 of 2 complete
- **Files modified:** 3

## Accomplishments

- `src/tools/identity-query.ts` implements `identity_query` tool: embeds the question via `embedText()` at call time, runs `$vectorSearch` on `identity_vector_index` with `numCandidates: 50` and `filter: { doc_type: "identity" }`, formats results with section/relevance score/sensitivity/content JSON, returns "No identity data found" when empty
- `src/tools/verify-integrity.ts` implements `verify_integrity` tool: executes `git rev-parse HEAD` via `execSync`, catches git failures with human-readable error message (no throw), returns Phase 3 attestation pending note in all success paths
- `src/index.ts` updated to import and register both new tools — all four tools (`identity_context`, `projects_list`, `identity_query`, `verify_integrity`) now registered
- `npm run build` compiles without errors — TypeScript strict mode satisfied
- Zero `console.log` in `src/` — all logging via `console.error()` per MCP-07

## Task Commits

Each task was committed atomically:

1. **Task 1: identity_query tool with MongoDB Atlas vector search** — `1ecb561` (feat)
2. **Task 2: verify_integrity tool and all four tools registered in index.ts** — `1d5c351` (feat)

## Files Created/Modified

- `src/tools/identity-query.ts` — identity_query tool; embedText() embedding; $vectorSearch aggregation; doc_type pre-filter; score/section/sensitivity formatting
- `src/tools/verify-integrity.ts` — verify_integrity tool; execSync git rev-parse HEAD; try/catch fallback; Phase 3 attestation pending note
- `src/index.ts` — added imports and registration calls for identity_query and verify_integrity

## Decisions Made

- **Pre-filter in $vectorSearch**: `filter: { doc_type: "identity" }` runs inside the Atlas ANN candidate pass, not as a post-filter. This excludes Phase 4 memory chunks before scoring rather than filtering out results after retrieval — semantically correct and more efficient.
- **execSync for git SHA**: Single synchronous `git rev-parse HEAD` is appropriate for a tool handler. No async/callback overhead. Wrapped in try/catch so git failures return a descriptive message without crashing the server.
- **Phase 3 attestation as pending note**: Following RESEARCH.md recommendation — return a useful response immediately rather than an error. The tool is functional from Phase 1; the attestation chain check is an additive Phase 3 feature.
- **limit clamped 1–10**: `Math.max(1, Math.min(10, limit ?? 5))` enforces bounds defensively regardless of Zod validation, preventing extremely large Atlas ANN queries.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

One known limitation from Plan 01-02 carries forward: the 4 identity documents in Atlas have zero-vector embeddings (seeded with `STUB_EMBEDDINGS=1`). The `identity_query` tool is fully implemented and structurally correct, but vector search results will be semantically meaningless until real embeddings are generated. This is documented in STATE.md and must be resolved before Phase 2 demo work.

The tool itself is NOT stubbed — the code correctly embeds questions at query time and runs `$vectorSearch`. The data is the limitation, not the tool.

## Issues Encountered

None.

## Next Phase Readiness

- All four MCP tools registered — server can be registered with Claude Desktop using `build/index.js` with `MONGODB_URI` and `OPENAI_API_KEY` env vars
- `verify_integrity` returns git SHA immediately; Phase 3 must add cross-verification with public attestation log
- Real embeddings must be regenerated (drop zero-vectors, re-seed with `OPENAI_API_KEY` set) before `identity_query` is semantically useful

## Self-Check: PASSED

- FOUND: src/tools/identity-query.ts
- FOUND: src/tools/verify-integrity.ts
- FOUND: src/index.ts (modified — registerIdentityQueryTool + registerVerifyIntegrityTool)
- FOUND: build/index.js (npm run build succeeded)
- FOUND: commit 1ecb561 (Task 1)
- FOUND: commit 1d5c351 (Task 2)

---
*Phase: 01-foundation*
*Completed: 2026-03-26*
