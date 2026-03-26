---
phase: 01-foundation
plan: 02
subsystem: database
tags: [mongodb, mongodb-atlas, openai, embeddings, vector-search, typescript]

# Dependency graph
requires:
  - phase: 01-foundation-01
    provides: "TypeScript types (IdentityDocument, IdentitySection, SensitivityLevel), nick-identity.json seed data, project scaffold"
provides:
  - "Lazy MongoDB singleton connection via getDb() (MCP-06)"
  - "OpenAI text-embedding-3-small embedding utility via embedText()"
  - "Idempotent seed script loading 4 identity sections into MongoDB with 1536-dim embeddings"
  - "Dry-run mode for validating seed data without touching MongoDB"
  - "Live MongoDB Atlas M0 cluster at breakfast-club.7bofp2n.mongodb.net"
  - "identity_vector_index vector search index (cosine, 1536 dims, doc_type + sensitivity filters)"
  - "STUB_EMBEDDINGS=1 escape hatch for zero-quota / CI environments"
affects:
  - "01-03 (MCP server needs getDb() to query identity collection)"
  - "01-04 (identity_query tool uses identity_vector_index)"
  - "04-03 (memory ingestion shares single vector index)"

# Tech tracking
tech-stack:
  added: [mongodb, openai, dotenv, tsx]
  patterns:
    - "Lazy singleton pattern for both MongoDB (getDb) and OpenAI clients — mirrors MCP-06 pattern from RESEARCH.md"
    - "upsert:true with {doc_type, section} discriminator filter — idempotent seed pipeline"
    - "Top-level sensitivity field extracted from _sensitivity in JSON, stripped from content"
    - "console.error() only — never console.log() — enforced in all seed/DB/embed code"
    - "STUB_EMBEDDINGS=1 escape hatch — returns zero-vector without calling OpenAI; for CI/quota-zero envs"

key-files:
  created:
    - "src/db.ts — lazy MongoClient singleton; exports getDb() and closeDb()"
    - "src/embed.ts — OpenAI embedding client; exports embedText(), EMBEDDING_MODEL, EMBEDDING_DIMENSIONS; STUB_EMBEDDINGS=1 support"
    - "scripts/seed-mongodb.ts — idempotent seed script with --dry-run support"
  modified:
    - "package.json — added seed and seed:dry-run npm scripts"

key-decisions:
  - "OpenAI text-embedding-3-small (1536 dims) confirmed as embedding model — locks Atlas vector index dimensions; cannot change without collection drop and reindex"
  - "relationships section excluded from MongoDB seed — private sensitivity, not needed for Phase 1 MCP tools; 4 sections: persona, skills, projects, values"
  - "sectionToText() serializes section data as JSON.stringify with section name prefix for semantic embedding quality"
  - "STUB_EMBEDDINGS=1 returns zero-vector (1536 zeros) — lets seed run without OpenAI quota; zero-vectors are semantically inert but structurally correct; real embeddings must be regenerated before Plan 01-04 vector search is useful"

patterns-established:
  - "Pattern: Lazy singleton with module-level null variable — both getDb() and getOpenAI() follow same init-on-first-call pattern"
  - "Pattern: Upsert filter {doc_type, section} — all future seed/sync scripts should use same discriminator"
  - "Pattern: _sensitivity extracted to top-level, stripped from content before storage"
  - "Pattern: STUB_EMBEDDINGS=1 escape hatch — bypass external API for dev/CI without code changes"

requirements-completed:
  - MCP-06

# Metrics
duration: ~2h (Tasks 1-2: ~8min automated; Task 3: manual Atlas provisioning by user)
completed: 2026-03-26
---

# Phase 1 Plan 02: MongoDB Data Layer Summary

**Lazy MongoDB singleton (MCP-06) + OpenAI text-embedding-3-small utility + idempotent seed script — Atlas M0 live at breakfast-club.7bofp2n.mongodb.net with 4 identity documents and identity_vector_index created**

## Performance

- **Duration:** ~2h total (Tasks 1-2: ~8 min automated; Task 3: manual Atlas provisioning + seeding)
- **Started:** 2026-03-25T23:54:24Z
- **Completed:** 2026-03-26
- **Tasks:** 3 of 3 complete
- **Files modified:** 4 (plus Atlas infrastructure provisioned)

## Accomplishments

- MongoDB lazy singleton in `src/db.ts` — single connection cached for process lifetime, compatible with MCP-06 requirement
- OpenAI embedding utility in `src/embed.ts` — uses text-embedding-3-small (1536 dims) matching Atlas vector index; STUB_EMBEDDINGS=1 escape hatch for zero-quota envs
- Seed script with `--dry-run` validated showing all 4 sections (persona, skills, projects, values) with correct sensitivity levels
- MongoDB Atlas M0 cluster provisioned at `breakfast-club.7bofp2n.mongodb.net`; 4 identity documents seeded into `identity` collection
- `identity_vector_index` vector search index created in Atlas UI (cosine similarity, 1536 dims, doc_type + sensitivity filters)

