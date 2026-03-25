# Phase 1: Foundation - Research

**Researched:** 2026-03-26
**Domain:** MCP Server (Node.js/TypeScript), MongoDB Atlas Vector Search, JSON Schema design, SKILL.md authoring
**Confidence:** HIGH

## Summary

Phase 1 builds the identity store, owner MCP tools, and SKILL.md that everything else depends on. The technical stack is well-understood: TypeScript with ESM, the official MCP SDK (`@modelcontextprotocol/sdk` v1.28.0), MongoDB Atlas M0 free tier with Atlas Vector Search, and the OpenAI embeddings API. All three are mature and documented.

The single hardest constraint is MongoDB M0's one-vector-index limit. Every document type in the system — identity sections (persona, skills, projects, values) and future memory chunks — must share a single Atlas Vector Search index. This requires a `doc_type` discriminator field (indexed as a filter field) on every document so `$vectorSearch` can pre-filter by type. Getting this schema wrong before any data is loaded forces a full collection drop and reindex. Design it first; the planner must treat the schema/index definition as the first locked deliverable.

The MCP stdio transport has one ironclad rule: `console.log()` is banned. Every byte written to stdout is part of the JSON-RPC stream. A single stray `console.log` will corrupt it silently — no error, just broken tool responses. Every log statement must use `console.error()`. This rule must be enforced in linting, not just documentation.

**Primary recommendation:** Lock the MongoDB document schema and vector index definition (including filter fields) before writing any tool handlers. Everything else flows from that foundation.

---

<user_constraints>
## User Constraints (from CONTEXT.md / STATE.md decisions)

### Locked Decisions
- **Schema sensitivity tiers:** Four tiers — `public`, `professional`, `personal`, `private` — drive projection enforcement from day one. These are locked and non-negotiable.
- **MongoDB single unified embedding field:** Single `embedding` field across all document types; M0 one-index limit is a hard constraint; schema must be designed before ingesting any data.
- **Auth:** Start with fine-grained PAT for sync pipeline, document GitHub App upgrade path; abstract via environment variable. (Phase 1 does not use the sync pipeline — MCP reads MongoDB directly; PAT only needed in Phase 3.)
- **Projections:** Whitelist model enforced in `applyProjection()` inside every tool handler; no-scope default is `public`, never `owner`. (Phase 2 implements projection engine; Phase 1 must design schema with sensitivity labels to make this possible.)
- **Logging:** `console.error()` everywhere in MCP server; `console.log()` is BANNED — stdout contamination silently corrupts JSON-RPC.
- **Infrastructure:** $0/month. Free tiers only. MongoDB Atlas M0 + GitHub free tier.
- **Language:** Node.js / TypeScript throughout. ES modules (import/export), not CommonJS.

### Claude's Discretion
- Embedding model choice for Phase 1 seed data. OpenAI `text-embedding-3-small` (1536 dims, requires API key) vs local Ollama (free, no API key). Recommendation below: use OpenAI for seed data upload — M0 limit means the choice is locked once the index is created; OpenAI is the safer bet for semantic quality.
- Token budget strategy for `identity_context` tool (must stay under 1200 tokens). Implementation approach (pre-rendered string vs runtime assembly) is at implementer's discretion.
- SKILL.md generation approach: static file checked into repo vs runtime-generated. Recommendation: static, committed file — simpler and survives MCP server restarts.

