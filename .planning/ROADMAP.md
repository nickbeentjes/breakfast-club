# Roadmap: Breakfast Club

## Overview

Breakfast Club delivers a self-sovereign AI identity system in five phases. Phase 1 lays the schema foundation and owner MCP tools — everything downstream depends on the identity schema being stable. Phase 2 builds the projection engine and recruiter chatbot, which is the demo-day deliverable. Phase 3 automates the sync pipeline and writes the attestation chain that feeds the public transparency log. Phase 4 adds conversation memory, which shares the single MongoDB vector index established in Phase 1 and requires the projection system from Phase 2 to be stable. Phase 5 builds the verification dashboard on top of Phase 3 attestation data and hardens the system for production demos. The mission throughout: "Don't you forget about me."

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Identity schema + owner MCP server + SKILL.md; the dependency root for everything else
- [ ] **Phase 2: Projection Engine + Recruiter Chatbot** - Whitelist projection system + scoped tokens + chatbot UI; the demo-day deliverable
- [ ] **Phase 3: Sync Pipeline + Attestation** - GitHub Action syncing identity to MongoDB + hash chain commits to public repo
- [ ] **Phase 4: Conversation Memory** - Memory chunking + vector retrieval + ingestion pipeline for Claude exports
- [ ] **Phase 5: Verification Dashboard + Hardening** - GitHub Pages dashboard + client-side chain verification + demo-day hardening

## Phase Details

### Phase 1: Foundation
**Goal**: Owner can query their identity via MCP, SKILL.md auto-injects context, and the schema is stable enough to build projections on
**Depends on**: Nothing (first phase)
**Requirements**: IDNT-01, IDNT-02, IDNT-03, IDNT-04, IDNT-05, IDNT-06, MCP-01, MCP-02, MCP-03, MCP-04, MCP-05, MCP-06, MCP-07, SKIL-01, SKIL-02, SKIL-03, SKIL-04
**Success Criteria** (what must be TRUE):
  1. Owner can ask Claude "who am I" via MCP and receive a synthesized persona/skills/projects response within 1200 tokens
  2. Claude can call `identity_query` with a natural-language question and get semantically relevant results from MongoDB Atlas vector search
  3. SKILL.md exists in the private repo root, stays under 600 tokens, and teaches any AI how to use the identity store without code changes
  4. The founder's identity (nick-identity.json) validates against the schema and is loaded as seed data
  5. All MCP server log output goes to stderr; no stdout contamination corrupts the JSON-RPC stream
**Plans**: 5 plans

Plans:
- [ ] 01-01-PLAN.md — Project scaffold + identity schema with sensitivity labels + seed data validation
- [ ] 01-02-PLAN.md — MongoDB lazy singleton + embedding utility + seed script + Atlas provisioning checkpoint
- [ ] 01-03-PLAN.md — MCP server core with stdio transport + identity_context and projects_list tools
- [ ] 01-04-PLAN.md — identity_query (vector search) + verify_integrity tools, complete tool registration
- [ ] 01-05-PLAN.md — SKILL.md with <identity> XML wrapper under 600-token budget + token counter

### Phase 2: Projection Engine + Recruiter Chatbot
**Goal**: Third parties can query a scoped professional projection via a shareable chatbot URL, with owner-controlled whitelist enforcement server-side
**Depends on**: Phase 1
**Requirements**: PROJ-01, PROJ-02, PROJ-03, PROJ-04, PROJ-05, RCTR-01, RCTR-02, RCTR-03, RCTR-04, RCTR-05
**Success Criteria** (what must be TRUE):
  1. A recruiter can open a shareable URL in a browser, ask natural-language questions about the owner's professional background, and receive grounded answers — with no technical setup required on their end
  2. The chatbot refuses to answer salary questions and personal data queries, staying within the role-fit and logistics scope defined in the system prompt
  3. The professional projection exposes only explicitly whitelisted fields — querying a field outside the allowlist returns nothing, never an accidental disclosure
  4. Every recruiter query is recorded in an append-only audit trail in the private repo
  5. Owner can define a custom projection by dropping a JSON file into `projections/` and it takes effect without code changes
**Plans**: TBD

Plans:
- [ ] 02-01: Projection engine — `applyProjection()` function, named projection JSON files, whitelist enforcement inside every MCP tool handler
- [ ] 02-02: Scoped projection tokens — token-to-projection binding, `public` default for unauthenticated requests, never default to `owner`
- [ ] 02-03: Recruiter chatbot backend — scoped token endpoint serving professional projection, constrained system prompt, audit trail writes to private repo
- [ ] 02-04: Recruiter chatbot UI — static HTML/JS shareable URL, no technical setup required for recipient
- [ ] 02-05: Demo prep — pre-scripted three-interaction narrative, pre-built TypeScript, `breakfast-club-status` health-check tool
**UI hint**: yes

