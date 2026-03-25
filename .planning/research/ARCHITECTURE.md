# Architecture Patterns: Breakfast Club Verification System

**Domain:** Self-sovereign AI identity — repo-as-database + verification triangle + static dashboard
**Researched:** 2026-03-26
**Overall Confidence:** HIGH (GitHub limits and MCP lifecycle from official docs; MongoDB from official docs + community; hash scheme from cryptographic first principles verified against SLSA/supply-chain literature)

---

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│  Private GitHub Repo (source of truth)                  │
│  agents/{agent-id}/profile.json                         │
│  agents/{agent-id}/attestations/{ts}.json               │
└─────────────────┬───────────────────────────────────────┘
                  │  GitHub Action (on push)
                  ▼
┌─────────────────────────────────────────────────────────┐
│  MongoDB Atlas (hot cache + query layer)                │
│  Collection: agents   { source_hash, synced_at, ... }   │
└─────────────────┬───────────────────────────────────────┘
                  │  GitHub Action (after successful sync)
                  ▼
┌─────────────────────────────────────────────────────────┐
│  Public GitHub Repo (attestation ledger)                │
│  attestations/{agent-id}/{date}.json  ← hash committed  │
└─────────────────┬───────────────────────────────────────┘
                  │  GitHub Pages (static hosting)
                  ▼
┌─────────────────────────────────────────────────────────┐
│  Verification Dashboard (index.html + pre-generated JSON)│
│  Fetches: /data/state.json, /data/chain.json            │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Repo-as-Database: Storage Model and Limits

### Recommended File Layout

Use one JSON file per entity, organised in subdirectories. Never put more than ~2,000 files in a single directory — GitHub hard-limits directory width at 3,000 entries and the web UI truncates display at 1,000. Use date-bucketed or ID-prefixed subdirectories when agent count grows.

```
agents/
  {agent-id}/
    profile.json          # current identity record
    attestations/
      2026-03-26T00.json  # one file per sync event
      2026-03-27T00.json
      ...
```

This keeps each directory well under limits even with daily attestations for thousands of agents.

### Hard Limits (enforced by GitHub)

| Limit | Value | Notes |
|-------|-------|-------|
| Max single file size | 100 MB | JSON profiles will be kilobytes — irrelevant |
| Directory width | 3,000 entries | Hard stop on entries per directory |
| Push size | 2 GB | Irrelevant for JSON |
| Directory depth | 50 levels | Irrelevant for this layout |
| Repo on-disk size (soft) | 10 GB | Flagged; not hard-rejected |

### API Rate Limits (critical for the sync Action)

| Token type | Requests/hour |
|------------|---------------|
| `GITHUB_TOKEN` (standard) | 1,000 |
| `GITHUB_TOKEN` (Enterprise Cloud) | 15,000 |
| PAT (any user) | 5,000 |
| GitHub App installation token | 5,000–12,500 (scales with org size) |

**Implication:** The sync Action that reads from the private repo and writes to the public repo must use a GitHub App token (not `GITHUB_TOKEN`), both for cross-repo access and for the higher rate ceiling. At 5,000 req/hr a sync touching 100 agents per run stays well within budget even with chunked reads. If you ever process thousands of agents in a single workflow run, batch reads using the Git Trees API (`GET /repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1`) — one call returns the entire file tree, avoiding per-file API calls.

### Atomic Updates and Conflict Avoidance

Git itself is the locking mechanism. Every push is atomic at the commit level. Race conditions between concurrent workflows writing to the same repo are real but manageable:

**Pattern: serialise writes through a single workflow trigger.** The private repo's push event triggers one sync workflow at a time (GitHub queues concurrent runs if `concurrency:` group is set). For the public attestation commit, use the GitHub API's `createOrUpdateFileContents` endpoint which requires the current file SHA — this is optimistic locking at the file level. If two workflows race to write the same attestation file, the second will get a 409 Conflict and can retry with the updated SHA.