### Deferred Ideas (OUT OF SCOPE for Phase 1)
- Projection engine (`applyProjection()`) — Phase 2
- Scoped projection tokens — Phase 2
- Sync pipeline (GitHub Action) — Phase 3
- Hash attestation chain — Phase 3
- Recruiter chatbot — Phase 2
- Blockchain anchoring — v2
- Bittensor subnet — v2
- ZK proofs — v2
- Memory chunking / conversation ingestion — Phase 4
- Verification dashboard — Phase 5
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| IDNT-01 | Private repo template has a defined JSON schema for persona (name, communication style, working style, preferences, dislikes) | Schema design section; nick-identity.json already exists as reference |
| IDNT-02 | Private repo template has a defined JSON schema for skills (primary stack, domain expertise, trades knowledge) | Same; skills section in nick-identity.json is the template |
| IDNT-03 | Private repo template has a defined JSON schema for active projects (name, status, description, stack) | Same; projects section |
| IDNT-04 | Private repo template has a defined JSON schema for values and beliefs (professionally relevant fields only) | Same; values section |
| IDNT-05 | All schema fields have a sensitivity label (personal/professional/public) for projection enforcement | Sensitivity tier pattern documented below |
| IDNT-06 | Founder's identity (nick-identity.json) validates against the schema and is loaded as seed data | seed-data/nick-identity.json exists; needs JSON Schema validation + MongoDB upsert |
| MCP-01 | MCP server runs as stdio process compatible with Claude Desktop and Claude Code | MCP SDK stdio transport pattern documented below; tsconfig/package.json config included |
| MCP-02 | `identity_context` tool returns synthesized persona/skills/projects context for system prompt injection (600-1200 token budget) | Token budget pattern documented; recommended approach: assemble sections, trim to budget |
| MCP-03 | `identity_query` tool does semantic search across identity data using MongoDB Atlas vector search | $vectorSearch pipeline documented; requires embedding the query at call time |
| MCP-04 | `projects_list` tool returns current active projects with status | Simple MongoDB find; no vector search needed |
| MCP-05 | `verify_integrity` tool returns current git tree SHA and checks against public attestation chain | Phase 1: return git tree SHA from GitHub API; attestation chain check is Phase 3 |
| MCP-06 | MCP server connects to MongoDB lazily on first tool call and caches the connection for the session lifetime | Singleton connection pattern documented below |
| MCP-07 | All MCP server logging goes to stderr (stdout reserved for JSON-RPC message stream) | console.error() rule documented; enforcement strategy: ESLint no-console rule |
| SKIL-01 | SKILL.md exists in the private repo root with instructions for any AI to use the identity store | Draft SKILL.md already exists in breakfast-club/SKILL.md — needs refinement and token count check |
| SKIL-02 | SKILL.md uses Markdown with `<identity>` XML wrapper format for cross-model compatibility | Pattern documented below |
| SKIL-03 | SKILL.md instructs the AI on persona loading, project context, memory search, and projection-scoped behavior | Covered in existing draft; gap: memory search instructions premature (Phase 4) — use placeholder |
| SKIL-04 | SKILL.md stays within 600-token budget when injected as a system prompt prefix | Token budget measurement: use tiktoken or rough word count; ~450 words ≈ 600 tokens |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@modelcontextprotocol/sdk` | 1.28.0 | MCP server implementation, stdio transport | Official Anthropic SDK; only supported path for Claude Desktop/Code integration |
| `mongodb` | 7.1.1 | MongoDB Node.js driver | Official driver; async/await native; no Mongoose needed (adds complexity without value) |
| `zod` | 4.3.6 | Schema validation for MCP tool inputs | Required peer dependency of MCP SDK; v4 is current |
| `openai` | 6.33.0 | Embeddings API for generating `embedding` field | text-embedding-3-small is the standard choice for 1536-dim Atlas vector index |
| `typescript` | 6.0.2 | Language | Project-mandated |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@types/node` | 25.5.0 | Node.js TypeScript types | Always — needed for process, console, etc. |
| `ajv` | latest | JSON Schema validation for nick-identity.json | Use for IDNT-06 validation step; lightweight, no runtime deps |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `openai` embeddings | Ollama local model | Ollama: free, no API key, but requires local GPU/CPU; embedding dimensions vary by model and lock the vector index. OpenAI: costs money per call but well-documented, 1536 dims is the Atlas sweet spot |
| `mongodb` driver direct | Mongoose ODM | Mongoose adds schema enforcement at the ORM layer which duplicates Zod; bare driver is lighter and fits the "no over-engineering" principle |
| `ajv` for validation | Zod for JSON Schema | Zod is already in the project; but AJV handles standard JSON Schema files better if a `.schema.json` file is the deliverable |

**Installation:**
```bash
npm install @modelcontextprotocol/sdk zod mongodb openai
npm install -D @types/node typescript
```

**Version verification (confirmed 2026-03-26):**
```bash
npm view @modelcontextprotocol/sdk version  # 1.28.0
npm view mongodb version                    # 7.1.1
npm view zod version                        # 4.3.6
npm view openai version                     # 6.33.0
npm view typescript version                 # 6.0.2
```

