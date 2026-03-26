---
phase: 02-projection-engine-recruiter-chatbot
plan: 02
subsystem: api,chatbot
tags: [projection, mcp-tools, hono, cloudflare-workers, auth-middleware, node-test, typescript]

requires:
  - phase: 02-projection-engine-recruiter-chatbot
    plan: 01
    provides: applyProjection() filter function, loadProjections() loader, three built-in projection JSON files

provides:
  - All three MCP tool handlers filter output through applyProjection() with projection_name parameter
  - chatbot-worker/ Cloudflare Worker scaffold with Hono, wrangler.toml (nodejs_compat_v2), Env types
  - authMiddleware: Bearer token → projection name, public default, personal/owner blocked (fail-safe)

affects:
  - 02-03 (chatbot chat handler — adds POST /chat route to the scaffold, uses auth middleware)
  - All downstream MCP clients — tools now accept optional projection_name (backward compatible, default: personal)

tech-stack:
  added:
    - hono@4.12.9 (chatbot-worker)
    - wrangler@4.77.0 (chatbot-worker devDep)
    - @cloudflare/workers-types@4.20250320.0 (chatbot-worker devDep)
    - @octokit/rest@22.0.1 (chatbot-worker)
  patterns:
    - "Module-level cached projections loader: loaded once on first use, cached in module-scope variable"
    - "Projection filtering applied after MongoDB fetch, before response formatting"
    - "Auth middleware: token → projection map parsed from TOKEN_MAP env JSON string, fail-safe to public on no token"
    - "personal/owner projection names blocked in external auth middleware — locked security invariant"
    - "Hono createMiddleware with typed Bindings+Variables for type-safe env access"

key-files:
  created:
    - chatbot-worker/package.json
    - chatbot-worker/tsconfig.json
    - chatbot-worker/wrangler.toml
    - chatbot-worker/src/index.ts
    - chatbot-worker/src/types.ts
    - chatbot-worker/src/middleware/auth.ts
    - chatbot-worker/src/middleware/auth.test.ts
    - chatbot-worker/public/.gitkeep
  modified:
    - src/tools/identity-context.ts
    - src/tools/identity-query.ts
    - src/tools/projects-list.ts

key-decisions:
  - "MCP tools default to personal projection — owner tools see everything; optional param preserves backward compatibility"
  - "Module-level cached projections loader in each tool file — projections loaded once, not per request"
  - "authMiddleware blocks personal/owner projection names at the middleware boundary — even if someone maps a token to those values in TOKEN_MAP"
  - "chatbot-worker has its own node_modules with mongodb and openai — Workers bundle at deploy time, cannot share root node_modules"

duration: 4min
completed: 2026-03-26
---

# Phase 02 Plan 02: MCP Projection Integration + Worker Scaffold Summary

**Projection filtering wired into all three MCP tool handlers (default: personal) + Cloudflare Worker scaffold with Hono, wrangler.toml (nodejs_compat_v2), and auth middleware that maps Bearer tokens to projection names**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-26T09:54:18Z
- **Completed:** 2026-03-26T09:57:45Z
- **Tasks:** 2 (both auto)
- **Files modified:** 11

## Accomplishments

- Three MCP tool handlers now filter all output through applyProjection() before returning — projection_name parameter added to each (optional, defaults to "personal" for full owner access, backward compatible)
- identity_context.ts: filteredDocs indexed by section instead of raw docs; projection name logged in console.error
- identity_query.ts: vectorSearch results mapped to IdentityDocument shape for projection filtering, filtered array used for output formatting
- projects_list.ts: doc wrapped in array for applyProjection(), undefined result handled with "No projects data available for this projection" message
- chatbot-worker/ scaffolded: package.json, tsconfig.json, wrangler.toml (nodejs_compat_v2 flag), public/ directory
- Env interface defines TOKEN_MAP as JSON string field — token-to-projection binding
- authMiddleware: parses TOKEN_MAP, resolves Bearer token to projection name, defaults to "public" for no-token requests, blocks personal/owner with 403
- 7 auth middleware tests — all pass with node:test + tsx

## Task Commits

1. **Task 1: Integrate applyProjection into MCP tool handlers** — `d2ee046`
2. **Task 2: Scaffold Cloudflare Worker project** — `4c800b7`

## Files Created/Modified

- `src/tools/identity-context.ts` — added projection_name param, applyProjection() filter, cached projections loader
- `src/tools/identity-query.ts` — added projection_name param, applyProjection() on vectorSearch results
- `src/tools/projects-list.ts` — added projection_name param, applyProjection() on projects doc
- `chatbot-worker/package.json` — hono, mongodb, openai, @octokit/rest deps
- `chatbot-worker/tsconfig.json` — Worker TypeScript config (moduleResolution: bundler)
- `chatbot-worker/wrangler.toml` — Worker config with nodejs_compat_v2 flag
- `chatbot-worker/src/index.ts` — Hono app with CORS and /health route
- `chatbot-worker/src/types.ts` — Env interface with TOKEN_MAP
- `chatbot-worker/src/middleware/auth.ts` — authMiddleware with token-to-projection resolution
- `chatbot-worker/src/middleware/auth.test.ts` — 7 unit tests covering all auth scenarios
- `chatbot-worker/public/.gitkeep` — placeholder for Cloudflare static assets directory

## Decisions Made

- MCP tools default to personal projection: owner gets full access without changing existing workflows; projection_name is optional with a backward-compatible default
- Cached projections at module level: loadProjections() is called once per process rather than on every tool invocation
- authMiddleware blocks personal/owner even if TOKEN_MAP tries to map a token there — defense in depth at the middleware boundary
- chatbot-worker has its own package.json with mongodb/openai listed explicitly — Cloudflare Workers bundles everything at deploy time; root node_modules are not available

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. TypeScript compiled cleanly in both root project and chatbot-worker. All 7 auth middleware tests passed on first run.

## User Setup Required

None — no external service configuration required for this plan. Cloudflare account and TOKEN_MAP secret will be configured in Plan 02-03 when the chatbot is deployed.

## Next Phase Readiness

- chatbot-worker/ scaffold is ready for Plan 02-03 to add POST /chat route with OpenAI streaming
- authMiddleware is fully tested and ready to be wired into chat routes
- All MCP tools now enforce projection filtering — any future tool additions should follow the same pattern (add projection_name param, call getProjections() + applyProjection())

---
*Phase: 02-projection-engine-recruiter-chatbot*
*Completed: 2026-03-26*

## Self-Check: PASSED

All 12 files found on disk. Both task commits verified in git history (d2ee046, 4c800b7).
