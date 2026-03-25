# Project Research Summary

**Project:** Breakfast Club — self-sovereign AI identity system
**Domain:** MCP server / personal identity infrastructure / GitHub-native data architecture
**Researched:** 2026-03-26
**Confidence:** HIGH (stack, architecture, risks from official docs), MEDIUM (identity schema standards, recruiter UX patterns)

---

## Executive Summary

Breakfast Club is a self-sovereign AI identity system: a private GitHub repo holds canonical identity JSON, a GitHub Actions pipeline syncs it to MongoDB Atlas, and an MCP server exposes it to Claude and other AI clients. The core insight is that "repo-as-database" is the right architecture for a system where self-ownership and auditability matter more than query performance — git provides versioning, attestation, and tamper-evidence for free, while MongoDB provides the semantic search layer that flat files cannot. The stack is deliberately minimal: Node.js + TypeScript, `@modelcontextprotocol/sdk` 1.x (stdio transport), `@octokit/rest`, `mongodb` driver, and vanilla HTML for the dashboard. No framework, no bundler, nothing that adds a build step to GitHub Pages.

The projection system is the product's defining architectural decision. Everything downstream — the recruiter chatbot, the SKILL.md injector, the OAuth scope mapping — flows from a whitelist-based field filter enforced server-side in MCP tool handlers. Get this design right before writing the first tool, because changing it later means auditing every data access path. The recommended approach is named projection files (JSON) stored in the private repo, with field allowlists using dotpath notation, mapped to MCP OAuth 2.1 scopes. The owner projection gets `allow_fields: ["*"]`; the recruiter projection gets an explicit allowlist of professional fields only.