---

## Architecture Patterns

### Recommended Project Structure
```
src/
├── index.ts          # Entry point: McpServer setup, transport connect, signal handlers
├── db.ts             # MongoDB singleton: lazy connect, cached client, getDb()
├── tools/
│   ├── identity-context.ts    # identity_context tool handler
│   ├── identity-query.ts      # identity_query tool handler (vector search)
│   ├── projects-list.ts       # projects_list tool handler
│   └── verify-integrity.ts    # verify_integrity tool handler
├── schema/
│   └── identity.schema.json   # JSON Schema for nick-identity.json validation
└── types.ts          # Shared TypeScript interfaces (IdentityDocument, etc.)

identity/             # Private repo template — the "brain"
├── nick-identity.json         # Seed data (IDNT-06)
└── projections/               # Phase 2 — placeholder only in Phase 1

SKILL.md              # AI instruction file (SKIL-01 through SKIL-04)
```

### Pattern 1: McpServer with stdio transport (MCP-01, MCP-07)
**What:** McpServer class from `@modelcontextprotocol/sdk/server/mcp.js`, connected via StdioServerTransport
**When to use:** Always — this is the only supported pattern for Claude Desktop/Code integration
**Example:**
```typescript
// Source: https://modelcontextprotocol.io/docs/develop/build-server
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({
  name: "breakfast-club-identity",
  version: "1.0.0",
});

// Register tools with registerTool()
server.registerTool(
  "identity_context",
  {
    description: "Return synthesized identity context for system prompt injection",
    inputSchema: {
      max_tokens: z.number().optional().default(1200).describe("Token budget ceiling"),
    },
  },
  async ({ max_tokens }) => {
    // ... handler body
    return { content: [{ type: "text", text: contextString }] };
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Breakfast Club MCP server running on stdio"); // stderr only
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
```

### Pattern 2: Lazy MongoDB singleton (MCP-06)
**What:** Single MongoClient created on first tool call, cached for process lifetime
**When to use:** Always — MCP server processes are long-lived; connection pooling is automatic in the driver
**Example:**
```typescript
// Source: MongoDB Node.js driver docs + singleton pattern
import { MongoClient, Db } from "mongodb";

let client: MongoClient | null = null;

export async function getDb(): Promise<Db> {
  if (!client) {
    const uri = process.env.MONGODB_URI;
    if (!uri) throw new Error("MONGODB_URI not set");
    client = new MongoClient(uri);
    await client.connect();
    console.error("MongoDB connected"); // stderr only
  }
  return client.db(process.env.MONGODB_DB_NAME ?? "breakfast-club");
}
```

### Pattern 3: MongoDB Atlas Vector Search with pre-filter (MCP-03)
**What:** `$vectorSearch` aggregation stage with `filter` on `doc_type` field
**When to use:** For `identity_query` tool; also the pattern Phase 4 memory search will extend
**Key constraint:** The `doc_type` field (or any filter field) MUST be defined in the vector index definition as type `"filter"`. Without this, filtering is not supported.

**Vector index definition (create once in Atlas UI or via API, cannot be done programmatically on M0):**
```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "doc_type"
    },
    {
      "type": "filter",
      "path": "sensitivity"
    }
  ]
}
```

**$vectorSearch query (TypeScript):**
```typescript
// Source: MongoDB Atlas Vector Search documentation
const queryEmbedding = await embedText(question); // call OpenAI embeddings API

const results = await db.collection("identity").aggregate([
  {
    $vectorSearch: {
      index: "identity_vector_index",
      path: "embedding",
      queryVector: queryEmbedding,
      numCandidates: 50,
      limit: 5,
      filter: { doc_type: "identity" }, // pre-filter: identity only, not memory chunks
    },
  },
  {
    $project: {
      _id: 0,
      section: 1,
      content: 1,
      sensitivity: 1,
      score: { $meta: "vectorSearchScore" },
    },
  },
]).toArray();
```

### Pattern 4: ESM TypeScript configuration (MCP-01)
**What:** package.json + tsconfig.json required for ESM MCP servers
**When to use:** Always — MCP SDK uses ESM imports, ESM is required

**package.json key fields:**
```json
{
  "type": "module",
  "scripts": {
    "build": "tsc && chmod 755 build/index.js",
    "start": "node build/index.js"
  }
}
```

**tsconfig.json:**
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "outDir": "./build",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  }
}
```

**Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):**
```json
{
  "mcpServers": {
    "breakfast-club-identity": {
      "command": "node",
      "args": ["/absolute/path/to/breakfast-club/build/index.js"],
      "env": {
        "MONGODB_URI": "mongodb+srv://...",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

### Pattern 5: SKILL.md format (SKIL-01 through SKIL-04)
**What:** Markdown with `<identity>` XML wrapper for cross-model parsing compatibility
**When to use:** Wrap the entire SKILL.md content in the XML tag when injected as system prompt prefix

**Structure:**
```markdown
<identity>
# [Owner Name] — AI Identity

## Who You're Talking To
[2-3 sentences from persona: communication style, working style]

## How To Load Context
Call `identity_context` at conversation start. Returns synthesized persona/skills/projects.

## How To Search Identity
Call `identity_query` with a natural-language question. Returns semantically relevant results.

## How To List Projects
Call `projects_list`. Returns active projects with status.

## Projection Rules
[Placeholder in Phase 1 — projection enforcement is Phase 2]
</identity>
```

**Token budget target:** Under 600 tokens. Measure with: `Math.ceil(content.split(/\s+/).length * 1.3)` as a rough estimate (words × 1.3 ≈ tokens for English prose). Use tiktoken for exact count.

### Anti-Patterns to Avoid
- **`console.log()` anywhere in MCP server:** Corrupts JSON-RPC stream silently. Every log must be `console.error()`. Add ESLint `no-console` rule with `warn` exception for `console.error` only.
- **Multiple vector indexes on M0:** Atlas M0 allows exactly one vector search index. Attempting to create a second will fail. All documents (identity + future memory) share one index and are distinguished by the `doc_type` filter field.
- **Creating the vector index programmatically on M0:** Atlas M0 does not support `createSearchIndex()` from the driver. The index must be created manually in the Atlas UI or via the Atlas Admin API. This is a manual step in Plan 01-02.
- **Ingesting data before the vector index is defined:** Documents without an `embedding` field (or with wrong dimensions) cause vector search to return no results. Load the index definition, then ingest seed data.
- **Committing MONGODB_URI or OPENAI_API_KEY to git:** Use environment variables; document in `.env.example`; add `.env` to `.gitignore`.
- **Using CommonJS `require()` syntax:** MCP SDK is ESM-only. `import` statements only.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vector similarity search | Custom cosine similarity in JS | MongoDB Atlas `$vectorSearch` | Approximate Nearest Neighbor at scale; handles indexing, recall guarantees, pre-filtering |
| JSON Schema validation | Manual field checks | `ajv` + `.schema.json` file | Edge cases in type coercion, required fields, nested objects; AJV is spec-compliant |
| Embedding generation | Custom model inference | OpenAI `text-embedding-3-small` API | Consistent dimensions (1536), high quality, locked to M0 index dimensions |
| MCP protocol framing | Custom stdio JSON-RPC | `@modelcontextprotocol/sdk` | Protocol versioning, capability negotiation, schema registry — all handled |
| Connection pooling | Manual connection retry logic | `mongodb` driver built-in pool | Driver manages pool size, reconnect, heartbeat automatically |

**Key insight:** The MCP SDK and MongoDB driver together eliminate ~2,000 lines of protocol and connection management code. The application is tool handlers and schema design — that's the only novel work.

---

## Common Pitfalls

### Pitfall 1: stdout contamination breaking the JSON-RPC stream
**What goes wrong:** Tool calls return garbled JSON or connection drops; Claude Desktop shows "Server disconnected" with no useful error.
**Why it happens:** Any `console.log()`, startup banner, debug print, or third-party library that writes to stdout corrupts the framing. The JSON-RPC parser sees mixed protocol messages and garbage.
**How to avoid:** Ban `console.log()` with ESLint. Use only `console.error()`. Audit all imported packages for stdout writes (rare but possible with legacy packages).
**Warning signs:** MCP tools return errors immediately; `npx @modelcontextprotocol/inspector node build/index.js` shows parse errors.

### Pitfall 2: Vector index dimensions locked at creation time
**What goes wrong:** Plan switches embedding model mid-phase; new embeddings are 768 dims but index expects 1536. All vector search returns empty results or errors.
**Why it happens:** Atlas vector index `numDimensions` cannot be changed after creation. The collection must be dropped and index recreated.
**How to avoid:** Commit to embedding model (OpenAI text-embedding-3-small, 1536 dims) before creating the index. Document the choice. Don't change it without a migration plan.
**Warning signs:** `$vectorSearch` returns zero results; no error thrown (silent failure).

### Pitfall 3: M0 cannot create vector index programmatically
**What goes wrong:** `collection.createSearchIndex()` call in setup script throws a permission or feature error on M0.
**Why it happens:** Atlas Search index management APIs require a dedicated cluster (M10+) or Atlas Admin API. M0 shared clusters only allow index creation via the Atlas UI.
**How to avoid:** Create the vector index manually in the Atlas UI during Plan 01-02. Document the exact index JSON definition in the plan so it's reproducible.
**Warning signs:** Driver throws "Atlas Search index creation not supported on shared tier" or similar.

### Pitfall 4: SKILL.md exceeds 600-token budget
**What goes wrong:** SKILL.md is injected as a system prompt prefix; tokens consumed reduce the context window available for conversation.
**Why it happens:** Descriptions get verbose; tool parameter lists bloat the file.
**How to avoid:** Measure token count at commit time. Target: instructions, not documentation. Bullet points, not paragraphs. Under 450 words is a safe proxy for under 600 tokens.
**Warning signs:** SKILL.md over 600 words; AIs see truncated instructions.

### Pitfall 5: Embedding seed data without `doc_type` filter field
**What goes wrong:** `$vectorSearch` with `filter: { doc_type: "identity" }` returns no results even though documents exist.
**Why it happens:** The `doc_type` field exists in the document but was not listed as a `"filter"` type field in the vector index definition. Atlas vector search only pre-filters on indexed filter fields.
**How to avoid:** Define the vector index with all anticipated filter fields (`doc_type`, `sensitivity`) before ingesting any documents.
**Warning signs:** Vector search returns empty array; `explain()` shows filter not applied.

### Pitfall 6: Sensitivity label missing on schema fields
**What goes wrong:** Phase 2 projection engine (`applyProjection()`) cannot enforce field-level access control because fields don't carry sensitivity metadata.
**Why it happens:** Schema is designed without Phase 2 in mind; sensitivity labels added as afterthought require data migration.
**How to avoid:** Add `sensitivity` to every schema field or section in IDNT-01 through IDNT-04. Use the four locked tiers: `public`, `professional`, `personal`, `private`. This is a Phase 1 deliverable (IDNT-05).
**Warning signs:** Phase 2 planning blocked because projection enforcement has no schema anchor.

---

## Code Examples

### MongoDB document shape for identity sections
```typescript
// Source: design derived from nick-identity.json + M0 vector index constraints
interface IdentityDocument {
  _id?: ObjectId;
  doc_type: "identity";          // filter field — discriminates from memory chunks (Phase 4)
  section: "persona" | "skills" | "projects" | "values";
  sensitivity: "public" | "professional" | "personal" | "private";
  schema_version: string;        // e.g. "0.1.0"
  content: Record<string, unknown>; // the actual identity data
  embedding: number[];           // 1536-dim vector from text-embedding-3-small
  embedding_model: string;       // "text-embedding-3-small" — locked to index dims
  source_hash?: string;          // SHA-256 of canonical JSON (Phase 3 fills this)
  git_tree_sha?: string;         // Phase 3 fills this
  updated_at: Date;
}
```

### Tool return shape
```typescript
// Source: MCP SDK documentation — all tools return this structure
return {
  content: [
    {
      type: "text",
      text: assembledContext,
    },
  ],
};
```

### Environment variables required
```
MONGODB_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/
MONGODB_DB_NAME=breakfast-club
OPENAI_API_KEY=sk-...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CommonJS `require()` for Node.js | ESM `import` with `"type": "module"` | Node.js 12+, enforced by MCP SDK | Must use `module: "Node16"` in tsconfig |
| Mongoose ODM for MongoDB | Bare `mongodb` driver | Always valid; preference shift | Mongoose adds boilerplate; bare driver is lighter for this use case |
| Separate vector DB (Pinecone, Weaviate) | MongoDB Atlas `$vectorSearch` | 2023-present | Eliminates separate infrastructure; respects M0 free tier |
| `Server` class from MCP SDK v0.x | `McpServer` class from v1.x | MCP SDK v1.0 | `McpServer` is the current higher-level API; `Server` is lower-level and still valid |

**Deprecated/outdated:**
- `@modelcontextprotocol/server` (old package name): replaced by `@modelcontextprotocol/sdk`
- `server.tool()` shorthand: `server.registerTool()` is the current API as of SDK 1.x (both may work; use `registerTool` for explicitness)

---

## Open Questions

1. **Embedding model choice**
   - What we know: OpenAI text-embedding-3-small = 1536 dims, ~$0.00002/1K tokens, requires API key. Ollama (e.g. nomic-embed-text) = 768 dims, free, local.
   - What's unclear: Whether kees has an OpenAI API key set up; whether he wants to avoid API costs for seed data.
   - Recommendation: Default to OpenAI for Phase 1 seed data. The identity JSON is small (~5KB); embedding cost is negligible (<$0.001). The 1536-dim index is better supported by Atlas documentation. Document Ollama as a fallback in the plan.

2. **`verify_integrity` tool scope in Phase 1**
   - What we know: MCP-05 says "returns current git tree SHA and checks against public attestation chain." The attestation chain is Phase 3.
   - What's unclear: Should the tool return an error/stub for the attestation check, or omit that check entirely?
   - Recommendation: Phase 1 implementation returns the git tree SHA (from GitHub API or local git) and marks the attestation check as "pending Phase 3." Tool should succeed, not error, with a human-readable note.

3. **Token counting for SKILL.md**
   - What we know: The 600-token budget must be verified; existing SKILL.md draft is ~350 words.
   - What's unclear: Whether to use tiktoken (requires Python or npm package) or a rough heuristic.
   - Recommendation: Use `npm install -D tiktoken` for exact counting at build time, or use the rough heuristic (words × 1.3). Either is acceptable; document which approach is used.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | MCP server runtime | Yes | v22.22.0 | — |
| npm | Package management | Yes | 10.9.4 | — |
| MongoDB Atlas M0 | Identity store + vector search | Not verified (cloud) | — | Must provision — no fallback |
| OpenAI API | Embeddings for seed data | Not verified (API key) | — | Ollama local (768 dims — changes index) |
| TypeScript | Build | Yes (npm install) | 6.0.2 | — |

**Missing dependencies with no fallback:**
- MongoDB Atlas M0 cluster — must be provisioned in Atlas UI as part of Plan 01-02. Free tier signup required if not already done.

**Missing dependencies with fallback:**
- OpenAI API key — required for text-embedding-3-small. Fallback: Ollama with nomic-embed-text (768 dims), but this changes the vector index definition and must be decided before index creation.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None yet — integration tests only per CLAUDE.md |
| Config file | None — see Wave 0 |
| Quick run command | `node build/index.js` (smoke: server starts without crashing) |
| Full suite command | Manual: register with Claude Desktop, call each tool, verify output |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IDNT-06 | nick-identity.json validates against schema | Integration | `node scripts/validate-seed.js` | No — Wave 0 |
| MCP-01 | Server starts and accepts stdio connection | Smoke | `npx @modelcontextprotocol/inspector node build/index.js` | No |
| MCP-02 | `identity_context` returns ≤1200 tokens | Integration | `node scripts/test-tools.js identity_context` | No — Wave 0 |
| MCP-03 | `identity_query` returns semantically relevant results | Integration | `node scripts/test-tools.js identity_query "what are nick's skills"` | No — Wave 0 |
| MCP-04 | `projects_list` returns active projects | Integration | `node scripts/test-tools.js projects_list` | No — Wave 0 |
| MCP-07 | No stdout output during operation | Smoke | `node build/index.js 2>/dev/null | head -1` should show no output | No |
| SKIL-04 | SKILL.md under 600 tokens | Static check | `node scripts/count-tokens.js SKILL.md` | No — Wave 0 |

Per CLAUDE.md: "integration tests that prove the thing works, not unit tests for getters." Unit tests for individual functions are not required.

### Sampling Rate
- **Per task commit:** Start server, call the relevant tool(s), verify output shape
- **Per wave merge:** All tool calls smoke-tested via MCP inspector
- **Phase gate:** All 4 owner tools callable and returning valid responses; SKILL.md token count verified

### Wave 0 Gaps
- [ ] `scripts/validate-seed.js` — validates nick-identity.json against JSON Schema
- [ ] `scripts/test-tools.js` — calls each MCP tool and prints output
- [ ] `scripts/count-tokens.js` — counts tokens in SKILL.md
- [ ] `tsconfig.json` — ESM config per MCP SDK requirements
- [ ] `package.json` — `"type": "module"`, build script, dependencies

---

## Sources

### Primary (HIGH confidence)
- [MCP TypeScript SDK official docs](https://modelcontextprotocol.io/docs/develop/build-server) — stdio server pattern, McpServer class, StdioServerTransport, logging rules, tsconfig/package.json config
- [npmjs.com @modelcontextprotocol/sdk](https://www.npmjs.com/package/@modelcontextprotocol/sdk) — confirmed version 1.28.0
- [npmjs.com mongodb](https://www.npmjs.com/package/mongodb) — confirmed version 7.1.1
- [npmjs.com zod](https://www.npmjs.com/package/zod) — confirmed version 4.3.6
- [npmjs.com openai](https://www.npmjs.com/package/openai) — confirmed version 6.33.0
- [mongocontextprotocol/typescript-sdk GitHub](https://github.com/modelcontextprotocol/typescript-sdk) — SDK structure and examples
- `breakfast-club/CLAUDE.md` — tech stack, code style, what not to build
- `breakfast-club/seed-data/nick-identity.json` — existing seed data structure
- `breakfast-club/SKILL.md` — existing SKILL.md draft

### Secondary (MEDIUM confidence)
- [MongoDB Atlas Vector Search docs](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-stage/) — $vectorSearch pipeline, filter fields, pre-filtering; M0 one-index limit confirmed via multiple community sources
- [OpenAI text-embedding-3-small](https://zilliz.com/ai-models/text-embedding-3-small) — 1536 dimensions confirmed
- Multiple WebSearch results confirming M0 free tier = single vector index limit

### Tertiary (LOW confidence)
- WebSearch results on MongoDB M0 index creation limitation (programmatic creation not supported) — cross-referenced with community forum posts but not from official docs page directly

---

## Project Constraints (from CLAUDE.md)

These directives from `breakfast-club/CLAUDE.md` are mandatory and override any conflicting research recommendations:

- **TypeScript strict mode** — `"strict": true` in tsconfig.json, no exceptions
- **ES modules** — `import/export` only; `require()` is forbidden
- **No Mongoose** — use the bare `mongodb` driver
- **No over-engineering** — if it works with a JSON file, don't add a database layer; if git gives integrity, don't add a blockchain yet
- **Free tier everything** — $0/month infrastructure; no paid services in Phase 1
- **Error handling: fail loud, fail early** — no swallowed exceptions; errors propagate up and crash the tool handler (MCP SDK returns the error to the client)
- **Integration tests over unit tests** — prove the thing works end-to-end; no getter tests
- **`console.log()` is banned** — only `console.error()` in MCP server code
- **No dependencies unless they earn their place** — every npm package is a liability; justify each one

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified against npm registry 2026-03-26
- Architecture: HIGH — patterns from official MCP SDK docs and MongoDB Atlas docs
- Pitfalls: HIGH — stdout contamination confirmed in MCP official docs; M0 index limit confirmed in multiple sources; filter field requirement from Atlas vector search docs
- SKILL.md format: MEDIUM — `<identity>` XML wrapper pattern is a reasonable inference from cross-model compatibility needs; not from an official spec

**Research date:** 2026-03-26
**Valid until:** 2026-06-01 (stable stack; MCP SDK releases infrequently; MongoDB Atlas free tier limits are stable)
