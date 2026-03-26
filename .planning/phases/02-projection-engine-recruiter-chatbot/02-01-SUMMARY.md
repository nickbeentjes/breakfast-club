---
phase: 02-projection-engine-recruiter-chatbot
plan: 01
subsystem: api
tags: [projection, whitelist, zod, node-test, typescript, identity-filter]

requires:
  - phase: 01-foundation
    provides: IdentityDocument type, SensitivityLevel, IdentitySection types from src/types.ts

provides:
  - applyProjection() whitelist filter function — fail-closed, pure, no side effects
  - ProjectionDefinition interface and ProjectionName type
  - loadProjections() file loader with Zod validation
  - getProjection() helper for Map lookup
  - Three built-in projection JSON files (public, professional, personal)

affects:
  - 02-02 (MCP tool integration — wraps tools with applyProjection)
  - 02-03 (chatbot worker — calls loadProjections at startup, applyProjection before LLM)
  - all downstream plans that return identity data to third parties

tech-stack:
  added: []
  patterns:
    - "Fail-closed projection: applyProjection(docs, null) always returns [] — never full documents"
    - "Whitelist model: allowed_sections + allowed_sensitivity + optional field_allowlist"
    - "TDD with node:test built-in runner (no jest/vitest) — tsx --test for TypeScript"
    - "Zod schema validation on all external JSON files at load time"
    - "loadProjections() throws loudly on invalid JSON or schema — never silently skips"

key-files:
  created:
    - src/projection/types.ts
    - src/projection/apply-projection.ts
    - src/projection/apply-projection.test.ts
    - src/projection/load-projections.ts
    - src/projection/load-projections.test.ts
    - projections/public.json
    - projections/professional.json
    - projections/personal.json
  modified: []

key-decisions:
  - "applyProjection() returns [] when projection is null/undefined — fail closed, never fall back to full docs"
  - "Three sensitivity tiers in professional projection: persona(filtered)+skills+projects with public+professional sensitivity"
  - "public projection field_allowlist restricts persona to name only and skills to primary_stack only"
  - "loadProjections throws on any invalid file rather than skipping — startup failure preferred over silent data leak"

patterns-established:
  - "Projection whitelist pattern: section filter -> sensitivity filter -> optional content field filter"
  - "TDD with node:test + tsx --test: no external test framework dependencies"
  - "All external JSON files validated at load time with Zod, errors thrown immediately"

requirements-completed: [PROJ-01, PROJ-02, PROJ-04]

duration: 10min
completed: 2026-03-26
---

# Phase 02 Plan 01: Projection Engine Core Summary

**Whitelist projection engine: applyProjection() fail-closed filter + Zod-validated JSON projection files loaded via loadProjections()**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-26T09:49:15Z
- **Completed:** 2026-03-26T09:59:00Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 8

## Accomplishments

- applyProjection() pure whitelist filter: section -> sensitivity -> optional field allowlist, returns [] on null projection (fail-closed invariant enforced)
- loadProjections() reads projections/*.json, validates with Zod schema, returns Map keyed by name — throws on any malformed or invalid file
- Three built-in projection JSON files: public (persona+skills, public sensitivity, field-restricted), professional (persona+skills+projects, public+professional, persona fields filtered), personal (all sections, all tiers)
- 18 unit tests (9 per module) all passing with node:test + tsx

## Task Commits

Each task was committed atomically (TDD = test commit + feat commit):

1. **Task 1 RED: Failing tests for applyProjection()** - `4f59490` (test)
2. **Task 1 GREEN: ProjectionDefinition types + applyProjection()** - `e78f59d` (feat)
3. **Task 2 RED: Failing tests for loadProjections()** - `841971c` (test)
4. **Task 2 GREEN: Projection JSON files + loadProjections()** - `f549380` (feat)

**Plan metadata:** (docs commit — see below)

_TDD tasks have two commits each (test → feat)_

## Files Created/Modified

- `src/projection/types.ts` - ProjectionDefinition interface, ProjectionName type
- `src/projection/apply-projection.ts` - applyProjection() whitelist filter, filterContent() helper
- `src/projection/apply-projection.test.ts` - 9 unit tests covering all filter behaviors + fail-closed
- `src/projection/load-projections.ts` - loadProjections() with Zod validation, getProjection() helper
- `src/projection/load-projections.test.ts` - 9 unit tests covering Map size/keys, error cases, content validation
- `projections/public.json` - public projection (persona/skills, public sensitivity, field allowlist)
- `projections/professional.json` - professional projection (persona/skills/projects, public+professional)
- `projections/personal.json` - personal/owner projection (all sections, all sensitivity tiers)

## Decisions Made

- Fail-closed is the top invariant: `!projection` check is the first line of applyProjection() before any other logic
- public projection restricts to public sensitivity only (not public+professional), enforcing minimal exposure
- professional projection includes persona section but field_allowlist limits it to name/working_style/communication_style — no location, no contact info
- loadProjections() throws rather than skipping invalid files — startup failure is the right tradeoff (Pitfall 5 from RESEARCH.md)
- Used node:test built-in runner — no external test framework needed, consistent with project's zero-external-test-deps preference

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `src/projection/` module is fully functional and tested — ready for Plan 02-02 to wrap MCP tool handlers
- applyProjection() signature is stable: `(docs: IdentityDocument[], projection: ProjectionDefinition | null | undefined) => IdentityDocument[]`
- loadProjections() can be called at MCP server startup with the `projections/` directory path
- Any custom projection added to `projections/` as a JSON file will be loaded automatically without code changes

---
*Phase: 02-projection-engine-recruiter-chatbot*
*Completed: 2026-03-26*

## Self-Check: PASSED

All 8 source files found on disk. All 4 task commits verified in git history.
