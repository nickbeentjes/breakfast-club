---
phase: 1
slug: foundation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-26
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Integration tests (tsc + build + script verification) |
| **Config file** | None — per CLAUDE.md: "integration tests that prove the thing works, not unit tests for getters" |
| **Quick run command** | `npm run build` |
| **Full suite command** | `npm run build && npx tsx scripts/validate-seed.ts && npx tsx scripts/count-tokens.ts SKILL.md` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task's `<automated>` verify command
- **After every plan wave:** Run `npm run build` to confirm no regressions
- **Before `/gsd:verify-work`:** Full suite must be green (build + validate-seed + count-tokens)
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 1-01-01 | 01-01 | 1 | IDNT-01..06 | build | `npx tsc --noEmit --pretty` | pending |
| 1-01-02 | 01-01 | 1 | IDNT-01..06 | integration | `npx tsx scripts/validate-seed.ts` | pending |
| 1-02-01 | 01-02 | 2 | MCP-06 | build | `npx tsc --noEmit` | pending |
| 1-02-02 | 01-02 | 2 | MCP-06 | integration | `npx tsx scripts/seed-mongodb.ts --dry-run` | pending |
| 1-02-03 | 01-02 | 2 | MCP-06 | checkpoint | MongoDB Atlas provisioned, 4 docs seeded, vector index created | pending |
| 1-03-01 | 01-03 | 3 | MCP-01, MCP-07 | build | `npm run build` | pending |
| 1-03-02 | 01-03 | 3 | MCP-02, MCP-04 | build+grep | `npm run build && grep -l "identity_context\|projects_list" build/tools/*.js` | pending |
| 1-04-01 | 01-04 | 4 | MCP-03 | build | `npx tsc --noEmit` | pending |
| 1-04-02 | 01-04 | 4 | MCP-03, MCP-05 | build+grep | `npm run build && grep -c "registerIdentityQueryTool\|registerVerifyIntegrityTool\|registerIdentityContextTool\|registerProjectsListTool" src/index.ts` | pending |
| 1-05-01 | 01-05 | 4 | SKIL-01..04 | static | `wc -w SKILL.md` (under 450 words) | pending |
| 1-05-02 | 01-05 | 4 | SKIL-04 | integration | `npx tsx scripts/count-tokens.ts SKILL.md` (exits 0 = PASS) | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

No dedicated Wave 0 is needed. Test infrastructure is embedded in the plans themselves:

- Plan 01-01 Task 1 creates `tsconfig.json` and `package.json` (build infrastructure)
- Plan 01-01 Task 2 creates `scripts/validate-seed.ts` (schema validation)
- Plan 01-02 Task 2 creates `scripts/seed-mongodb.ts` with `--dry-run` (seed verification)
- Plan 01-05 Task 2 creates `scripts/count-tokens.ts` (token budget verification)

Each plan's verify commands use `tsc`, `npm run build`, or `npx tsx scripts/*.ts` — all created by the plans themselves. No separate test framework install is required.

This aligns with CLAUDE.md: "integration tests that prove the thing works, not unit tests for getters."

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MCP tools respond correctly with seeded data | MCP-02..05 | Requires live MongoDB + OpenAI connection | After Plan 01-02 checkpoint: `echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \| node build/index.js 2>/dev/null` — should list 4 tools |
| Any AI can use MCP tools from SKILL.md alone | SKIL-03 | Requires AI comprehension judgement | Open fresh Claude session with no project context, paste SKILL.md, ask it to call `identity_context` — should produce valid JSON-RPC tool call |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 not needed — verification scripts created within plans
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready
