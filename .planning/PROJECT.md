# Breakfast Club

## What This Is

An open-source, self-sovereign AI identity system that lets people own their personality, memories, and knowledge across every AI provider — stored in infrastructure they control (private GitHub repo + MongoDB Atlas free tier), accessible via MCP server and REST API, with a public transparency log proving data integrity. The mission statement is six words: "Don't you forget about me."

## Core Value

Any AI, any provider, reads the same you — without you having to repeat yourself, and without any company owning the relationship you've built.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Private GitHub repo template with structured JSON/markdown schema (persona, skills, projects, preferences, values, conversation memory) that users fork as their "brain"
- [ ] Public GitHub repo template with append-only hash attestation log and GitHub Pages static dashboard showing verification state, timeline, and hash consistency
- [ ] GitHub Action that fires on push to private repo, syncs curated data to MongoDB Atlas, computes state hash, and commits attestation to public repo
- [ ] MCP server (Node.js/TypeScript) wrapping GitHub API (Octokit) + MongoDB queries with tools: identity_query, identity_context, projects_list, verify_integrity
- [ ] SKILL.md — AI-agnostic instruction file teaching any model how to use the identity store (the portability layer)
- [ ] Projection views — filtered identity slices for different audiences (personal/full, professional, custom/role-specific)
- [ ] Seed data — founder's identity (nick-identity.json) loaded as the first test case
- [ ] REST API endpoints alongside MCP tools for non-MCP clients (e.g. ChatGPT)
- [ ] Recruiter chatbot demo — professional projection queryable via chatbot interface
- [ ] Verification triangle working end-to-end: private repo SHA → MongoDB source_hash → public attestation

### Out of Scope

- Blockchain anchoring (Phase 2+) — pragmatic first, crypto comes after we have users
- Bittensor subnet (Phase 3) — requires 100+ TAO and economic design, not MVP
- ZK proofs and SD-JWT selective disclosure (Phase 4) — advanced privacy, later
- ChatGPT custom GPT integration — nice to have, not needed for James MacDonald demo
- UI for editing identity data — git + JSON IS the editing interface for MVP
- Any paid infrastructure — must run at $0/month on free tiers throughout Milestone 1
- Authentication system — GitHub access controls ARE the auth for MVP

## Context

### The Problem Being Solved

Every AI conversation starts from zero. Switching providers means starting over as a stranger. Worse, that relationship data lives on vendor servers — the user doesn't own it, can't move it, and loses it if terms change. Breakfast Club treats AI-built identity as the user's property, stored in infrastructure they control, with cryptographic proof of authenticity.

### Why These Choices

- **Git as storage**: already a Merkle tree — content-addressed, append-only, tamper-evident. Free. Every developer understands it.
- **MongoDB Atlas free tier**: 512MB shared cluster (enormous for structured personality data), vector search built-in, GitHub Action syncs on push, source commit hash stored with every document.
- **No custom server**: $0 cost, GitHub reliability/uptime, battle-tested security, portability.
- **Verification triangle**: Private repo SHA → MongoDB source_hash → Public repo attestation. Tampering any one leg breaks the chain.
- **SKILL.md as the portability layer**: any AI reads the same instruction file, making the system truly provider-agnostic.

### Competitive Gap

Existing projects (Mem0 OpenMemory, CaviraOSS OpenMemory, OpenBrain, Anthropic native memory) treat memory as DATA — embeddings and chunks. None model the PERSON. None provide structured identity, projection views, integrity verification, or third-party queryability.

### First Demo Target

James MacDonald, Managing Director at NewyTechPeople (Newcastle tech recruiter). Live demo: he queries the founder's professional projection via chatbot, sees the transparency dashboard, experiences the future of recruitment. Potential podcast appearance if it lands.

### Tech Stack

- **Runtime**: Node.js / TypeScript
- **Primary storage**: Private GitHub repo (structured JSON/markdown)
- **Hot cache**: MongoDB Atlas free tier with vector search
- **Transparency**: Public GitHub repo + GitHub Pages (static HTML/JS)
- **MCP server**: Node.js, Octokit + MongoDB driver
- **Embeddings**: OpenAI API or local (nomic-embed-text via Ollama)
- **CI/CD**: GitHub Actions (free tier: 2,000 min/month)

## Constraints

- **Budget**: $0/month — everything must run on free tiers. No paid infra in Milestone 1.
- **MCP compatibility**: Must work with Claude Code and Claude Desktop out of the box
- **Open source**: MIT license from day one. No proprietary dependencies.
- **No corporate jargon**: In docs, code comments, README, anywhere. Ever.
- **Demo deadline**: James MacDonald demo is the forcing function — working recruiter chatbot needed ASAP

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Git as primary storage (not a database) | Merkle tree properties give us tamper-evidence for free; portable; zero cost; universally understood | — Pending |
| MongoDB Atlas as hot cache (not primary store) | Free vector search; always consistent with git via Action; source hash stored for verification | — Pending |
| Public repo has zero private data | Trust requires transparency; recruiter must be able to inspect the source of truth | — Pending |
| SKILL.md as portability layer | Makes any AI usable with the identity without code changes | — Pending |
| GitHub Actions for sync (not a custom server) | $0 cost; GitHub reliability; no ops burden | — Pending |
| Projection whitelist model (not blacklist) | Safer default — you explicitly grant, never accidentally expose | — Pending |
| Static GitHub Pages dashboard (not a hosted app) | Zero cost; inspectable source; no auth complexity; anyone can verify | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-26 after initialization*
