---
phase: 01-foundation
plan: 02
subsystem: database
tags: [mongodb, openai, embeddings, vector-search, typescript]

# Dependency graph
requires:
  - phase: 01-foundation-01
    provides: "TypeScript types (IdentityDocument, IdentitySection, SensitivityLevel), nick-identity.json seed data, project scaffold"
provides:
  - "Lazy MongoDB singleton connection via getDb() (MCP-06)"
  - "OpenAI text-embedding-3-small embedding utility via embedText()"
  - "Idempotent seed script loading 4 identity sections into MongoDB with 1536-dim embeddings"
  - "Dry-run mode for validating seed data without touching MongoDB"
affects:
  - "01-03 (MCP tools that query MongoDB identity collection)"
  - "01-04 (SKILL.md — no direct dependency but same MCP stack)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy singleton pattern for both MongoDB (getDb) and OpenAI clients — mirrors MCP-06 pattern from RESEARCH.md"
    - "upsert:true with section discriminator filter — idempotent seed pipeline"
    - "Top-level sensitivity field extracted from _sensitivity in JSON, stripped from content"
    - "console.error() only — never console.log() — enforced in all seed/DB/embed code"

key-files:
  created:
    - "src/db.ts — lazy MongoClient singleton; exports getDb() and closeDb()"
    - "src/embed.ts — OpenAI embedding client; exports embedText(), EMBEDDING_MODEL, EMBEDDING_DIMENSIONS"
    - "scripts/seed-mongodb.ts — idempotent seed script with --dry-run support"
  modified:
    - "package.json — added seed and seed:dry-run npm scripts"

key-decisions:
  - "OpenAI text-embedding-3-small (1536 dims) confirmed as embedding model — locks Atlas vector index dimensions"
  - "relationships section excluded from MongoDB seed — private sensitivity, not needed for Phase 1 MCP tools"
  - "sectionToText() serializes section data as JSON.stringify with section name prefix for semantic embedding quality"

patterns-established:
  - "Pattern: Lazy singleton with module-level null variable — both getDb() and getOpenAI() follow same init-on-first-call pattern"
  - "Pattern: Upsert filter {doc_type, section} — all future seed/sync scripts should use same discriminator"
  - "Pattern: _sensitivity extracted to top-level, stripped from content before storage"

requirements-completed:
  - MCP-06

# Metrics
duration: 8min
completed: 2026-03-26
---

# Phase 1 Plan 02: MongoDB Data Layer Summary

**Lazy MongoDB singleton (MCP-06) + OpenAI text-embedding-3-small utility + idempotent seed script for 4 identity sections — paused at Atlas provisioning checkpoint**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-25T23:54:24Z
- **Completed:** 2026-03-26T00:02:00Z
- **Tasks:** 2 of 3 automated tasks complete (Task 3 is human-action checkpoint)
- **Files modified:** 4

## Accomplishments
- MongoDB lazy singleton in `src/db.ts` — single connection cached for process lifetime, compatible with MCP-06 requirement
- OpenAI embedding utility in `src/embed.ts` — uses text-embedding-3-small (1536 dims) matching planned Atlas vector index
- Seed script with `--dry-run` verified showing all 4 sections (persona, skills, projects, values) with correct sensitivity levels
- Both db.ts and embed.ts follow lazy init pattern — clients created only on first call, never at import time

## Task Commits

Each automated task was committed atomically:

1. **Task 1: MongoDB lazy singleton and OpenAI embedding utility** - `4a3533d` (feat)
2. **Task 2: Seed script to load identity sections into MongoDB** - `76285dc` (feat)

Task 3 (Atlas provisioning + vector index) is a blocking human-action checkpoint — not committed.

## Files Created/Modified
- `src/db.ts` - Lazy MongoClient singleton; `getDb()` and `closeDb()` exports; console.error only
- `src/embed.ts` - OpenAI embeddings client; `embedText()`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` exports
- `scripts/seed-mongodb.ts` - Reads nick-identity.json, embeds 4 sections, upserts into MongoDB identity collection; supports `--dry-run`
- `package.json` - Added `seed` and `seed:dry-run` npm scripts

## Decisions Made
- OpenAI text-embedding-3-small (1536 dims) is the embedding model — this locks the Atlas vector index `numDimensions`. Cannot be changed without dropping the collection and recreating the index.
- `relationships` section excluded from seed — it has `_sensitivity: private` and is not needed by Phase 1 MCP tools. The 4 sections seeded are: persona, skills, projects, values.
- Text representation for embedding: `"Section: {name}\n{JSON.stringify(content)}"` — preserves structure while being semantically meaningful

## Deviations from Plan

None — plan executed exactly as written.

## User Setup Required

Task 3 requires manual Atlas provisioning. After completing the checkpoint steps:

1. Create MongoDB Atlas M0 free cluster
2. Create database user and add IP to network access
3. Create `.env` file with `MONGODB_URI`, `MONGODB_DB_NAME=breakfast-club`, `OPENAI_API_KEY`
4. Run `npm run seed` to load the 4 identity sections
5. Create vector search index `identity_vector_index` in Atlas UI:
   ```json
   {
     "fields": [
       { "type": "vector", "path": "embedding", "numDimensions": 1536, "similarity": "cosine" },
       { "type": "filter", "path": "doc_type" },
       { "type": "filter", "path": "sensitivity" }
     ]
   }
   ```

## Next Phase Readiness
- `src/db.ts` and `src/embed.ts` are ready for import by MCP tool handlers (Plan 01-03)
- Once Atlas is provisioned and seeded, Plan 01-03 can build identity_query, identity_context, projects_list, verify_integrity tools
- Vector index must be created BEFORE Plan 01-03 tools are tested end-to-end

---
*Phase: 01-foundation*
*Completed: 2026-03-26*
