---
phase: 01-foundation
plan: 01
subsystem: database
tags: [typescript, json-schema, ajv, mongodb, mcp, esm, eslint]

requires: []

provides:
  - ESM TypeScript project scaffold with strict mode and Node16 module resolution
  - JSON Schema (draft 2020-12) for identity documents with four sensitivity tiers
  - TypeScript interfaces mirroring MongoDB document shape (IdentityDocument, SensitivityLevel, IdentitySection)
  - Founder seed data (nick-identity.json) with sensitivity labels, validated against schema
  - AJV-based validation script (scripts/validate-seed.ts)
  - ESLint config banning console.log (only console.error allowed)

affects:
  - 01-02 (MCP server build depends on types.ts and schema)
  - 01-03 (MongoDB seed ingestion uses IdentityDocument shape and schema)
  - All future plans that import from src/types.ts

tech-stack:
  added:
    - "@modelcontextprotocol/sdk ^1.28.0"
    - "zod ^4.3.6"
    - "mongodb ^7.1.1"
    - "openai ^6.33.0"
    - "ajv ^8.18.0 (ajv/dist/2020 for draft 2020-12)"
    - "typescript (devDep)"
    - "tsx (devDep)"
    - "eslint (devDep)"
    - "@types/node (devDep)"
  patterns:
    - "ESM-only: import/export, package.json type=module, tsconfig module=Node16"
    - "console.error() only — console.log banned by ESLint no-console rule"
    - "Sensitivity labels on every identity section (_sensitivity field in JSON)"
    - "AJV draft 2020-12 via ajv/dist/2020.js import path"

key-files:
  created:
    - src/schema/identity.schema.json
    - src/types.ts
    - seed-data/nick-identity.json
    - scripts/validate-seed.ts
    - package.json
    - tsconfig.json
    - .eslintrc.json
    - .env.example
    - .gitignore
  modified: []

key-decisions:
  - "Used ajv/dist/2020.js import for JSON Schema draft 2020-12 support — base Ajv class only handles draft-07"
  - "additionalProperties: true on all schema sections to allow future fields without breaking validation"
  - "relationships section included in schema and seed data with _sensitivity: private (most sensitive)"
  - "SensitivityLevel and IdentitySection exported as types (not interfaces) for union type usage"

patterns-established:
  - "Sensitivity pattern: every identity section has _sensitivity field with public/professional/personal/private enum"
  - "MongoDB document pattern: doc_type + section + sensitivity + embedding + content + updated_at"
  - "Validation pattern: AJV compile + validate + exit code pattern for seed data scripts"

requirements-completed: [IDNT-01, IDNT-02, IDNT-03, IDNT-04, IDNT-05, IDNT-06]

duration: 18min
completed: 2026-03-26
---

# Phase 01 Plan 01: Project Scaffold and Identity Schema Summary

**ESM TypeScript scaffold with strict-mode compilation, JSON Schema draft 2020-12 identity document spec covering four sections (persona, skills, projects, values) with sensitivity labels, and validated founder seed data**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-03-26T00:28:09Z
- **Completed:** 2026-03-26T00:46:00Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- ESM TypeScript project compiles with strict mode and Node16 module resolution; all production and dev dependencies installed
- JSON Schema (draft 2020-12) covers all four required identity sections — persona, skills, projects, values — each with a `_sensitivity` enum field for Phase 2 projection enforcement
- TypeScript types export `IdentityDocument` matching the MongoDB document shape from RESEARCH.md (doc_type, section, sensitivity, embedding, content, updated_at)
- Founder seed data (nick-identity.json) validated against schema via AJV — exits 0, zero errors
- ESLint configured to ban `console.log` (only `console.error` allowed) per MCP stdout contamination prevention rule

## Task Commits

Each task was committed atomically:

1. **Task 1: ESM TypeScript project scaffold with ESLint console.log ban** - `009a06f` (chore)
2. **Task 2: Identity JSON Schema, TypeScript types, and seed data validation** - `092079b` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `package.json` - ESM project config with all dependencies, build/lint/validate-seed scripts
- `tsconfig.json` - TypeScript strict mode, Node16 module resolution, ES2022 target
- `.gitignore` - Excludes node_modules, build, .env
- `.env.example` - Documents MONGODB_URI, MONGODB_DB_NAME, OPENAI_API_KEY
- `.eslintrc.json` - Bans console.log, allows console.error
- `src/schema/identity.schema.json` - JSON Schema draft 2020-12 for identity documents with sensitivity tiers
- `src/types.ts` - IdentityDocument, IdentitySchema, SensitivityLevel, IdentitySection, section sub-interfaces
- `seed-data/nick-identity.json` - Founder identity data with _sensitivity on all 5 sections
- `scripts/validate-seed.ts` - AJV validation script, exits 0 on success / 1 with errors

## Decisions Made

- **AJV draft 2020-12 import:** Used `ajv/dist/2020.js` not `ajv` directly — the base Ajv class only handles JSON Schema draft-07; draft 2020-12 requires the explicit import path. (Rule 1 auto-fix during Task 2 verification)
- **additionalProperties: true on sections:** Allows future fields to be added to identity documents without schema breakage during early iterations
- **relationships section included:** The seed data has a `relationships` section with `_sensitivity: "private"` — most sensitive data. Schema accommodates it with optional additionalProperties
- **Types vs interfaces for unions:** `SensitivityLevel` and `IdentitySection` exported as `type` (union type) rather than `interface` — correct TypeScript pattern for string unions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] AJV draft 2020-12 import path**
- **Found during:** Task 2 (validate-seed.ts verification run)
- **Issue:** `import Ajv from "ajv"` throws "no schema with key or ref https://json-schema.org/draft/2020-12/schema" at runtime — base Ajv class only handles draft-07
- **Fix:** Changed import to `import Ajv from "ajv/dist/2020.js"` — AJV ships a separate entrypoint for draft 2020-12 support
- **Files modified:** scripts/validate-seed.ts
- **Verification:** `npx tsx scripts/validate-seed.ts` exits 0, prints "VALID"
- **Committed in:** `092079b` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — wrong AJV import path for draft 2020-12)
**Impact on plan:** Essential fix. Schema used draft 2020-12 `$schema` URI; AJV requires explicit import for that draft version. No scope creep.

## Issues Encountered

None beyond the AJV import fix documented above.

## User Setup Required

None — no external service configuration required at this plan stage. MongoDB Atlas provisioning is Plan 01-02.

## Next Phase Readiness

- TypeScript project compiles clean — ready for MCP server implementation (Plan 01-02)
- Schema and types are the dependency root — Plans 01-02 and 01-03 can proceed
- `IdentityDocument` interface is ready for MongoDB collection insertion in Plan 01-03
- Seed data is validated and ready for MongoDB ingestion
- No blockers for Phase 01 continuation

---
*Phase: 01-foundation*
*Completed: 2026-03-26*
