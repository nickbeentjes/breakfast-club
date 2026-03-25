---
phase: 1
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | jest 29.x (TypeScript via ts-jest) |
| **Config file** | jest.config.ts — Wave 0 installs |
| **Quick run command** | `npm test -- --testPathPattern=unit` |
| **Full suite command** | `npm test` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `npm test -- --testPathPattern=unit`
- **After every plan wave:** Run `npm test`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01-01 | 1 | IDNT-01 | unit | `npx ajv validate -s schema/identity.schema.json -d seed-data/nick-identity.json` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01-01 | 1 | IDNT-02 | unit | `npm test -- --testPathPattern=schema` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01-01 | 1 | IDNT-03 | unit | `npm test -- --testPathPattern=sensitivity` | ❌ W0 | ⬜ pending |
| 1-02-01 | 01-02 | 1 | IDNT-04 | integration | `npm run seed:dry-run` | ❌ W0 | ⬜ pending |
| 1-02-02 | 01-02 | 1 | IDNT-05 | integration | `npm run seed && npm run verify-index` | ❌ W0 | ⬜ pending |
| 1-03-01 | 01-03 | 2 | MCP-01 | unit | `npm test -- --testPathPattern=transport` | ❌ W0 | ⬜ pending |
| 1-03-02 | 01-03 | 2 | MCP-02 | unit | `npm test -- --testPathPattern=stderr` | ❌ W0 | ⬜ pending |
| 1-03-03 | 01-03 | 2 | MCP-03 | integration | `echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \| node dist/index.js` | ❌ W0 | ⬜ pending |
| 1-04-01 | 01-04 | 2 | MCP-04 | integration | `npm test -- --testPathPattern=identity_context` | ❌ W0 | ⬜ pending |
| 1-04-02 | 01-04 | 2 | MCP-05 | integration | `npm test -- --testPathPattern=identity_query` | ❌ W0 | ⬜ pending |
| 1-04-03 | 01-04 | 2 | MCP-06 | integration | `npm test -- --testPathPattern=projects_list` | ❌ W0 | ⬜ pending |
| 1-04-04 | 01-04 | 2 | MCP-07 | integration | `npm test -- --testPathPattern=verify_integrity` | ❌ W0 | ⬜ pending |
| 1-05-01 | 01-05 | 3 | SKIL-01 | manual | Token count check — see Manual Verifications | ❌ W0 | ⬜ pending |
| 1-05-02 | 01-05 | 3 | SKIL-02 | unit | `npm test -- --testPathPattern=skill-generator` | ❌ W0 | ⬜ pending |
| 1-05-03 | 01-05 | 3 | SKIL-03 | manual | AI comprehension test — see Manual Verifications | N/A | ⬜ pending |
| 1-05-04 | 01-05 | 3 | SKIL-04 | unit | `npm test -- --testPathPattern=idnt-06` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `jest.config.ts` — TypeScript Jest config with ts-jest transformer
- [ ] `src/__tests__/schema.test.ts` — JSON Schema validation tests (IDNT-01, IDNT-02, IDNT-03)
- [ ] `src/__tests__/transport.test.ts` — MCP stdio transport stubs (MCP-01, MCP-02, MCP-03)
- [ ] `src/__tests__/tools.test.ts` — Tool handler stubs (MCP-04 through MCP-07)
- [ ] `src/__tests__/skill-generator.test.ts` — SKILL.md generation stubs (SKIL-01, SKIL-02, SKIL-04)
- [ ] `scripts/seed.ts` — Seed dry-run capability (IDNT-04, IDNT-05)
- [ ] `npm install --save-dev jest ts-jest @types/jest` — test framework

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SKILL.md is under 600 tokens | SKIL-01 | Token counting requires external tool | Run `npx gpt-tokenizer count SKILL.md` or paste into claude.ai token counter; must report < 600 |
| Any AI can use MCP tools from SKILL.md alone | SKIL-03 | Requires AI comprehension judgement | Open fresh Claude session with no project context, paste SKILL.md, ask it to call `identity_context` — should produce valid JSON-RPC tool call |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
