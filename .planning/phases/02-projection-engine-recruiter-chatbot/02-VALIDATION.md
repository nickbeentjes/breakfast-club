---
phase: 2
slug: projection-engine-recruiter-chatbot
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Node.js 22 built-in `node:test` + `tsx --test` for TypeScript |
| **Config file** | None — no external framework needed |
| **Quick run command** | `tsx --test src/projection/apply-projection.test.ts` |
| **Full suite command** | `tsx --test 'src/**/*.test.ts' 'chatbot-worker/src/**/*.test.ts'` |
| **Estimated runtime** | ~8 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task's `<automated>` verify command
- **After every plan wave:** Run `npm run build` + quick test suite
- **Before `/gsd:verify-work`:** Full suite must pass + manual browser smoke test
- **Max feedback latency:** 8 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 02-01 | 1 | PROJ-01 | unit | `tsx --test src/projection/apply-projection.test.ts` | ❌ W0 | ⬜ pending |
| 2-01-02 | 02-01 | 1 | PROJ-02, PROJ-04 | unit | `tsx --test src/projection/load-projections.test.ts` | ❌ W0 | ⬜ pending |
| 2-01-03 | 02-01 | 1 | PROJ-03 | unit+build | `npm run build && tsx --test src/projection/apply-projection.test.ts` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02-02 | 2 | PROJ-05 | unit | `tsx --test chatbot-worker/src/middleware/auth.test.ts` | ❌ W0 | ⬜ pending |
| 2-02-02 | 02-02 | 2 | PROJ-05 | build | `cd chatbot-worker && npm run build` | ❌ W0 | ⬜ pending |
| 2-03-01 | 02-03 | 2 | RCTR-01 | unit | `tsx --test chatbot-worker/src/lib/audit.test.ts` | ❌ W0 | ⬜ pending |
| 2-03-02 | 02-03 | 2 | RCTR-05 | build | `cd chatbot-worker && npm run build` | ❌ W0 | ⬜ pending |
| 2-04-01 | 02-04 | 3 | RCTR-04 | static | `test -f chatbot-worker/public/index.html` | ❌ W0 | ⬜ pending |
| 2-04-02 | 02-04 | 3 | RCTR-04 | build | `cd chatbot-worker && npm run build` | ❌ W0 | ⬜ pending |
| 2-05-01 | 02-05 | 4 | RCTR-02, RCTR-03 | build | `npm run build` | ✅ exists | ⬜ pending |
| 2-05-02 | 02-05 | 4 | all | integration | `npm run health-check` (breakfast-club-status tool) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/projection/apply-projection.test.ts` — stubs for PROJ-01, PROJ-03
- [ ] `src/projection/load-projections.test.ts` — stubs for PROJ-02, PROJ-04
- [ ] `chatbot-worker/src/middleware/auth.test.ts` — stub for PROJ-05
- [ ] `chatbot-worker/src/lib/audit.test.ts` — stub for RCTR-05 with mock Octokit
- [ ] `chatbot-worker/package.json` + Wrangler config — Cloudflare Worker scaffold (Plan 02-02 creates these)

Wave 0 test files are created by Plan 02-01 Task 1 (projection engine scaffold includes test stubs).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Recruiter chatbot URL works in browser | RCTR-04 | Requires browser + deployed Worker | Open shareable URL, ask "what are your strongest skills?" — expect streaming text response |
| Chatbot refuses salary queries | RCTR-02 | Requires live LLM + deployed Worker | Ask "what salary do you expect?" — expect refusal response |
| Natural language returns grounded answers | RCTR-03 | Requires live MongoDB + LLM | Ask "tell me about your React experience" — expect answer grounded in identity data |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 8s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
