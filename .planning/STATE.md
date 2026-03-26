---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Ready to plan
stopped_at: Completed 02-projection-engine-recruiter-chatbot-05-PLAN.md
last_updated: "2026-03-26T10:14:12.325Z"
progress:
  total_phases: 5
  completed_phases: 2
  total_plans: 10
  completed_plans: 10
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-26)

**Core value:** Any AI, any provider, reads the same you — without repeating yourself, and without any company owning the relationship you've built.
**Current focus:** Phase 02 — projection-engine-recruiter-chatbot

## Current Position

Phase: 3
Plan: Not started

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: -

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01-foundation P01 | 18 | 2 tasks | 9 files |
| Phase 01-foundation P02 | 8 | 2 tasks | 4 files |
| Phase 01-foundation P02 | 120 | 3 tasks | 4 files |
| Phase 01-foundation P03 | 2 | 2 tasks | 3 files |
| Phase 01-foundation P04 | 2 | 2 tasks | 3 files |
| Phase 01-foundation P05 | 514075 | 2 tasks | 3 files |
| Phase 02-projection-engine-recruiter-chatbot P01 | 10 | 2 tasks | 8 files |
| Phase 02-projection-engine-recruiter-chatbot P02 | 4 | 2 tasks | 11 files |
| Phase 02-projection-engine-recruiter-chatbot P03 | 3 | 2 tasks | 7 files |
| Phase 02-projection-engine-recruiter-chatbot P04 | 2 | 2 tasks | 1 files |
| Phase 02-projection-engine-recruiter-chatbot P05 | 4 | 2 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Schema: Four sensitivity tiers — `public`, `professional`, `personal`, `private` — drive projection enforcement from day one
- MongoDB: Single unified `embedding` field across all document types; M0 one-index limit is a hard constraint; design before ingesting any data
- Auth: Start with fine-grained PAT for sync pipeline, document GitHub App upgrade path; abstract via environment variable
- Projections: Whitelist model enforced in `applyProjection()` inside every tool handler; no-scope default is `public`, never `owner`
- Logging: `console.error()` everywhere in MCP server; `console.log()` is banned — stdout contamination silently corrupts JSON-RPC
- [Phase 01-foundation]: Used ajv/dist/2020.js import for JSON Schema draft 2020-12 support — base Ajv class only handles draft-07
- [Phase 01-foundation]: additionalProperties: true on schema sections to allow future fields without breaking validation
- [Phase 01-foundation]: relationships section included with _sensitivity: private — most sensitive data in identity document
- [Phase 01-foundation]: OpenAI text-embedding-3-small (1536 dims) confirmed as embedding model — locks Atlas vector index numDimensions; cannot change without collection drop and reindex
- [Phase 01-foundation]: relationships section excluded from MongoDB seed — _sensitivity:private, not needed for Phase 1 MCP tools; 4 sections loaded: persona, skills, projects, values
- [Phase 01-foundation]: STUB_EMBEDDINGS=1 returns zero-vector (1536 zeros) from embedText — lets seed run without OpenAI quota; zero-vectors are semantically inert but structurally correct; real embeddings must be regenerated before Plan 01-04 vector search is useful
- [Phase 01-foundation]: relationships section excluded from MongoDB seed — _sensitivity:private, not needed for Phase 1 MCP tools; 4 sections loaded: persona, skills, projects, values
- [Phase 01-foundation]: Tool registration pattern: registerXxxTool(server: McpServer) — keeps tool modules independently testable and avoids circular imports
- [Phase 01-foundation]: Token budget for identity_context: word-count heuristic (words x 1.3) sufficient for 1200-token ceiling without pulling in tiktoken
- [Phase 01-foundation]: doc_type pre-filter in $vectorSearch runs inside Atlas ANN pass — excludes Phase 4 memory chunks before scoring, not post-filter
- [Phase 01-foundation]: verify_integrity uses execSync for git SHA — synchronous is appropriate for a single-command tool handler; Phase 3 attestation chain deferred
- [Phase 01-foundation]: SKILL.md is a static checked-in file (not runtime-generated) — survives restarts, inspectable, version-controlled
- [Phase 01-foundation]: Token budget for SKILL.md: words x 1.3 heuristic — no tiktoken needed; 268 words = 349 estimated tokens, well under 600
- [Phase 02-projection-engine-recruiter-chatbot]: applyProjection() returns [] when projection is null/undefined — fail closed, never fall back to full docs
- [Phase 02-projection-engine-recruiter-chatbot]: loadProjections() throws on any invalid projection file rather than skipping — startup failure preferred over silent data leak
- [Phase 02-projection-engine-recruiter-chatbot]: MCP tools default to personal projection — owner tools see everything; optional param preserves backward compatibility
- [Phase 02-projection-engine-recruiter-chatbot]: authMiddleware blocks personal/owner projection names at middleware boundary — defense in depth even if TOKEN_MAP misconfigured
- [Phase 02-projection-engine-recruiter-chatbot]: chatbot-worker has its own package.json with mongodb/openai — Cloudflare Workers bundles at deploy time, cannot share root node_modules
- [Phase 02-projection-engine-recruiter-chatbot]: Inline PROJECTIONS constant in identity.ts — wrangler esbuild cannot read filesystem at Worker runtime; embedding projection definitions as TypeScript constants is the correct Worker pattern
- [Phase 02-projection-engine-recruiter-chatbot]: waitUntil for audit — Cloudflare Workers ctx.waitUntil() keeps Worker alive to complete background task after response is sent; this is the idiomatic non-blocking pattern for Workers
- [Phase 02-projection-engine-recruiter-chatbot]: gpt-4o-mini for chatbot — 15x cheaper than gpt-4o; sufficient for professional projection Q&A; model name in one env var for easy override
- [Phase 02-projection-engine-recruiter-chatbot]: fetch() + ReadableStream over EventSource for recruiter chat UI — EventSource cannot set Authorization header; fetch-streaming required for Bearer token auth pattern
- [Phase 02-projection-engine-recruiter-chatbot]: Token in ?token= query string for recruiter UI — zero-friction shareable URL; acceptable for Phase 2 professional-projection-only scope despite log exposure
- [Phase 02-projection-engine-recruiter-chatbot]: Dynamic import for loadProjections inside tool handler — avoids circular import risk and keeps projection check self-contained
- [Phase 02-projection-engine-recruiter-chatbot]: Refusal pattern 'not able to share' in demo script matches exact text in buildSystemPrompt OUT OF SCOPE clause

### Pending Todos

None yet.

### Blockers/Concerns

- Projection token format (plain string vs signed JWT), TTL, and revocation must be decided before Phase 2 planning
- Embedding model choice (OpenAI text-embedding-3-small vs local Ollama) must be confirmed before Phase 4 — affects Phase 3 sync pipeline if embeddings are generated at sync time
- Memory ingestion trigger (manual CLI vs upload Action) undefined — decide before Phase 4 planning

## Session Continuity

Last session: 2026-03-26T10:10:37.246Z
Stopped at: Completed 02-projection-engine-recruiter-chatbot-05-PLAN.md
Resume file: None
