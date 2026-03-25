# Technology Stack: Breakfast Club MCP Server

**Project:** Breakfast Club — self-sovereign AI identity system
**Researched:** 2026-03-26
**Overall confidence:** HIGH (MCP SDK, Octokit, GitHub Actions/Pages), MEDIUM (MongoDB Atlas free tier edge cases)

---

## Recommended Stack

### Core: MCP Server

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `@modelcontextprotocol/sdk` | 1.27.1 (v1.x stable) | MCP server runtime | Official SDK; v2 still pre-alpha as of Q1 2026 |
| `zod` | 3.25+ (v3, NOT v4) | Schema validation for tool inputs | Required peer dependency; SDK internally imports zod/v4 but v3.25+ is forward-compatible |
| Node.js | 18+ LTS | Runtime | SDK requires Node 16+; 18+ for native fetch support |
| TypeScript | 5.x | Language | Strictest type safety; SDK ships full types |

**Transport choice: stdio for local, Streamable HTTP for deployed.**

The MCP spec (2025-03-26) now defines exactly two supported transports:
- **stdio** — for local process-spawned servers (Claude Desktop, Cursor, etc.)
- **Streamable HTTP** — for remote/deployed servers

SSE is deprecated as a standalone transport. If this server runs locally (Claude Desktop spawns it as a child process), use stdio. If it needs to be reachable over the network (shared identity across devices/users), use Streamable HTTP.

For Breakfast Club, **start with stdio**. The server accesses a private GitHub repo and MongoDB with credentials that should not be exposed in a network-facing service without auth middleware.

### GitHub Integration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `octokit` | latest (^9.x) | All-in-one GitHub SDK | Includes REST, GraphQL, plugins; replaces `@octokit/rest` directly |
| — or — | — | — | — |
| `@octokit/rest` | latest (^21.x) | REST-only, lighter weight | Use this if you only need REST, not GraphQL or GitHub Apps |

For Breakfast Club: use `@octokit/rest` unless you add GitHub App auth later. Smaller footprint, fewer transitive deps.

### Database

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `mongodb` | ^6.x (6.14+ recommended) | MongoDB Atlas driver | Official driver; v6 required for Atlas Vector Search via Node.js |

### GitHub Actions Sync Pipeline

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `actions/checkout` | v4 | Checkout repos in workflow | Current stable |
| `actions/github-script` | v7 | Octokit in workflow context | Inline scripting with auto-auth |

### GitHub Pages Dashboard

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Vanilla HTML/JS/CSS | N/A | Static identity dashboard | Zero build step; Pages serves files directly |

No React, no Vite, no bundler. A plain `index.html` in the repo root (or `docs/` folder) deploys instantly on push. This is the correct choice for a dashboard that just reads public JSON from the same repo.

---

## Installation

```bash
# Core MCP server
npm install @modelcontextprotocol/sdk zod

# GitHub integration (choose one)
npm install @octokit/rest            # lighter, REST only
# npm install octokit                # heavier, all-in-one

# MongoDB Atlas
npm install mongodb

# Dev dependencies
npm install -D typescript @types/node tsx
```

**tsconfig.json settings that matter:**
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "strict": true,
    "esModuleInterop": true
  }
}
```

**package.json must have:**
```json
{
  "type": "module"
}
```

The SDK is ESM-only. `"type": "module"` is required or imports will fail silently with cryptic errors.

---

## Key API Patterns

### 1. MCP Server Setup (stdio transport)

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({
  name: "breakfast-club",
  version: "1.0.0",
});

// Register a tool
server.registerTool(
  "get_identity",
  {
    description: "Retrieve identity document for an agent",
    inputSchema: {
      agent_id: z.string().describe("The agent DID or slug"),
    },
  },
  async ({ agent_id }) => {
    // fetch from MongoDB / GitHub here
    return {
      content: [{ type: "text", text: JSON.stringify(identityDoc) }],
    };
  }
);

// Register a resource
server.resource(
  "identity://current",
  "Current user's identity document",
  async (uri) => ({
    contents: [{ uri: uri.href, text: JSON.stringify(currentIdentity) }],
  })
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Breakfast Club MCP server running on stdio"); // stderr only!
}

main().catch((err) => { console.error(err); process.exit(1); });
```

**CRITICAL GOTCHA:** Never use `console.log()` in a stdio MCP server. It writes to stdout, which is the JSON-RPC channel. This silently corrupts the protocol. Use `console.error()` for all logging. This applies to any library you use that writes to stdout (e.g., MongoDB driver connection messages).

