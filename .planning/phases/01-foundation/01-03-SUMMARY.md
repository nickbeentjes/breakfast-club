---
phase: 01-foundation
plan: 03
subsystem: mcp-server
tags: [typescript, mcp, mongodb, zod, stdio, esm]

# Dependency graph
requires:
  - phase: 01-foundation-01
    provides: "TypeScript types (IdentityDocument, PersonaSection, SkillsSection, ProjectsSection), ESM project scaffold"
  - phase: 01-foundation-02
    provides: "getDb() MongoDB singleton, identity collection seeded with 4 documents"

provides:
  - "MCP server entry point (src/index.ts) with StdioServerTransport"
  - "identity_context tool — synthesizes persona/skills/projects from MongoDB within token budget"
  - "projects_list tool — returns active projects with name, status, description, stack"
  - "Two registered tools visible via tools/list on the MCP protocol"

affects:
  - "01-04 (identity_query and verify_integrity tool registration goes into same src/index.ts)"
  - "Claude Desktop config — register build/index.js as MCP server"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tool registration pattern: registerXxxTool(server: McpServer) — module exports a registration function that accepts the server instance; keeps tool modules independently testable"
    - "Token budget heuristic: Math.ceil(words * 1.3) — word count times 1.3 approximates English prose token count"
    - "StdioServerTransport: server.connect(transport) in async main(); SIGINT handler for graceful shutdown"
    - "console.error() only — zero stdout writes except JSON-RPC (MCP-07 enforced)"

key-files:
  created:
    - "src/index.ts — McpServer entry point; registers identity_context and projects_list tools; StdioServerTransport; SIGINT handler"
    - "src/tools/identity-context.ts — identity_context tool; queries all identity documents; assembles persona/skills/projects context; respects max_tokens budget"
    - "src/tools/projects-list.ts — projects_list tool; queries projects section document; formats active and optionally completed projects"
  modified: []

key-decisions:
  - "Tool modules accept McpServer as a parameter (not import it) — registration function pattern keeps tool modules independently testable and avoids circular imports"
  - "Token budget: cap active projects at 3 and use word-count heuristic (words x 1.3) — sufficient precision for 1200-token ceiling without pulling in tiktoken"
  - "projects_list queries by {doc_type: identity, section: projects} findOne — single targeted query vs scanning all docs"
  - "identity_context queries {doc_type: identity} find all then indexes by section in memory — 4 docs max; efficient for this scale"

# Metrics
duration: ~2min
completed: 2026-03-26
---

# Phase 01 Plan 03: MCP Server Entry Point and Tools Summary

**MCP server with stdio transport and two registered tools (identity_context, projects_list) that query MongoDB identity collection — TypeScript compiles clean, server starts without crash, zero stdout contamination**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-26T02:49:02Z
- **Completed:** 2026-03-26T02:51:05Z
- **Tasks:** 2 of 2 complete
- **Files modified:** 3

## Accomplishments

- `src/index.ts` creates `McpServer`, registers both tools, connects `StdioServerTransport` in `main()`, handles SIGINT gracefully — only `console.error()` writes (zero stdout contamination)
- `src/tools/identity-context.ts` implements `identity_context` tool: queries all identity documents, assembles a persona/skills/projects context string, respects `max_tokens` budget via word-count heuristic (words × 1.3), caps active projects at 3
- `src/tools/projects-list.ts` implements `projects_list` tool: targeted findOne query for the projects section document, formats active projects with name/status/description/stack, optional `include_completed` flag for completed projects
- `npm run build` compiles without errors — TypeScript strict mode satisfied
- Smoke test confirmed: `node build/index.js` starts, logs "Breakfast Club MCP server running on stdio" to stderr, waits for JSON-RPC input

## Task Commits

Each task was committed atomically:

1. **Task 1: MCP server entry point with stdio transport** — `c5e9a5a` (feat)
2. **Task 2: identity_context and projects_list tool handlers** — `88721df` (feat)

## Files Created/Modified

- `src/index.ts` — McpServer with StdioServerTransport; registers identity_context and projects_list tools; graceful SIGINT shutdown
- `src/tools/identity-context.ts` — identity_context tool; getDb() MongoDB query; token budget with word-count heuristic; Zod max_tokens param
- `src/tools/projects-list.ts` — projects_list tool; targeted findOne for projects section; Zod include_completed param; stack formatting

## Decisions Made

- **Registration function pattern**: `registerXxxTool(server: McpServer)` — each tool module exports a function that receives the server instance. Avoids global server import, prevents circular dependencies, and makes tool handlers independently testable.
- **Token budget approach**: `Math.ceil(text.split(/\s+/).length * 1.3)` word-count heuristic from RESEARCH.md. Simpler than pulling in tiktoken. The 1200-token ceiling has enough margin that ±10% precision is fine.
- **identity_context query**: `find({ doc_type: "identity" })` fetches all 4 sections, then indexes by `section` in memory. At 4 documents, full-scan is faster than 4 separate queries.
- **projects_list query**: `findOne({ doc_type: "identity", section: "projects" })` — targeted single-document query; only the projects section is needed.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — both tools are fully wired to MongoDB. The only known limitation from Plan 01-02 is that the 4 identity documents in Atlas currently have zero-vector embeddings (`STUB_EMBEDDINGS=1` was set during seed). This does not affect Plan 01-03 tools since `identity_context` and `projects_list` use standard find queries, not vector search.

## Issues Encountered

None.

## Next Phase Readiness

- MCP server entry point ready for Plans 01-04 additions (`identity_query`, `verify_integrity` tool registrations go in `src/index.ts`)
- Server can be registered with Claude Desktop now using `build/index.js` with `MONGODB_URI` env var
- Plans 01-04 can import the same `getDb()` and `McpServer` patterns established here

## Self-Check: PASSED

- FOUND: src/index.ts
- FOUND: src/tools/identity-context.ts
- FOUND: src/tools/projects-list.ts
- FOUND: build/index.js
- FOUND: commit c5e9a5a (Task 1)
- FOUND: commit 88721df (Task 2)

---
*Phase: 01-foundation*
*Completed: 2026-03-26*