### Phase 3: Sync Pipeline + Attestation
**Goal**: A push to the private repo automatically syncs identity to MongoDB and appends a hash chain entry to the public attestation repo within 90 seconds
**Depends on**: Phase 2
**Requirements**: SYNC-01, SYNC-02, SYNC-03, SYNC-04, SYNC-05, SYNC-06, SYNC-07, VERF-01
**Success Criteria** (what must be TRUE):
  1. Pushing a change to the private repo triggers the GitHub Action and MongoDB reflects the updated identity within 90 seconds
  2. Each MongoDB document carries a `source_hash` (SHA-256 of canonical JCS JSON) and `git_tree_sha` enabling independent verification that the cached data matches the repo
  3. The public attestation repo gains a new hash chain entry on each sync — each entry links to the previous via `prev_attestation_hash`, making the chain tamper-evident
  4. The sync workflow uses a GitHub App (or fine-grained PAT) for cross-repo writes and bot commits carry `[skip ci]` to prevent workflow loops
  5. All third-party Actions in the sync workflow are pinned to commit SHAs, not version tags
**Plans**: TBD

Plans:
- [ ] 03-01: GitHub App setup — cross-repo auth, Contents:Read on private + Contents:Read+Write on public repo
- [ ] 03-02: Sync Action — push trigger, Git Trees API batch read, canonical JCS hash computation, MongoDB upsert
- [ ] 03-03: Attestation Action — hash chain entry construction (`source_hash`, `tree_sha`, `timestamp`, `prev_attestation_hash`, `self_hash`), bot commit to public repo with `[skip ci]`
- [ ] 03-04: Pre-generation — `data/state.json` (current state summary) and `data/chain/{id}.json` (per-agent chain) written to public repo for dashboard consumption

### Phase 4: Conversation Memory
**Goal**: Conversation memory from Claude exports is ingested, chunked, embedded, and retrievable via vector search within the same MongoDB index as identity data
**Depends on**: Phase 3
**Requirements**: MEM-01, MEM-02, MEM-03, MEM-04, MEM-05, MEM-06
**Success Criteria** (what must be TRUE):
  1. A Claude conversation export (Markdown format) can be ingested via a CLI command and appears as searchable memory chunks in MongoDB
  2. Vector search across memory chunks respects the single-index M0 constraint — `chunk_type` pre-filter distinguishes memory chunks from identity documents without a second index
  3. Retrieval applies recency weighting so recent memories surface above stale ones for equivalent semantic similarity
  4. Each memory chunk records source AI (claude/chatgpt/gemini), conversation date, and conversation ID for provenance
**Plans**: TBD

Plans:
- [ ] 04-01: Memory schema — chunk types (turn, summary, semantic, entity), unified `embedding` field with `doc_type` discriminator, provenance fields
- [ ] 04-02: Chunking pipeline — 512-token baseline with semantic/recursive boundary detection, 10-15% overlap
- [ ] 04-03: Embedding + ingestion — embed chunks using chosen model, upsert to MongoDB using pre-established single vector index, CLI trigger for manual ingestion
- [ ] 04-04: Retrieval integration — `memory_search` MCP tool with recency weighting (30%), `$vectorSearch` pre-filter by `chunk_type`

### Phase 5: Verification Dashboard + Hardening
**Goal**: Anyone can visit the public GitHub Pages URL and verify the integrity of the owner's identity chain without trusting any server
**Depends on**: Phase 3
**Requirements**: VERF-02, VERF-03, VERF-04
**Success Criteria** (what must be TRUE):
  1. The GitHub Pages dashboard loads, runs WebCrypto chain verification client-side, and displays "verified" for an intact chain — all without any server request beyond fetching static files
  2. The dashboard shows the tamper/unknown state visually when a chain entry is modified, distinguishable at a glance
  3. The dashboard is vanilla HTML/JS with no build step — `git clone` + open in browser = working verification
  4. A `npm run verify` health-check command confirms the full stack is live before any demo
**Plans**: TBD

Plans:
- [ ] 05-01: Dashboard scaffold — vanilla HTML/JS, GitHub Pages config, load `data/state.json` and lazy-load `data/chain/{id}.json`
- [ ] 05-02: Client-side verification — WebCrypto SubtleCrypto chain walk, verified/tampered/unknown state display, attestation timeline
- [ ] 05-03: Demo hardening — `breakfast-club-status` tool end-to-end test, pre-build TypeScript, demo runbook with three pre-scripted interactions
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/5 | Not started | - |
| 2. Projection Engine + Recruiter Chatbot | 0/5 | Not started | - |
| 3. Sync Pipeline + Attestation | 0/4 | Not started | - |
| 4. Conversation Memory | 0/4 | Not started | - |
| 5. Verification Dashboard + Hardening | 0/3 | Not started | - |