The critical risks split into two categories: infrastructure constraints (MongoDB M0's single vector index limit is the binding constraint — design the schema around it from day one) and demo-day operational risks (the James MacDonald recruiter demo has HIGH-priority failure modes around MCP server startup and Claude Desktop auto-updates). The setup experience for the open-source template is the highest-impact adoption risk: if it takes more than 30 minutes, most users abandon before they see value. A `scripts/setup.sh` that validates connectivity before proceeding is non-negotiable.

---

## Cross-Cutting Findings

These insights emerged across multiple research files and represent the most synthesized conclusions:

**1. The single vector index limit on MongoDB M0 shapes everything.**
STACK.md, FEATURES.md, and RISKS.md all converge here. There is exactly one vector search index available on the free tier. This means identity embeddings and conversation memory embeddings must share a single index on a unified `embedding` field, with a `doc_type` or `chunk_type` discriminator used as a pre-filter on `$vectorSearch`. This must be a day-one schema decision — retrofitting it is painful.

**2. Stdout contamination is a silent killer of MCP servers.**
STACK.md and ARCHITECTURE.md both flag this independently. Any `console.log()` in a stdio MCP server writes to the JSON-RPC channel and silently corrupts the protocol. This extends to any npm dependency that prints startup messages to stdout. The fix (`console.error()` for all logging) is simple but must be enforced from the first line of code — habits form early.

**3. The projection system is the trust anchor, not crypto.**
FEATURES.md recommends whitelist-based projection enforced server-side. RISKS.md confirms this is the correct security model for MVP, with an explicit note that BBS+ cryptographic selective disclosure is an architectural future-proofing step — not needed for single-user MVP. The projection enforcement belongs in one place: the `applyProjection()` function called inside every MCP tool handler, including the owner's tools (for audit consistency).

**4. GitHub App token is better than PAT for the sync pipeline, but PAT is acceptable for MVP.**
ARCHITECTURE.md recommends GitHub App for cross-repo authentication (better audit trail, scoped access, short-lived tokens). RISKS.md acknowledges that GitHub App setup is developer-hostile for non-platform engineers and recommends PAT for the initial MVP template to reduce adoption friction. The decision: build the sync pipeline with PAT first, document the GitHub App upgrade path.

**5. The demo is a product decision, not just a technical one.**
RISKS.md identifies six demo-day risks for the James MacDonald recruiter demo. The highest-impact one (Risk 5.6) is that the demo scope is too ambitious. Three interactions maximum: background question, leadership question, email refusal. Pre-scripting the demo narrative is as important as pre-building the TypeScript.

---

## Key Findings

### Recommended Stack

The stack is ESM-only TypeScript running on Node 18+ LTS. The MCP SDK (`@modelcontextprotocol/sdk` 1.27.1 — do NOT use v2, it's pre-alpha) uses stdio transport for local deployment. `@octokit/rest` (not the heavier `octokit` meta-package) handles GitHub API access. The native `mongodb` driver (v6.x) connects to Atlas. The dashboard is vanilla HTML/JS with no build step.

**Core technologies:**
- `@modelcontextprotocol/sdk@1.27.1`: MCP server runtime — stable v1.x, exact version pin (no `^`), ESM-only
- `@octokit/rest`: GitHub API — REST-only, lighter than full octokit, fine-grained PAT with `Contents: Read`
- `mongodb@^6.x`: Atlas driver — v6 required for `$vectorSearch` support
- `zod@3.25+`: MCP tool schema validation — 3.25+ for v4 shim compatibility with SDK internals
- `tsx` (dev): TypeScript execution without build step — for development only; pre-build to JS before demo
- Vanilla HTML/JS: GitHub Pages dashboard — zero build step, Pages serves files directly

**Critical config:**
- `"type": "module"` in `package.json` — SDK is ESM-only, missing this produces cryptic failures
- `tsconfig.json`: `"module": "Node16"`, `"moduleResolution": "Node16"`, `"strict": true`
- MongoDB: `maxPoolSize: 5`, `minPoolSize: 1` — prevents connection exhaustion, keeps warm connection
- GitHub Actions: `concurrency: group: sync-pipeline, cancel-in-progress: false` — serializes writes

### Expected Features

**Must have (table stakes):**
- Owner identity access via MCP (stdio, owner projection) — the primary use case
- SKILL.md generator from identity JSON — system prompt injection, immediate personal value
- GitHub repo as source of truth — self-sovereignty is the product promise
- Projection system with field-level sensitivity controls — privacy is the whole point
- Recruiter projection + shareable link — the demonstrable external value case
- Conversation memory storage in MongoDB — cross-session continuity

**Should have (differentiators):**
- Projection-aware SKILL.md auto-generation (no manual format maintenance)
- Git-backed identity versioning (history for free)
- Cross-AI memory normalization (Claude + ChatGPT + Gemini exports unified)
- Transparency attestation dashboard (hash chain verification, public GitHub Pages)
- `breakfast-club-status` health-check MCP tool — critical for demo confidence

**Defer to v2+:**
- BBS+ cryptographic selective disclosure (VC-based proofs) — architecture future-proofing
- Rate limiting on recruiter projection (needed before public launch, not for personal MVP)
- Multi-user / shared identity scenarios — scope creep
- LinkedIn data ingestion — legal risk, stale data
- AI-editable identity — trust violation

**Anti-features (never build):**
- AI editing identity files — ownership violation
- Automatic PII detection/redaction — false security, use field taxonomy instead
- Public API with no auth — even "public" projections require signed tokens
- Ingesting third-party data (LinkedIn scrape) — legal risk

### Architecture Approach

The system is a verification triangle: private GitHub repo (source of truth) → MongoDB Atlas (hot cache + query layer) → public GitHub repo (attestation ledger) → GitHub Pages (verification dashboard). The MCP server sits alongside MongoDB as a read/write interface for AI clients. The sync pipeline (GitHub Actions) connects the repo to MongoDB and publishes attestations to the public repo. Everything flows through the sync trigger — push to private repo → sync → attest → dashboard live in ~90 seconds.

**Major components:**
1. **Private repo** — canonical identity JSON and projection definitions; source of trust
2. **Sync Action** — reads changed agent files, writes to MongoDB, computes SHA-256 hashes, triggers attestation
3. **MongoDB Atlas** — hot cache with `$vectorSearch` for memory retrieval; `verification_state` field tracks sync integrity
4. **Attest Action** — appends hash chain entries to public repo, pre-generates `data/state.json` and per-agent `data/chain/{id}.json`
5. **MCP server** — tool interface to MongoDB; enforces projections at handler boundary; stdio transport, module-scoped connection pool
6. **GitHub Pages dashboard** — vanilla JS reads pre-generated JSON; runs WebCrypto chain verification client-side; no server needed

**Hash scheme:** Use SHA-256 of canonical JSON (RFC 8785 / JCS) as `source_hash`, NOT git commit SHA. Commit SHA includes metadata (author, timestamp) and cannot verify "MongoDB data matches repo data" independently. Include `git_tree_sha` (pure content hash of directory state) and `git_commit_sha` (human audit trail) as supplementary fields. Hash chain links via `prev_attestation_hash` on each attestation record.

**Data pre-generation pattern:** The sync Action generates `data/state.json` (current state, all agents) and `data/chain/{agent-id}.json` (full chain, per-agent, lazy-loaded) into the public repo. Never put full chain data in `state.json` — it grows without bound.

### Critical Pitfalls (Top 5)

1. **`console.log()` in stdio MCP server corrupts JSON-RPC silently** — Use `console.error()` or `process.stderr.write()` for all logging. Audit every dependency for stdout writes. This is the #1 "works but mysteriously broken" failure mode.

2. **Single vector index on M0 is a hard limit — plan before creating** — Design one unified `embedding` field across all document types (identity chunks, memory chunks). Use `$vectorSearch` pre-filters with a `doc_type` discriminator. Creating a second vector index silently fails on M0.

3. **`repos.getContent` TypeScript types are wrong — always narrow before accessing `.content`** — Check `!Array.isArray(response.data)` first. Content is base64 with embedded newlines; use `Buffer.from(content, "base64")`, not `atob()`. Files >1 MB cannot be retrieved via Contents API — use Git Data API for large files.

4. **GITHUB_TOKEN cannot write to a different repo** — Cross-repo writes require a fine-grained PAT (or GitHub App token) stored as a secret. PAT pushes DO trigger target repo workflows (GITHUB_TOKEN pushes do not) — use `[skip ci]` in bot commit messages.

5. **MongoDB atlas M0 requires `mongodb+srv://` connection string, not `mongodb://`** — The driver resolves SRV DNS records to find replica set members. Firewalls blocking SRV lookups cause intermittent failures with no meaningful error. GitHub Actions runners use dynamic IPs, requiring `0.0.0.0/0` in Atlas IP access list for sync workflows.

---

## Critical Decisions Before Building

These must be resolved in order — each blocks downstream work:

**Decision 1: Identity schema + field sensitivity taxonomy** (blocks everything)
The schema structure and the `_sensitivity` sidecar map define what the projection engine filters. Build this first, commit it to the repo, and don't change the field names once MCP tools reference them. Recommended: use the schema from FEATURES.md as the starting point with the four sensitivity tiers: `public`, `professional`, `personal`, `private`.

**Decision 2: Single unified `embedding` field design** (blocks MongoDB setup)
Decide whether identity documents and memory chunks live in the same collection (with `doc_type` discriminator) or separate collections sharing the one allowed vector index. Recommended: separate collections, both indexed with the same field name `embedding`, sharing the single vector index with `doc_type` as pre-filter. Create this index via Atlas UI during initial setup — include in setup script.

**Decision 3: PAT vs GitHub App for sync pipeline** (blocks GitHub Actions)
PAT is lower friction for MVP (one secret, one step). GitHub App is better for production (auditable, scoped, short-lived). Recommended: start with PAT for the first working sync pipeline, document upgrade path. Do NOT design the pipeline to be PAT-only — use an abstraction layer (environment variable for token) so swapping auth mechanisms requires only a secret change.

**Decision 4: Projection enforcement mechanism** (blocks MCP tool implementation)
Named projection JSON files in private repo with explicit `allow_fields` allowlists. Projections map to MCP OAuth 2.1 scopes. If no auth scope is present, default to the most restrictive projection (`public`). Never default to `owner`. The `applyProjection()` function is called inside every tool handler — even for owner access (audit consistency).

**Decision 5: Demo scope and narrative** (blocks demo-day prep)
Three interactions maximum for the James MacDonald demo. The demo must be pre-scripted, the TypeScript pre-compiled (not JIT via `tsx`), and the `breakfast-club-status` health-check tool must be the first thing called to confirm the stack is live. All five demo-day risks (5.1–5.5) require mitigation steps taken the night before, not the morning of.

---

## Implications for Roadmap

### Phase 1: Foundation (Identity Schema + Owner MCP)
**Rationale:** The identity schema is the dependency root. Nothing else — projections, SKILL.md, memory — can be built without a committed, stable schema. The owner MCP tools (get_identity, update_identity) are the fastest path to personal value and the validation loop for the schema design.
**Delivers:** Working MCP server on stdio; owner can ask Claude "who am I" and get a structured answer; SKILL.md auto-generated from identity JSON
**Addresses:** Owner identity access, SKILL.md injection (must-have table stakes)
**Avoids:** ESM config mistakes, stdout contamination — get these right at project init
**Research flags:** Standard patterns — MCP SDK stdio setup is well-documented

### Phase 2: Projection Engine + Recruiter Chatbot
**Rationale:** The projection system is the product's core differentiator. Build it immediately after the owner tools so the architecture is validated before the sync pipeline is built on top of it. The recruiter chatbot is the concrete test of the projection system and the demo anchor.
**Delivers:** Named projections enforced server-side; recruiter projection JSON; shareable URL (GitHub Pages static chatbot); `query_professional_profile` tool
**Addresses:** Recruiter projection, field-level sensitivity controls, projection-aware SKILL.md
**Avoids:** Projection bypass bugs — unit test `applyProjection()` before demo; verify recruiter output manually
**Research flags:** OAuth 2.1 scope mapping in MCP may need phase-specific research — client support varies

### Phase 3: GitHub Actions Sync Pipeline + Attestation
**Rationale:** The sync pipeline connects the repo (source of truth) to MongoDB and the public attestation repo. This must come after the identity schema and projection engine are stable — the schema shape determines what the sync script reads and indexes.
**Delivers:** Automated sync on push to `agents/**`; SHA-256 hash computation and storage; attestation JSON written to public repo; `data/state.json` and `data/chain/{id}.json` pre-generated for dashboard
**Addresses:** GitHub-backed identity versioning, transparency attestation
**Avoids:** Infinite loop from PAT pushes (`[skip ci]`); GITHUB_TOKEN cross-repo limitation; Actions minute exhaustion (cache `node_modules`, use `paths:` filter)
**Research flags:** Standard patterns — GitHub Actions workflow patterns are well-documented

### Phase 4: Conversation Memory
**Rationale:** Memory is the most complex data domain. It shares the single vector index with identity, so the index design from Phase 1 must be validated before adding memory chunks. Defer until the core identity and projection flows are proven.
**Delivers:** Memory chunk ingestion from Claude export JSON; semantic chunking (512-token baseline, semantic boundaries); hybrid retrieval (vector similarity + recency weighting); cross-session memory accessible via MCP tool
**Addresses:** Conversation memory storage (table stake), cross-AI memory unification (differentiator)
**Avoids:** Vector index limit — memory chunks must use the same `embedding` field and `$vectorSearch` pre-filter pattern established in Phase 1
**Research flags:** Multi-source normalization (ChatGPT/Gemini export formats) may need phase research; entity extraction pipeline design

### Phase 5: Verification Dashboard + Hardening
**Rationale:** The public GitHub Pages dashboard is dependent on the attestation data produced by Phase 3. Build it last as a trust demonstration layer, not a prerequisite for any other component.
**Delivers:** Vanilla HTML/JS dashboard; client-side WebCrypto chain verification; verification state display; per-agent attestation timeline; `npm run verify` health-check command for setup validation
**Addresses:** Transparency attestation dashboard, demo-day hardening
**Avoids:** Full chain in `state.json` (grows without bound — use lazy-loaded per-agent files); over-ambitious demo scope
**Research flags:** Standard patterns — GitHub Pages + vanilla JS is fully documented

### Phase Ordering Rationale

- Phase 1 must come first: identity schema is the dependency root for all downstream components
- Phase 2 before Phase 3: projection engine shape determines what MongoDB stores and what sync indexes; validate it before automating
- Phase 3 before Phase 4: memory indexing shares the vector index — the index design must be confirmed working for identity before adding memory
- Phase 5 last: attestation dashboard consumes data produced by Phase 3; hardening work wraps everything

### Research Flags

Needs deeper research during planning:
- **Phase 2:** MCP OAuth 2.1 scope enforcement varies by client (Claude Desktop vs Cursor vs Windsurf); projection fallback mechanism may need client-specific handling
- **Phase 4:** ChatGPT and Gemini export format normalization; LLM-based entity/topic extraction pipeline cost and latency

Standard patterns (skip research-phase):
- **Phase 1:** MCP SDK stdio setup, MongoDB Atlas connection pooling — official docs are comprehensive
- **Phase 3:** GitHub Actions cross-repo workflows, `[skip ci]` pattern — well-documented
- **Phase 5:** GitHub Pages + vanilla JS + WebCrypto — fully documented, zero framework complexity

---

## The 5 Most Important Gotchas

Things that would burn the team without this research:

1. **`console.log()` silently destroys the MCP server.** Any stdout write in a stdio server corrupts JSON-RPC. The symptom is an MCP server that starts but tools never respond. Affects `console.log()`, MongoDB driver startup messages, and any npm package that writes to stdout. Enforce `console.error()` from the first commit.

2. **MongoDB M0 has exactly one vector search index. Plan before creating.** If you create a vector index for identity and then try to create one for memory, the second one fails. You cannot fix this without dropping indexes. Design the unified `embedding` field schema and create the single index during setup, before ingesting any data.

3. **The Octokit `repos.getContent` TypeScript types are wrong.** The return type is `file | directory | symlink | submodule` but TypeScript doesn't discriminate it correctly. You must check `!Array.isArray(response.data)` and `response.data.type === 'file'` before accessing `.content`. Content is also base64 with embedded newlines — `atob()` fails on this; `Buffer.from(content, "base64")` works.

4. **The MongoDB connection must be established once at module scope, not per tool call.** Atlas connection takes 100–500ms. A server that connects inside each tool handler will feel broken — every tool call has a half-second cold start. Declare `MongoClient` at module scope, connect lazily on first call, set `minPoolSize: 1` to keep a warm connection between tool calls.

5. **The demo WILL fail if you don't pre-build TypeScript and pre-test the exact config path.** Claude Desktop's `claude_desktop_config.json` must reference the compiled JS file path exactly. `tsx` JIT compilation can fail mid-demo. Claude Desktop auto-updates can silently break MCP server registration. Pre-build with `tsc`, test the `breakfast-club-status` tool the night before, disable auto-updates before demo day.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | MCP SDK, Octokit, MongoDB driver — all from official docs and changelogs |
| Features | MEDIUM | Identity schema has no authoritative standard (W3C VC covers credentials, not AI personalization); schema design is synthesized from JSON Resume, PAI, and first principles |
| Architecture | HIGH | GitHub limits from official docs; MCP lifecycle from spec; hash scheme from cryptographic first principles verified against SLSA literature |
| Risks | HIGH (infra), MEDIUM (adoption) | Infrastructure limits from official docs; adoption/UX risks from adjacent tool failure patterns |

**Overall confidence:** HIGH for infrastructure decisions; MEDIUM for identity schema field design and recruiter UX patterns.

### Gaps to Address

- **Identity schema evolution:** No versioning strategy is defined. When the schema changes (new fields, renamed fields), how do existing MongoDB documents get migrated? Consider `schema_version` field from day one and plan for a migration script step in the sync pipeline.

- **Projection token lifecycle:** The recruiter shareable URL includes a token that grants `identity:read:professional` scope. The token format (plain string vs signed JWT), TTL, and revocation mechanism are not specified. For MVP a simple shared secret with a configurable expiry is acceptable — but this must be decided before the projection engine is built.

- **Embedding model choice:** The sync pipeline needs to generate embeddings for memory chunks. The research recommends text-embedding-3-small (OpenAI) but does not evaluate alternatives (Cohere, Gemini embedding, local models). If OpenAI is the choice, the `OPENAI_API_KEY` is a required secret in the sync Action — this adds setup friction and cost. Validate the choice before Phase 4.

- **Memory ingestion trigger:** The research describes a GitHub Actions sync triggered by pushes to `agents/**`. Conversation memory export files (Claude, ChatGPT, Gemini JSON exports) are user-uploaded blobs, not repo commits. The ingestion trigger for memory (manual CLI command vs a separate upload Action) is undefined. Decide before Phase 4 planning.

---

## Sources

### Primary (HIGH confidence)
- `@modelcontextprotocol/sdk` npm 1.27.1 — MCP server patterns, stdio transport, tool registration
- MCP Specification 2025-03-26 — transport lifecycle, OAuth 2.1 scopes
- MongoDB Atlas free cluster limits (official docs) — storage, connection, vector index constraints
- MongoDB Node.js driver docs v6 — `$vectorSearch`, connection pooling, `createSearchIndex`
- GitHub REST API docs — rate limits, `repos.getContent`, Git Trees API
- GitHub Actions docs — workflow triggers, concurrency, secrets, free tier minutes
- GitHub Apps docs — cross-repo authentication, installation tokens
- GitHub repository limits (official) — directory width, file size, repo size

### Secondary (MEDIUM confidence)
- JSON Resume schema — identity schema field structure
- Personal AI Infrastructure (PAI, Daniel Miessler) — markdown-based identity patterns
- W3C Verifiable Credentials v2.0 (May 2025) — sensitivity taxonomy, selective disclosure concepts
- Weaviate/Pinecone/NVIDIA chunking research — 512-token baseline, semantic boundary splitting
- MCP OAuth auth0 blog — scope mapping patterns
- AGENTS.md / AAIF (Linux Foundation) — cross-tool system prompt format compatibility

### Tertiary (LOW confidence / patterns only)
- Recruiter chatbot UX research (assesscandidates.com) — question categories and boundary patterns
- API security whitelisting effectiveness (Qodex.ai) — whitelist vs blacklist comparison
- tj-actions supply chain attack analysis (Wiz) — GitHub Actions security failure modes
- Truffle Security CFOR vulnerability — private repo data persistence risk

---

*Research completed: 2026-03-26*
*Ready for roadmap: yes*