```yaml
# Prevents concurrent sync runs from racing
concurrency:
  group: sync-pipeline
  cancel-in-progress: false   # queue, do not cancel; every sync matters
```

### Pagination Strategy for Large Repos

Avoid listing directory contents with `GET /repos/.../contents/{path}` when the directory has many files — it paginates at 100 entries per page and each page costs an API call. Instead:

1. Use `GET /repos/.../git/trees/{sha}?recursive=1` to fetch the full tree in one call (returns up to 100,000 entries before truncation).
2. Cache the tree SHA between runs and use `GET /repos/.../commits` to detect if any file changed before re-fetching.
3. For very large repos (>100,000 nodes), use a manifest index file (`agents/index.json`) that the sync Action maintains, listing all agent IDs and their last-modified commit SHAs.

---

## 2. Verification Triangle: Hash Scheme

### The Problem with Commit SHA Alone

A git commit SHA is deterministic but includes metadata: author name, email, timestamp, and parent commit SHA. Two commits with identical file contents but different timestamps produce different commit SHAs. This means:

- Commit SHA is NOT a pure content hash — it cannot be used to verify "the data in MongoDB matches the data in the repo" independently of when the commit was made.
- Tree SHA IS a pure content hash — it hashes only directory structure, filenames, and file content recursively, with no metadata.

**Recommendation: use the git tree SHA as `source_hash`, not the commit SHA.**

`git rev-parse HEAD^{tree}` returns the root tree SHA — identical across any two repos with identical content regardless of commit history.

### What to Hash and Why

For the Breakfast Club use case, the verification claim is: "The data MongoDB has for agent X matches what was committed to the private repo." The correct hash is:

```
source_hash = SHA-256(canonical_json(profile_record))
```

Computed independently of git, stored in MongoDB, and attested in the public repo. This is portable: anyone can re-derive it from the raw JSON without git tooling.

The git tree SHA serves a complementary role — it proves the file existed in the repo at the commit where the sync was triggered. Include both:

| Field | Value | Purpose |
|-------|-------|---------|
| `source_hash` | SHA-256 of canonical JSON | Content integrity, MongoDB-to-source verification |
| `git_tree_sha` | Root tree SHA at sync time | Proves repo state at sync moment |
| `git_commit_sha` | HEAD commit SHA at sync time | Human-readable audit trail, links to GitHub UI |
| `synced_at` | ISO 8601 UTC | Temporal ordering |
| `prev_attestation_hash` | SHA-256 of previous attestation record | Hash chain linkage |

### Canonical JSON

Canonicalisation is mandatory for deterministic hashing. Use RFC 8785 (JCS — JSON Canonicalization Scheme): keys sorted alphabetically, no insignificant whitespace, Unicode normalised. In Node.js use the `canonicalize` npm package or implement it directly (sort object keys recursively, `JSON.stringify` with no spacing).

### Hash Chain Structure

Each attestation in the public repo is a JSON record:

```json
{
  "agent_id": "agent-abc",
  "seq": 42,
  "source_hash": "sha256:a3f...",
  "git_tree_sha": "deadbeef...",
  "git_commit_sha": "cafebabe...",
  "synced_at": "2026-03-26T12:00:00Z",
  "prev_attestation_hash": "sha256:9d1...",
  "self_hash": "sha256:7e2..."
}
```

`self_hash` is SHA-256 of the canonical JSON of this record with `self_hash` set to an empty string — the standard bootstrap approach for self-referential records.

Any tampering with any field cascades: changing `source_hash` breaks `self_hash`, which breaks the next record's `prev_attestation_hash`, which breaks every subsequent entry. This is O(n) verification — one SHA-256 per record.

### Tamper Detection Algorithm

```
verify(chain):
  for i in range(len(chain)):
    record = chain[i]

    # 1. Verify self_hash
    candidate = record with self_hash = ""
    computed = sha256(canonical_json(candidate))
    assert computed == record.self_hash

    # 2. Verify chain linkage
    if i > 0:
      assert record.prev_attestation_hash == chain[i-1].self_hash
    else:
      assert record.prev_attestation_hash == "GENESIS"
```