### 2. Octokit — Reading Files from a Private Repo

```typescript
import { Octokit } from "@octokit/rest";

const octokit = new Octokit({
  auth: process.env.GITHUB_TOKEN, // Fine-grained PAT with repo read scope
});

async function readRepoFile(
  owner: string,
  repo: string,
  path: string,
  ref = "main"
): Promise<string> {
  const response = await octokit.rest.repos.getContent({
    owner,
    repo,
    path,
    ref,
  });

  // GOTCHA: TypeScript types are broken here — data can be a file OR directory
  // Must type-narrow before accessing .content
  if (Array.isArray(response.data)) {
    throw new Error(`Path ${path} is a directory, not a file`);
  }
  if (response.data.type !== "file" || !response.data.content) {
    throw new Error(`Unexpected response type: ${response.data.type}`);
  }

  // Content is always base64-encoded by the API
  return Buffer.from(response.data.content, "base64").toString("utf-8");
}
```

**GOTCHA: The TypeScript types for `repos.getContent` are wrong/incomplete.** The response `data` is typed as a union of file | directory | symlink | submodule. TypeScript will not let you access `.content` without narrowing. Always check `!Array.isArray(response.data)` first.

**GOTCHA: Content is base64-encoded with embedded newlines.** The API splits base64 across multiple lines with `\n`. `Buffer.from(content, "base64")` handles this correctly; `atob()` does not (it fails on embedded newlines).

**Rate limits:** 5,000 requests/hour with a PAT. For a repo-as-database pattern reading many files per request, this is ample but consider caching hot files in-process or in MongoDB to avoid hammering the API.

**Fine-grained PAT scopes needed:**
- `Contents: Read` on the private identity repo
- That's it — minimum scope principle

### 3. MongoDB Atlas — Connection and Vector Search

```typescript
import { MongoClient, ServerApiVersion } from "mongodb";

const client = new MongoClient(process.env.MONGODB_URI!, {
  serverApi: {
    version: ServerApiVersion.v1,
    strict: true,
    deprecationErrors: true,
  },
  // IMPORTANT for M0: Keep connection pool small
  maxPoolSize: 10,
  minPoolSize: 1,
});

// Connect once at startup, reuse the client
await client.connect();
const db = client.db("breakfast_club");
const identities = db.collection("identities");

// Vector search (requires index created in Atlas UI or via driver)
const results = await identities.aggregate([
  {
    $vectorSearch: {
      index: "identity_vector_index",
      path: "embedding",
      queryVector: queryEmbedding,        // float[] from your embedding model
      numCandidates: 100,
      limit: 10,
      filter: { agent_type: "human" },    // optional pre-filter
    },
  },
  {
    $project: {
      _id: 1,
      agent_id: 1,
      display_name: 1,
      score: { $meta: "vectorSearchScore" },
    },
  },
]).toArray();

// Document with source_hash pattern
await identities.insertOne({
  agent_id: "did:github:kees",
  display_name: "Kees",
  source_repo: "kees/breakfast-club-identity",
  source_path: "identity/kees.json",
  source_hash: sha256OfFileContent,      // SHA-256 hex string
  source_ref: "main",
  synced_at: new Date(),
  embedding: float32Array,               // from text-embedding-3-small etc.
  data: parsedJsonDocument,
});
```

**Connection string format (Atlas M0):**
```
mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/breakfast_club?retryWrites=true&w=majority
```

Must use `mongodb+srv://` (SRV format), not plain `mongodb://`. The driver resolves the SRV DNS record to find replica set members.

### 4. GitHub Actions — Sync Workflow (private repo → MongoDB)

```yaml
# .github/workflows/sync-identity.yml
# Triggered when identity files change in the private repo

name: Sync Identity to MongoDB

on:
  push:
    branches: [main]
    paths:
      - "identity/**"

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"

      - run: npm ci

      - name: Sync to MongoDB
        env:
          MONGODB_URI: ${{ secrets.MONGODB_URI }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}  # for embeddings
        run: node scripts/sync-to-mongodb.js

      # To push summary/manifest to a PUBLIC repo (the Pages dashboard):
      - name: Checkout public repo
        uses: actions/checkout@v4
        with:
          repository: kees/breakfast-club-public  # the Pages repo
          path: public-repo
          token: ${{ secrets.CROSS_REPO_PAT }}    # fine-grained PAT, NOT GITHUB_TOKEN

      - name: Update public manifest
        run: |
          node scripts/generate-public-manifest.js > public-repo/data/manifest.json
          cd public-repo
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/manifest.json
          git diff --staged --quiet || git commit -m "chore: sync identity manifest [skip ci]"
          git push
```