## Task Commits

Each task committed atomically:

1. **Task 1: MongoDB lazy singleton and OpenAI embedding utility** - `4a3533d` (feat)
2. **Task 2: Seed script to load identity sections into MongoDB** - `76285dc` (feat)
3. **Task 3: Atlas provisioning (human-action checkpoint)** - Completed externally; stub embeddings patch `f951ae4` (chore)

**Plan metadata (pre-checkpoint pause commit):** `e4a8cc2` (docs: complete MongoDB data layer plan)

## Files Created/Modified

- `src/db.ts` - Lazy MongoClient singleton; `getDb()` and `closeDb()` exports; console.error only
- `src/embed.ts` - OpenAI embeddings client; `embedText()`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` exports; STUB_EMBEDDINGS=1 support
- `scripts/seed-mongodb.ts` - Reads nick-identity.json, embeds 4 sections, upserts into MongoDB identity collection; supports `--dry-run`
- `package.json` - Added `seed` and `seed:dry-run` npm scripts

## Decisions Made

- **text-embedding-3-small (1536 dims)** is the embedding model — locks Atlas vector index `numDimensions`. Cannot change without dropping the collection and recreating the index.
- **relationships section excluded from seed** — `_sensitivity: private`, not needed by Phase 1 MCP tools. The 4 sections seeded: persona, skills, projects, values.
- **STUB_EMBEDDINGS=1 escape hatch** — zero-quota environment needed to seed without burning OpenAI credits. `embedText()` returns `Array(1536).fill(0)` when set. Zero-vectors are semantically inert — real embeddings must be regenerated (remove flag, re-run `npm run seed`) before Plan 01-04 vector search produces useful results.
- **Text representation for embedding**: `"Section: {name}\n{JSON.stringify(content)}"` — preserves structure while being semantically meaningful.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added STUB_EMBEDDINGS=1 escape hatch to embed.ts**
- **Found during:** Task 3 (Atlas provisioning) — seed script needed to run with zero OpenAI quota in the `.env`
- **Issue:** With `STUB_EMBEDDINGS=1` set, the seed script would fail calling the OpenAI API; no way to test the seeding pipeline without quota
- **Fix:** Added conditional in `embedText()` — when `STUB_EMBEDDINGS=1`, returns `Array(EMBEDDING_DIMENSIONS).fill(0)` immediately without calling OpenAI
- **Files modified:** `src/embed.ts`
- **Verification:** Seed script ran successfully; 4 documents inserted into Atlas with zero-vector embeddings
- **Committed in:** `f951ae4` (chore: stub embeddings for zero-quota env)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Essential for running seed pipeline without OpenAI quota. Zero-vectors are acknowledged as semantically inert — acceptable for Phase 1 dev; real embeddings required before Plan 01-04 vector search goes live.

## Issues Encountered

- M0 free tier does not support programmatic vector index creation — index must be created via Atlas UI (as noted in plan). Index created manually with exact JSON definition from plan.
- `STUB_EMBEDDINGS=1` was set in `.env` during seeding — 4 documents now contain zero-vectors. Real embeddings must be regenerated before `identity_query` (Plan 01-04) is used.

## Known Stubs

- **4 identity documents in Atlas have zero-vector embeddings** (`src/embed.ts` STUB_EMBEDDINGS path, committed `f951ae4`). Vector search will return semantically arbitrary results until real embeddings are generated. **Resolution:** Remove `STUB_EMBEDDINGS=1` from `.env` and re-run `npm run seed` with valid `OPENAI_API_KEY`. Required before Plan 01-04 `identity_query` tool is tested.

## User Setup Required

Task 3 was a human-action checkpoint completed manually:

- MongoDB Atlas M0 cluster live at `breakfast-club.7bofp2n.mongodb.net`
- `.env` contains `MONGODB_URI`, `OPENAI_API_KEY`, `STUB_EMBEDDINGS=1`
- 4 identity documents seeded into `identity` collection (zero-vector embeddings)
- `identity_vector_index` created with cosine similarity, 1536 dims, doc_type + sensitivity filters

## Next Phase Readiness

- `src/db.ts` and `src/embed.ts` ready for import by MCP server (Plan 01-03)
- Atlas cluster and vector index live — Plan 01-03 can build identity_query, identity_context, projects_list tools
- **Action before Plan 01-04 end-to-end testing:** Remove `STUB_EMBEDDINGS=1` from `.env` and re-run `npm run seed` to generate real embeddings

---
*Phase: 01-foundation*
*Completed: 2026-03-26*