The dashboard runs this algorithm client-side in vanilla JS on page load. No server needed.

### MongoDB Storage

MongoDB stores the current verified state:

```javascript
{
  _id: "agent-abc",
  profile: { /* full profile record */ },
  source_hash: "sha256:a3f...",           // matches what public repo attests
  git_commit_sha: "cafebabe...",
  synced_at: ISODate("2026-03-26T12:00:00Z"),
  latest_attestation_hash: "sha256:7e2...", // tip of hash chain
  verification_state: "verified" | "pending" | "mismatch"
}
```

`verification_state: "mismatch"` is set if the sync Action computes `source_hash` of the incoming data and it does not match what was last attested in the public repo — indicating someone modified MongoDB directly.

---

## 3. GitHub Actions Cross-Repo Workflow

### Authentication: GitHub App (not PAT)

Use a GitHub App, not a PAT. PATs are user-scoped, expire inconsistently, have no audit trail per-workflow, and give no fine-grained repository access control. A GitHub App is machine-to-machine, short-lived tokens (8 hour expiry, minted per-run), and can be installed on exactly two repos: the private source and the public attestation repo.

**Setup (one-time):**

1. Create a GitHub App in the org/account settings. Give it no homepage URL (internal use).
2. Grant repository permissions: `Contents: Read` on the private repo, `Contents: Read & Write` on the public repo.
3. Install the app on both repos.
4. Store `APP_ID` as a repo variable and `APP_PRIVATE_KEY` (PEM) as a repo secret in the private repo.

**Workflow pattern:**

```yaml
name: Sync and Attest

on:
  push:
    paths:
      - 'agents/**'

concurrency:
  group: sync-pipeline
  cancel-in-progress: false

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Mint app token (scoped to both repos)
        id: app-token
        uses: actions/create-github-app-token@v2
        with:
          app-id: ${{ vars.APP_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
          repositories: breakfast-club-private,breakfast-club-public

      - name: Checkout private repo
        uses: actions/checkout@v4
        with:
          token: ${{ steps.app-token.outputs.token }}

      - name: Sync to MongoDB Atlas
        env:
          MONGODB_URI: ${{ secrets.MONGODB_URI }}
        run: node scripts/sync.js

      - name: Commit attestation to public repo
        uses: actions/checkout@v4
        with:
          repository: your-org/breakfast-club-public
          token: ${{ steps.app-token.outputs.token }}
          path: public-repo

      - name: Write and push attestation
        run: |
          cd public-repo
          node ../scripts/attest.js
          git config user.name "Breakfast Club Bot"
          git config user.email "bot@noreply"
          git add attestations/
          git add data/state.json data/chain.json  # pre-generate dashboard data
          git commit -m "attest: sync $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          git push
```

### Secrets Management

| Secret/Variable | Where stored | Value |
|-----------------|-------------|-------|
| `APP_ID` | Private repo variable (not secret) | Integer app ID |
| `APP_PRIVATE_KEY` | Private repo secret | Full PEM including headers |
| `MONGODB_URI` | Private repo secret | Atlas connection string with credentials |

Never store `MONGODB_URI` in the public repo. The public repo's workflow (GitHub Pages deployment) should need no secrets — it only reads committed files.

### Trigger Chain

```
Push to private repo
  → sync workflow triggers
  → sync.js reads changed agents, writes to MongoDB
  → attest.js computes hashes, writes to public repo
  → public repo push triggers GitHub Pages deployment
  → dashboard is live in ~30 seconds
```

If the MongoDB write fails, the attestation commit should NOT happen — the workflow must exit non-zero before the attestation step. Atomicity between MongoDB and the public repo commit is not achievable (no distributed transaction), so the order matters: write MongoDB first, then attest. If attestation fails after MongoDB write, the next sync run will re-attest the same content (idempotent by design since source_hash is derived from content).