**CRITICAL GOTCHA: Infinite loop prevention.**

`GITHUB_TOKEN` pushes do NOT trigger subsequent workflow runs — GitHub suppresses this by design. But if you use a PAT (required for cross-repo pushes), that push WILL trigger the target repo's workflows. Two defenses:
1. Add `[skip ci]` to the commit message (GitHub Actions honors this)
2. Filter in the target workflow with `if: github.actor != 'github-actions[bot]'`

**GOTCHA: GITHUB_TOKEN cannot push to a different repo.** It is scoped to the running repo only. Cross-repo writes require a fine-grained PAT stored as a secret.

### 5. GitHub Pages — Static Dashboard

Structure in the public repo:
```
/
├── index.html           # entry point
├── style.css
├── app.js               # vanilla JS, fetches data/manifest.json
└── data/
    └── manifest.json    # generated by GitHub Actions sync, public-safe only
```

Enable in repo Settings → Pages → Source: Deploy from branch `main` → folder `/` (root) or `/docs`.

**CORS situation:** GitHub Pages cannot have custom response headers. The dashboard can only `fetch()` from:
- The same GitHub Pages origin (same repo's `data/` folder — fine for `manifest.json`)
- External APIs that already serve `Access-Control-Allow-Origin: *` (e.g., public GitHub API endpoints, public MongoDB Data API if used)

For Breakfast Club: the dashboard reads `data/manifest.json` from its own Pages origin — no CORS issue. Do NOT attempt to `fetch()` MongoDB Atlas directly from the dashboard; Atlas does not serve browser-accessible CORS headers on the free tier driver protocol.

---

## MongoDB Atlas M0 Free Tier: Constraint Inventory

| Constraint | Value | Impact on Breakfast Club |
|------------|-------|--------------------------|
| Storage | 512 MB | Fine for identity JSON + embeddings |
| Max connections | 500 (some sources say 100 concurrent) | Fine for MCP server (single process) |
| Sort memory | 32 MB | Avoid large in-memory sorts |
| Ops/second | ~100 | Fine for identity lookups |
| Vector search indexes | **1 per free cluster** | Plan your single vector index carefully |
| Atlas Search (text) | Available on M0 with driver-based index creation | Use `$search` aggregation stage |
| Vector index creation | Driver + Atlas UI both work; CLI `createSearchIndex` may error with "Command not found" | Create index via Atlas UI or driver `createSearchIndex()` method |
| MongoDB version required | 7.0.2+ for `$vectorSearch` | Atlas M0 runs current; verify in console |

**The single vector index limit is the most significant constraint.** Design the index to cover all vector search use cases:
- Either index one field across all documents
- Or use a compound vector index with filters

If you need text search AND vector search on M0, you get one vector index and separate Atlas Search indexes (text). Text search indexes are not subject to the same 1-index limit.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| MCP transport | stdio (local) | Streamable HTTP | HTTP adds auth complexity; MCP clients spawn stdio locally |
| GitHub SDK | `@octokit/rest` | `octokit` (all-in-one) | Heavier, unnecessary for REST-only access |
| GitHub SDK auth | Fine-grained PAT | GitHub App | App setup is overkill for single-user identity server |
| DB driver | `mongodb` native | Mongoose | ODM overhead unnecessary; native driver better for flexible identity schemas |
| Dashboard framework | Vanilla HTML/JS | React + Vite | Build step = GitHub Actions complexity; Pages serves HTML natively |
| DB for identity | MongoDB Atlas | GitHub raw files only | MongoDB enables semantic search; GitHub repo provides source of truth + verification |

---

## Surprising Constraints and Gotchas

### MCP SDK
- **ESM-only.** Must use `"type": "module"` in package.json and `.js` extensions on all imports.
- **`console.log` kills stdio servers.** Any stdout write corrupts JSON-RPC. Patch startup ASAP by auditing all deps that print to stdout.
- **v2 is NOT production-ready** as of Q1 2026. The npm latest (1.27.1) is v1.x. Do not install from the GitHub main branch.
- **Zod peer dep:** SDK ships with internal zod/v4 usage. If you use zod v3 in tool schemas, use 3.25+ which has the v4 compatibility shim.

### Octokit
- **`repos.getContent` TypeScript types are wrong.** The return type union is not discriminated properly; you must manually check for `Array.isArray` and `response.data.type === 'file'` before accessing `.content`.
- **Base64 content has embedded newlines.** Use `Buffer.from(content, "base64")`, not `atob()`.
- **Files >1 MB cannot be retrieved via the Contents API.** Use the Git Data API (`git.getBlob`) for large files if identity documents grow.
- **Rate limit is per-user, not per-repo.** 5,000 requests/hour total across all your API calls.

### MongoDB Atlas
- **SRV connection string only.** `mongodb+srv://` not `mongodb://`. The driver resolves DNS; firewalls blocking SRV lookups will cause intermittent failures.
- **One vector search index on M0.** This is a hard limit documented in the MongoDB changelog (April 2025). Plan before creating.
- **Vector index creation via UI vs driver:** The Atlas UI is reliable. The driver `createSearchIndex()` method works on M0 for vector indexes but you may see "Command not found" if running against an older MongoDB version. Always test after cluster version upgrades.
- **Connection pool on free tier:** Keep `maxPoolSize` at 10 or lower. M0 connections are shared across all databases in your organization. Exhausting the limit will cause connection failures with no meaningful error message.
- **No Atlas Data API on M0 for browser access.** The Data API (HTTPS REST endpoint to MongoDB) is not available on M0. Do not design the dashboard to query MongoDB directly.

### GitHub Actions
- **GITHUB_TOKEN cannot write to other repos.** Requires a separate PAT stored as a secret.
- **PAT pushes DO trigger target repo workflows.** GITHUB_TOKEN pushes do not. Use `[skip ci]` in commit messages for bot commits.
- **Workflow triggered by GITHUB_TOKEN push to same repo does NOT re-trigger.** This is intentional loop prevention. If your sync workflow commits back to the same private repo, the commit will land silently without triggering another run.
- **Action minute limits on free tier:** GitHub Actions free tier gives 2,000 minutes/month for private repos. Identity sync is fast; this is not a concern unless you push dozens of times per day.

### GitHub Pages
- **Cannot set CORS headers.** You cannot configure `Access-Control-Allow-Origin` on GitHub Pages. Static files are served as-is.
- **No server-side logic.** 100% static. All dynamic behavior must be client-side JS reading pre-generated JSON.
- **Build step is optional but not automatic.** Push raw HTML/JS/CSS and Pages serves it. No Jekyll processing needed (add `.nojekyll` file to disable Jekyll if you use underscored filenames).
- **Custom domain on Pages does not cost money** but requires DNS configuration. `pages.github.com` subdomain is free.

---

## Sources

- MCP TypeScript SDK — [GitHub](https://github.com/modelcontextprotocol/typescript-sdk), [npm (1.27.1)](https://www.npmjs.com/package/@modelcontextprotocol/sdk), [official docs](https://modelcontextprotocol.io/docs/develop/build-server)
- MCP transports specification — [modelcontextprotocol.io/specification/2025-03-26/basic/transports](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)
- MCP transport blog post — [MCP Transport Future (Dec 2025)](https://blog.modelcontextprotocol.io/posts/2025-12-19-mcp-transport-future/)
- Octokit REST — [GitHub](https://github.com/octokit/octokit.js), [npm](https://www.npmjs.com/package/octokit)
- Octokit `getContent` types issue — [octokit/types.ts#267](https://github.com/octokit/types.ts/issues/267), [octokit/rest.js#32](https://github.com/octokit/rest.js/issues/32)
- MongoDB Atlas free tier limits — [Atlas Free Cluster Limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/)
- MongoDB Atlas vector search — [Node.js Driver docs](https://www.mongodb.com/docs/drivers/node/current/atlas-vector-search/)
- MongoDB Atlas vector search on M0 — [community forum discussion](https://www.mongodb.com/community/forums/t/is-vector-search-feature-paid-or-free/267191)
- GitHub rate limits — [REST API rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- GitHub Actions secrets — [Using secrets in GitHub Actions](https://docs.github.com/actions/security-guides/using-secrets-in-github-actions)
- GitHub Actions loop prevention — [community discussion #25702](https://github.com/orgs/community/discussions/25702)
- Cross-repo push with PAT — [some-natalie.dev blog](https://some-natalie.dev/blog/multi-repo-actions/)
- GitHub Pages CORS — [community discussion #22399](https://github.com/orgs/community/discussions/22399)