---

## 4. Static Dashboard

### Data Format Strategy

The sync Action pre-generates two JSON files into the public repo's `data/` directory. The dashboard HTML fetches them with `fetch()` — no API calls, no build step, just static files served by GitHub Pages.

**`/data/state.json`** — current verification state for all agents:

```json
{
  "generated_at": "2026-03-26T12:00:00Z",
  "agents": [
    {
      "agent_id": "agent-abc",
      "display_name": "Claude Opus",
      "verification_state": "verified",
      "latest_source_hash": "sha256:a3f...",
      "latest_attestation_hash": "sha256:7e2...",
      "last_synced": "2026-03-26T12:00:00Z",
      "attestation_count": 42
    }
  ]
}
```

**`/data/chain/{agent-id}.json`** — full hash chain for one agent (fetched on demand when user clicks an agent):

```json
{
  "agent_id": "agent-abc",
  "chain": [
    {
      "seq": 1,
      "synced_at": "2026-03-01T00:00:00Z",
      "source_hash": "sha256:...",
      "self_hash": "sha256:...",
      "prev_attestation_hash": "GENESIS",
      "git_commit_sha": "..."
    }
  ]
}
```

**Do not** put the full chain in `state.json` — it grows without bound. Lazy-load per-agent chains.

### Dashboard Implementation Pattern

One `index.html`, no framework, no build step:

```html
<!DOCTYPE html>
<html>
<head>
  <title>Breakfast Club Verification</title>
  <meta charset="utf-8">
</head>
<body>
  <div id="summary"></div>
  <div id="agent-detail" hidden></div>
  <script>
    const BASE = '';  // same origin — GitHub Pages serves data/ alongside index.html

    async function main() {
      const state = await fetch(`${BASE}/data/state.json`).then(r => r.json());
      renderSummary(state);
    }

    async function showAgent(agentId) {
      const chain = await fetch(`${BASE}/data/chain/${agentId}.json`).then(r => r.json());
      const valid = verifyChain(chain.chain);
      renderDetail(chain, valid);
    }

    function verifyChain(entries) {
      // runs entirely client-side — no server trust required
      for (let i = 0; i < entries.length; i++) {
        const entry = entries[i];
        // compute self_hash via SubtleCrypto (WebCrypto API, no dependencies)
        // compare prev_attestation_hash to entries[i-1].self_hash
      }
      return true;
    }

    main();
  </script>
</body>
</html>
```

Use the WebCrypto `SubtleCrypto.digest('SHA-256', ...)` API for client-side hash verification — it is available in all modern browsers with no dependencies.

### GitHub Pages Configuration

- Source: the public attestation repo, `main` branch, root `/`
- Custom domain: optional, but `your-org.github.io/breakfast-club-public` works out of the box
- CORS: GitHub Pages serves files with permissive CORS headers — `fetch()` from the same origin works without configuration
- Deployment lag: Pages typically deploys within 60 seconds of a push to main

### Timeline Display

The chain data includes `synced_at` timestamps in ISO 8601. Render as a vertical timeline sorted descending. Show hash prefix (first 8 chars of `self_hash`) as the visual identifier for each entry — long enough to be unique in any reasonable chain, short enough to display inline.

---

## 5. MCP Server Process Model

### Lifecycle: One Process, Many Tool Calls

When Claude Desktop or Claude Code spawns a stdio MCP server, it starts a subprocess and keeps it alive for the duration of the client session. The MCP spec (2025-03-26) defines three phases: Initialize → Operate → Shutdown. Shutdown occurs when the client closes stdin or sends SIGTERM.

**Critical implication:** the server process is NOT restarted between tool calls. A MongoDB connection established during the first tool call is reused for every subsequent call in the same session. This is identical to the serverless connection-caching pattern — declare the client outside the request handler.

### Cold Start Handling

The cold start problem: the first tool call after the server spawns must connect to MongoDB Atlas before it can respond. Atlas connection establishment takes 100–500ms on a warm network path.

**Recommended pattern:**

```typescript
import { MongoClient } from 'mongodb';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';

// Module-level: created once per process, reused across all tool calls
let mongoClient: MongoClient | null = null;

async function getDb() {
  if (!mongoClient) {
    mongoClient = new MongoClient(process.env.MONGODB_URI!, {
      maxPoolSize: 5,        // MCP server is single-threaded JS; 5 is generous
      minPoolSize: 1,        // keep one connection alive between tool calls
      maxIdleTimeMS: 300000, // close idle connections after 5 minutes
      serverSelectionTimeoutMS: 10000,  // fail fast if Atlas unreachable
      connectTimeoutMS: 10000,
    });
    await mongoClient.connect();
  }
  return mongoClient.db('breakfast-club');
}

// Initialize MCP server
const server = new Server({ name: 'breakfast-club', version: '1.0.0' }, {
  capabilities: { tools: {} }
});

server.setRequestHandler(/* tool handlers call getDb() */);

// Start transport
const transport = new StdioServerTransport();
await server.connect(transport);
// Process stays alive here — event loop keeps running
```

### Connection Pool Sizing

MCP stdio servers handle one tool call at a time (JSON-RPC is sequential over stdio; no concurrent requests from a single client session). A `maxPoolSize` of 5 is more than sufficient and avoids exhausting Atlas's connection limits if multiple Claude instances run simultaneously.

Do NOT set `minPoolSize: 0` (the default) — with zero minimum, the pool closes all connections when idle, forcing a reconnect on the next tool call. Set `minPoolSize: 1` to keep one warm connection.

### Reconnect on Atlas Disconnect

Atlas M0 (free tier) and M2/M5 shared clusters disconnect idle connections after ~30 minutes. Dedicated clusters (M10+) have a configurable limit. The MongoDB Node.js driver handles reconnect automatically with the default `retryReads: true` / `retryWrites: true` settings — no manual reconnect logic needed. The `minPoolSize: 1` setting will proactively re-establish the connection before it would be terminated.

### Startup Diagnostics

Log to stderr only (stdout is the MCP message stream — anything non-JSON-RPC written there corrupts the session):

```typescript
process.stderr.write(`[breakfast-club-mcp] starting, connecting to Atlas...\n`);
```

Use the MCP SDK's built-in logging capability for structured logs visible in the client's debug output. Never write to stdout outside of the SDK's transport layer.

### Process Termination

The server process exits when:
1. Claude Desktop closes (stdin closes → SIGTERM → SIGKILL if unresponsive)
2. The server calls `process.exit()` on an unrecoverable error

On SIGTERM, call `mongoClient.close()` to cleanly drain the connection pool:

```typescript
process.on('SIGTERM', async () => {
  if (mongoClient) await mongoClient.close();
  process.exit(0);
});
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| Private repo | Source of truth for agent identity JSON | GitHub Action reads on push |
| Sync Action | Read changed files, write to MongoDB, compute hashes | Private repo, MongoDB Atlas |
| Attest Action | Append hash chain entry, pre-generate dashboard data | Public repo (write) |
| MongoDB Atlas | Hot cache with query capability | MCP server (read/write), sync Action (write) |
| Public repo | Attestation ledger (append-only in practice) | GitHub Pages (static host) |
| Dashboard | Client-side chain verification, display | Reads `/data/*.json` from same origin |
| MCP server | Tool interface for Claude Desktop/Code | MongoDB Atlas (read/write), optionally GitHub API |

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Using Commit SHA as Content Hash
**What goes wrong:** Two commits with identical file contents but different timestamps have different commit SHAs. You cannot verify "MongoDB data matches repo data" by comparing commit SHAs.
**Instead:** Hash the canonical JSON directly. Commit SHA is useful for audit trail, not content verification.

### Anti-Pattern 2: Writing to Stdout in MCP Server
**What goes wrong:** Any non-JSON-RPC bytes on stdout corrupts the MCP message stream. `console.log()` is fatal.
**Instead:** All logging goes to stderr. Use `process.stderr.write()` or the MCP SDK logging utilities.

### Anti-Pattern 3: Connecting to MongoDB on Every Tool Call
**What goes wrong:** 100–500ms Atlas connection overhead per call. Tool calls feel sluggish.
**Instead:** Declare MongoClient at module scope, connect lazily on first call, reuse for the session lifetime.

### Anti-Pattern 4: Using GITHUB_TOKEN for Cross-Repo Operations
**What goes wrong:** `GITHUB_TOKEN` is scoped to the current repository only. Cross-repo operations fail with 403.
**Instead:** Use a GitHub App installation token scoped to both repositories.

### Anti-Pattern 5: Storing Full Chain in state.json
**What goes wrong:** `state.json` grows linearly with attestation history. Fetching it on every page load becomes slow.
**Instead:** `state.json` holds only current state. Full chain is in per-agent files fetched on demand.

### Anti-Pattern 6: More Than 2,000 Files Per Directory
**What goes wrong:** GitHub hard-limits directory entries at 3,000; web UI truncates at 1,000. Git Trees API calls become slow. Tooling breaks.
**Instead:** Date-bucket or ID-prefix subdirectories: `attestations/2026/03/` rather than `attestations/`.

---

## Scalability Notes

| Concern | At 100 agents | At 10K agents | At 1M agents |
|---------|--------------|--------------|-------------|
| Private repo size | ~1 MB | ~100 MB | Requires LFS or external store |
| Git Trees API | Single call, fast | Single call, may truncate (100K nodes) | Must use manifest index |
| MongoDB | Trivial | Single collection, indexed by agent_id | Sharding on agent_id |
| state.json | <10 KB | ~1 MB, still fine | Split by shard/prefix |
| Chain files | <1 KB each | Same | Same |
| Sync Action duration | <30s | 2–5 minutes | Requires batching + parallelism |

The repo-as-database pattern is practical up to roughly 10,000 agents with daily attestations. Beyond that, the Git Trees API approaches its 100,000-node truncation limit and sync times grow. At that scale, switch to an S3-compatible store as source of truth with git used only for commit-SHAs-as-audit-trail.

---

## Sources

- [GitHub Repository Limits — Official Docs](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits)
- [GitHub REST API Rate Limits — Official Docs](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- [GitHub Apps for Cross-Repo Auth — Official Docs](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow)
- [actions/create-github-app-token — GitHub Marketplace](https://github.com/marketplace/actions/create-github-app-token)
- [MCP Lifecycle Specification 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle)
- [MCP Stdio Transport Internals](https://medium.com/@laurentkubaski/understanding-mcp-stdio-transport-protocol-ae3d5daf64db)
- [MongoDB MCP Server — Official](https://www.mongodb.com/docs/mcp-server/get-started/)
- [Building a Tamper-Evident Audit Log with SHA-256 Hash Chains](https://dev.to/veritaschain/building-a-tamper-evident-audit-log-with-sha-256-hash-chains-zero-dependencies-h0b)
- [Beyond Encryption: Designing a Tamper-Evident State Engine](https://dev.to/laphilosophia/beyond-encryption-designing-a-tamper-evident-state-engine-1c19)
- [Git Object Model — SHA and Tree Hashes](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects)
- [SLSA Provenance and Git Tree SHA](https://github.com/slsa-framework/slsa/issues/214)
- [GitHub Flat Data Pattern](https://githubnext.com/projects/flat-data/)
- [MongoDB Atlas — Manage Connections from AWS Lambda](https://docs.atlas.mongodb.com/best-practices-connecting-from-aws-lambda/)
- [Replacing PAT with GitHub App](https://aembit.io/blog/replacing-a-github-personal-access-token-with-a-github-application/)
- [GitHub Apps: PAT vs GitHub App Community Discussion](https://github.com/orgs/community/discussions/109668)
