# Phase 2: Projection Engine + Recruiter Chatbot - Research

**Researched:** 2026-03-26
**Domain:** TypeScript projection engine, token-scoped API auth, Cloudflare Workers/Hono chatbot backend, static HTML UI, GitHub API audit trail
**Confidence:** HIGH (core stack), MEDIUM (token format decision), HIGH (infrastructure choice)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROJ-01 | Projection system uses whitelist model — only explicitly listed field categories included | `applyProjection()` function design, sensitivity-tier filtering pattern documented |
| PROJ-02 | At least three built-in projections: personal (full), professional (skills/projects/work-style), public (summary only) | JSON projection file schema, sensitivity tier mappings documented |
| PROJ-03 | Projection enforcement happens server-side in the MCP tool handler, never client-side | Pattern: every tool handler wraps response through `applyProjection()` before returning |
| PROJ-04 | Owner can create custom projections as JSON files in `projections/` directory | Projection loader reads `projections/*.json` at runtime; no code changes needed |
| PROJ-05 | Projection tokens are scoped API keys — a token tied to a projection can only access that projection's data | Token-to-projection binding design documented; opaque token recommended |
| RCTR-01 | Chatbot endpoint accepts a scoped token and serves only the professional projection | Hono route on Cloudflare Workers with Bearer token middleware |
| RCTR-02 | System prompt constrains to role-fit/experience/logistics; salary and personal data out of scope | System prompt design pattern documented |
| RCTR-03 | Recruiter can ask natural language questions and receive contextual answers grounded in real identity data | OpenAI chat completions API with identity context as system message |
| RCTR-04 | Chatbot queryable via simple web UI (shareable URL with token) requiring no technical setup | Vanilla HTML/JS + fetch streaming UI pattern documented |
| RCTR-05 | Every recruiter query logged in append-only audit trail in private repo | GitHub Contents API `createOrUpdateFileContents` pattern for append-only JSONL log |
</phase_requirements>

---

## Summary

Phase 2 builds on the Phase 1 MCP server and MongoDB identity store to deliver a recruiter-facing chatbot accessible via a shareable URL. The system has two distinct parts: (1) the **projection engine** embedded in the existing MCP server, and (2) a **new separate HTTP service** hosting the chatbot backend and static UI.

The projection engine is purely TypeScript logic — a whitelist filter function that wraps every MCP tool handler response, dropping identity fields not in the active projection's allowlist. Projections are defined as JSON files in a `projections/` directory; the loader reads them at startup, making custom projections zero-code additions. Three built-in projections cover `public` (summary only), `professional` (skills/projects/work-style), and `personal` (full owner access).

The chatbot backend is best deployed as a **Cloudflare Workers** endpoint using **Hono** as the HTTP framework. This is the $0/month path that supports MongoDB Atlas connections (as of 2025 via `nodejs_compat_v2` flag), streams OpenAI responses via SSE, and handles Bearer token validation in middleware. The worker reads the scoped projection for the presented token, queries MongoDB directly, constructs a constrained system prompt, and streams the OpenAI response. Every query is appended to an audit log JSONL file in the private GitHub repo via the GitHub Contents API.

The UI is a single static HTML file served directly from the Cloudflare Worker's static assets, requiring no build step and no technical setup from the recruiter. The shareable URL embeds the token in the query string.

**Primary recommendation:** Cloudflare Workers + Hono for the chatbot backend; opaque random tokens (not JWTs) stored in a KV-like map in environment secrets for Phase 2 scope; `applyProjection()` whitelist enforced at every tool handler boundary.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| hono | 4.12.9 | HTTP framework for Cloudflare Workers | First-party Cloudflare framework; TypeScript-native; streaming helpers built-in |
| wrangler | 4.77.0 | Cloudflare Workers CLI (dev + deploy) | Official Cloudflare toolchain; TypeScript support; `.dev.vars` for local secrets |
| openai | 6.33.0 | OpenAI chat completions + streaming | Already a project dependency from Phase 1 |
| mongodb | 7.1.1 | MongoDB Atlas connection from Worker | Already a project dependency; Worker-compatible with `nodejs_compat_v2` |
| @octokit/rest | 22.0.1 | GitHub Contents API for audit trail commits | Official GitHub SDK; handles base64 encoding and SHA for update operations |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| zod | 4.3.6 | Projection JSON schema validation | Already a project dependency; validate projection JSON files on load |
| jose | 6.2.2 | JWT signing/verification | Only needed if locked decision switches from opaque tokens to signed JWTs (see Open Questions) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Cloudflare Workers | Vercel serverless functions | Vercel is also $0 but has 10s execution limit on Hobby; Workers has no wall-time limit while client is connected; Workers is closer to the MongoDB Atlas edge |
| Opaque tokens (env map) | Signed JWTs (jose) | JWTs are stateless (no lookup), portable across restarts, self-expiring — but require a signing key and add complexity; opaque tokens are simpler, trivially revocable by deleting the env entry, sufficient for Phase 2 |
| Hono | Express on Vercel | Express has more ecosystem but Hono is purpose-built for Workers, ships streaming helpers out of the box |
| JSONL file in GitHub | MongoDB audit collection | GitHub append-only log satisfies the "private repo audit trail" requirement from RCTR-05 without a new collection; Phase 3 already writes to GitHub, establishing the pattern |

**Installation (new Worker project):**
```bash
npm create hono@latest chatbot-worker -- --template cloudflare-workers
cd chatbot-worker
npm install mongodb @octokit/rest
```

**Version verification (confirmed 2026-03-26):**
```
hono@4.12.9
wrangler@4.77.0
@octokit/rest@22.0.1
```

---

## Architecture Patterns

### Recommended Project Structure

The chatbot Worker is a **separate deployable** from the MCP server — it has its own `wrangler.toml` and is deployed independently to Cloudflare. The shared logic (`applyProjection`, types) lives in the main project and is referenced via relative imports.

```
breakfast-club/                  # existing project root
├── src/
│   ├── projection/
│   │   ├── apply-projection.ts  # applyProjection() — pure whitelist filter
│   │   ├── load-projections.ts  # reads projections/*.json at startup
│   │   └── types.ts             # ProjectionDefinition, ProjectionName types
│   ├── tools/                   # existing MCP tools — NOW wrap with applyProjection()
│   │   ├── identity-context.ts
│   │   ├── identity-query.ts
│   │   └── ...
│   └── index.ts                 # MCP server entry (unchanged)
│
├── projections/                 # owner-managed projection JSON files
│   ├── public.json
│   ├── professional.json
│   └── personal.json
│
└── chatbot-worker/              # NEW — Cloudflare Worker deployment
    ├── src/
    │   ├── index.ts             # Hono app + route definitions
    │   ├── middleware/
    │   │   └── auth.ts          # Bearer token validation → projection name
    │   ├── routes/
    │   │   ├── chat.ts          # POST /chat — query handler + SSE stream
    │   │   └── health.ts        # GET /health — status check
    │   └── lib/
    │       ├── identity.ts      # MongoDB query for scoped projection
    │       ├── openai.ts        # stream chat completions
    │       └── audit.ts         # append JSONL entry to GitHub repo
    ├── public/
    │   └── index.html           # static recruiter UI (served as Worker asset)
    ├── wrangler.toml
    └── package.json
```

### Pattern 1: applyProjection() — Whitelist Filter

**What:** Pure function that takes an `IdentityDocument[]` and a `ProjectionDefinition` and returns a filtered array with only allowlisted sensitivity tiers and field paths included.

**When to use:** Called inside every MCP tool handler that returns identity data, and called inside the chatbot Worker before feeding data to OpenAI.

```typescript
// src/projection/apply-projection.ts
// Source: pattern derived from Phase 1 SensitivityLevel type

export interface ProjectionDefinition {
  name: string;
  allowed_sections: IdentitySection[];          // e.g. ["skills", "projects"]
  allowed_sensitivity: SensitivityLevel[];       // e.g. ["public", "professional"]
  field_allowlist?: Record<string, string[]>;    // optional: field-level allowlist per section
}

export function applyProjection(
  docs: IdentityDocument[],
  projection: ProjectionDefinition
): IdentityDocument[] {
  return docs
    .filter(doc => projection.allowed_sections.includes(doc.section))
    .filter(doc => projection.allowed_sensitivity.includes(doc.sensitivity))
    .map(doc => ({
      ...doc,
      content: filterContent(doc.content, projection.field_allowlist?.[doc.section])
    }));
}

function filterContent(
  content: Record<string, unknown>,
  allowlist?: string[]
): Record<string, unknown> {
  if (!allowlist) return content;  // no field-level filter — whole section allowed
  return Object.fromEntries(
    Object.entries(content).filter(([key]) => allowlist.includes(key))
  );
}
```

**Critical invariant:** If `projection` is missing or lookup fails, the function MUST return `[]` — never fall back to returning the full document. "Fail closed" is the safety contract.

### Pattern 2: Projection JSON File Format

**What:** A JSON file in `projections/` defines a named projection. Owner creates new projections by adding files without code changes.

```json
// projections/professional.json
{
  "name": "professional",
  "description": "Recruiter-facing projection — skills, projects, work style only",
  "allowed_sections": ["skills", "projects"],
  "allowed_sensitivity": ["public", "professional"],
  "field_allowlist": {
    "persona": ["name", "working_style", "communication_style"]
  }
}
```

The loader reads all JSON files from `projections/` at server startup and caches them in a Map keyed by `name`. Missing projection name → throw, never silently degrade.

### Pattern 3: Token-to-Projection Binding

**What:** A scoped token (opaque random string) maps to exactly one projection name. Stored as environment variables / Cloudflare Worker secrets.

**Recommended format for Phase 2:** Encode the binding in the environment as a JSON string:

```bash
# wrangler secret put TOKEN_MAP
# Value (JSON string):
# {"tok_abc123": "professional", "tok_def456": "public"}
```

The auth middleware parses `TOKEN_MAP` env secret as JSON on startup, validates the Bearer token, and returns the projection name. If token is absent from the map, reject with 401. If no token is presented, default to `"public"` projection (never `"owner"` — locked decision).

**Revocation:** Delete the token entry from `TOKEN_MAP` and redeploy. No database needed for Phase 2.

### Pattern 4: Hono Worker with SSE Streaming

**What:** Hono's `streamText()` helper streams Server-Sent Events from OpenAI back to the browser.

```typescript
// Source: https://hono.dev/docs/helpers/streaming
// chatbot-worker/src/routes/chat.ts

import { streamText } from 'hono/streaming';

app.post('/chat', authMiddleware, async (c) => {
  const { message, history } = await c.req.json();
  const projectionName = c.get('projectionName');  // set by auth middleware

  const identityContext = await getIdentityForProjection(projectionName, c.env);
  const systemPrompt = buildSystemPrompt(identityContext, projectionName);

  const openai = new OpenAI({ apiKey: c.env.OPENAI_API_KEY });

  return streamText(c, async (stream) => {
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      stream: true,
      messages: [
        { role: 'system', content: systemPrompt },
        ...history,
        { role: 'user', content: message },
      ],
    });

    for await (const chunk of completion) {
      const delta = chunk.choices[0]?.delta?.content ?? '';
      if (delta) await stream.write(delta);
    }

    // Audit after stream completes
    await appendAuditEntry(message, projectionName, c.env);
  });
});
```

### Pattern 5: GitHub Audit Trail — Append-Only JSONL

**What:** Each recruiter query appends a JSON line to `audit/recruiter-queries.jsonl` in the private repo via the GitHub Contents API. The file is read, new line appended, and written back with the current file SHA to prevent conflicts.

```typescript
// chatbot-worker/src/lib/audit.ts

export async function appendAuditEntry(
  query: string,
  projectionName: string,
  env: Env
): Promise<void> {
  const octokit = new Octokit({ auth: env.GITHUB_TOKEN });
  const path = 'audit/recruiter-queries.jsonl';

  // Get current file (or empty if new)
  let currentContent = '';
  let fileSha: string | undefined;
  try {
    const { data } = await octokit.repos.getContent({
      owner: env.GITHUB_OWNER,
      repo: env.GITHUB_PRIVATE_REPO,
      path,
    });
    if ('content' in data) {
      currentContent = Buffer.from(data.content, 'base64').toString('utf8');
      fileSha = data.sha;
    }
  } catch (e) {
    // File doesn't exist yet — start fresh
  }

  const entry = JSON.stringify({
    timestamp: new Date().toISOString(),
    projection: projectionName,
    query_hash: await sha256(query),  // hash the query, not plaintext (privacy)
    query_preview: query.slice(0, 80),
  });

  const newContent = currentContent + entry + '\n';

  await octokit.repos.createOrUpdateFileContents({
    owner: env.GITHUB_OWNER,
    repo: env.GITHUB_PRIVATE_REPO,
    path,
    message: 'audit: recruiter query [skip ci]',
    content: Buffer.from(newContent).toString('base64'),
    sha: fileSha,
  });
}
```

**Note:** Race condition on concurrent writes is theoretically possible but tolerable at Phase 2 volume (single recruiter). If the 409 SHA conflict occurs, log the error to stderr and continue — the chat response is unaffected. Audit write failure must never block the chat response.

### Pattern 6: Constrained System Prompt

**What:** The chatbot system prompt anchors the LLM to the projection scope and refuses out-of-scope queries.

```
You are a professional profile assistant for [Name]. You have access to their
professional background: skills, projects, and work style.

SCOPE: Answer only questions about role fit, technical skills, project experience,
work approach, and logistics like availability and location.

OUT OF SCOPE — respond with "I'm not able to share that information":
- Salary expectations or compensation
- Personal relationships or personal life
- Home address or contact details
- Any information not present in the context below

Identity context:
[applyProjection() output formatted as structured text]
```

### Anti-Patterns to Avoid

- **Token hardcoded in URL path:** Use `?token=xxx` in the query string only. Never put a secret in a path segment that might appear in server logs.
- **Default to owner projection:** If token lookup fails or no token is presented, ALWAYS default to `public`. Never fall back to `owner` or `personal`. This is a locked decision.
- **Returning empty string instead of refusing:** The `applyProjection()` function returning `[]` is correct; the downstream formatter must handle empty results as "no data available for this query" — not as a passthrough to raw data.
- **Blocking chat on audit write:** Audit writes go to GitHub (external HTTP call, potentially slow). Always fire-and-forget or await after streaming starts — never before sending the first token.
- **`console.log()` in Worker code:** The same ban applies as in the MCP server. Cloudflare Workers surface `console.log` in the dashboard, but the practice bleeds into the MCP server if files are shared. Use `console.error()` everywhere.
- **Single MongoDB client per Worker invocation:** Cloudflare Workers isolates are reused across requests. The `client ??= new MongoClient(...)` pattern (connection reuse) is correct — do not create a new client on every request.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP routing + middleware | Custom Express-like router | Hono | Workers-native, TypeScript-first, streaming built-in, maintained by Cloudflare |
| SSE streaming | Manual `TransformStream` and SSE framing | `hono/streaming` `streamText()` | Handles SSE framing, error teardown, and Workers streaming semantics correctly |
| GitHub file updates | Raw `fetch()` against GitHub REST API | `@octokit/rest` `createOrUpdateFileContents` | Handles base64, SHA race, authentication headers, and retries |
| Token generation | UUID or Math.random() | `crypto.randomBytes(32).toString('hex')` (Node.js) | Cryptographically secure; sufficient entropy for opaque tokens; already available in Node 22 |
| JWT signing | Custom HMAC implementation | `jose` (if JWTs are chosen) | Handles RS256/HS256, expiry, claims validation — never hand-roll crypto |
| OpenAI streaming | Manually parsing SSE chunks from OpenAI | `openai` SDK with `stream: true` async iterator | SDK handles reconnection, chunk parsing, and finish reasons |

**Key insight:** The projection engine itself (whitelist filtering) is intentionally hand-rolled — it's the core IP of this system. Everything around it (HTTP, streaming, GitHub writes) should use battle-tested libraries.

---

## Common Pitfalls

### Pitfall 1: Cloudflare Workers MongoDB Connection — Missing nodejs_compat_v2 Flag

**What goes wrong:** `MongoClient.connect()` throws a `net.Socket` or `tls.TLSSocket not found` error; the Worker fails on all requests.
**Why it happens:** Cloudflare Workers V8 isolate does not include Node.js built-ins by default. The MongoDB driver requires `node:net` and `node:tls` which were only added behind `nodejs_compat_v2` flag.
**How to avoid:** `wrangler.toml` must include:
```toml
compatibility_flags = ["nodejs_compat_v2"]
compatibility_date = "2025-03-20"
```
Also set `maxPoolSize: 1, minPoolSize: 0` on MongoClient — Workers isolates don't maintain long-lived connections the same way a Node server does.
**Warning signs:** `Error: net is not defined` or `Cannot read property 'TLSSocket' of undefined` in Worker logs.

### Pitfall 2: applyProjection() Receiving Stale Cached Connection

**What goes wrong:** MongoDB client is cached at module scope in the Worker. On a cold start the client is null and connects fine. On a subsequent warm request, the cached client may have been dropped by Atlas M0 (M0 idles connections aggressively). Queries fail silently or return empty results.
**Why it happens:** MongoDB Atlas M0 free tier closes idle connections after ~60 seconds.
**How to avoid:** Add reconnect logic — catch `MongoNotConnectedError` and re-instantiate the client. Or pass `serverSelectionTimeoutMS: 5000` and let the driver retry on the next call.
**Warning signs:** Empty results on the second chatbot request after a gap.

### Pitfall 3: Audit Write Blocks Streaming Response

**What goes wrong:** The audit write to GitHub is awaited before the first SSE chunk is sent to the browser. The recruiter sees a blank screen for 1-3 seconds before the chat starts.
**Why it happens:** `await appendAuditEntry(...)` placed before `return streamText(...)`.
**How to avoid:** Audit write happens inside the stream callback AFTER the stream is complete, or is dispatched without awaiting using `c.executionCtx.waitUntil(appendAuditEntry(...))`. Cloudflare Workers provides `ctx.waitUntil()` specifically for this pattern — the Worker stays alive to complete background work after the response is sent.
**Warning signs:** Recruiter chat UI shows spinner for 1+ seconds before any text appears.

### Pitfall 4: Token in URL Leaks to Logs

**What goes wrong:** Shareable URL includes `?token=tok_abc123`. Cloudflare access logs, browser history, and referrer headers all capture query strings.
**Why it happens:** Tokens in query strings are a common convenience pattern that ignores log exposure.
**How to avoid:** For Phase 2, `?token=` in the query string is acceptable given the low-sensitivity use case (professional projection only). Document this limitation. For production hardening: use `Authorization: Bearer` header from the UI via fetch (not SSE EventSource, which can't set headers). The static HTML UI should use `fetch()` + `ReadableStream`, not `EventSource`, specifically to enable the Authorization header pattern.
**Warning signs:** Token appears in Cloudflare request log URL column.

### Pitfall 5: Projection File Load Fails Silently

**What goes wrong:** A malformed `projections/*.json` file causes the projection loader to skip that projection. Requests using that projection name fail with 500.
**Why it happens:** Try/catch around individual file loads swallows the parse error.
**How to avoid:** Validate each projection file against a Zod schema on load. Log a clear error for any invalid file. Fail the Worker startup if a projection named in `TOKEN_MAP` cannot be loaded.
**Warning signs:** 500 errors on requests that reference a specific projection name but 200 on others.

### Pitfall 6: GitHub SHA Conflict on Concurrent Audit Writes

**What goes wrong:** Two simultaneous recruiter queries both read the current JSONL file SHA, both compute updated content, and the second `createOrUpdateFileContents` call fails with HTTP 409 (SHA mismatch).
**Why it happens:** The Contents API requires the current `sha` of the file for updates. If two writes race, the second will have a stale SHA.
**How to avoid:** Phase 2 volume makes this unlikely. Add `try/catch` around the audit write, log the 409 to `console.error()`, and continue. Never let audit failure throw to the user. For Phase 3+, consider using a dedicated audit collection in MongoDB instead.
**Warning signs:** `422 Unprocessable Entity` or `409 Conflict` in Worker stderr logs.

---

## Code Examples

### MongoDB Connection Pattern for Workers

```typescript
// chatbot-worker/src/lib/db.ts
// Source: https://alexbevi.com/blog/2025/03/25/cloudflare-workers-and-mongodb/

import { MongoClient } from 'mongodb';

let client: MongoClient | null = null;

export async function getDb(mongoUri: string) {
  if (!client) {
    client = new MongoClient(mongoUri, {
      maxPoolSize: 1,
      minPoolSize: 0,
      serverSelectionTimeoutMS: 5000,
    });
  }
  // Re-connect if connection was dropped (M0 idle timeout)
  try {
    await client.db('admin').command({ ping: 1 });
  } catch {
    client = null;
    client = new MongoClient(mongoUri, {
      maxPoolSize: 1,
      minPoolSize: 0,
      serverSelectionTimeoutMS: 5000,
    });
  }
  await client.connect();
  return client.db('breakfast-club');
}
```

### Cloudflare Worker Environment Type

```typescript
// chatbot-worker/src/types.ts
export interface Env {
  MONGODB_URI: string;
  OPENAI_API_KEY: string;
  GITHUB_TOKEN: string;
  GITHUB_OWNER: string;
  GITHUB_PRIVATE_REPO: string;
  TOKEN_MAP: string;  // JSON string: {"tok_xxx": "professional"}
}
```

### Auth Middleware Pattern

```typescript
// chatbot-worker/src/middleware/auth.ts
import { createMiddleware } from 'hono/factory';
import type { Env } from '../types.js';

export const authMiddleware = createMiddleware<{ Bindings: Env }>(async (c, next) => {
  const token = c.req.header('Authorization')?.replace('Bearer ', '')
    ?? new URL(c.req.url).searchParams.get('token')
    ?? null;

  const tokenMap: Record<string, string> = JSON.parse(c.env.TOKEN_MAP);
  const projectionName = token ? tokenMap[token] : 'public';

  if (token && !projectionName) {
    return c.json({ error: 'Invalid token' }, 401);
  }

  // Never default to 'owner' or 'personal' — locked decision
  c.set('projectionName', projectionName ?? 'public');
  await next();
});
```

### Recruiter UI — Fetch-Based SSE (not EventSource)

Using `fetch()` with `ReadableStream` instead of `EventSource` enables the Authorization header pattern and works in all modern browsers.

```html
<!-- chatbot-worker/public/index.html — key JS excerpt -->
<script>
async function sendMessage(message) {
  const token = new URLSearchParams(window.location.search).get('token') ?? '';
  const response = await fetch('/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ message, history }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    renderChunk(buffer);
  }
}
</script>
```

### wrangler.toml Template

```toml
name = "breakfast-club-chatbot"
main = "src/index.ts"
compatibility_date = "2025-03-20"
compatibility_flags = ["nodejs_compat_v2"]

[assets]
directory = "./public"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| MongoDB + Cloudflare Workers not possible | Works via `nodejs_compat_v2` flag | March 2025 | Can use existing MongoDB Atlas M0 from Worker — no separate data store needed |
| Cloudflare Workers free = 10ms CPU only | CPU limit is for CPU time only; network await does not count | Always true, often misunderstood | OpenAI streaming calls are feasible on free tier |
| EventSource for streaming (can't set headers) | `fetch()` + `ReadableStream` for full header control | Browser standard matured | Use fetch-streaming pattern for auth header support |
| Fine-grained PATs beta | Fine-grained PATs GA (March 2025) | March 2025 | Can use fine-grained PAT scoped to Contents:Read+Write on private repo for audit writes |

**Deprecated/outdated:**
- `nodejs_compat` (older flag): Superseded by `nodejs_compat_v2` for full Node.js module compatibility including `net` and `tls`
- Vercel-first approach for Workers-adjacent workloads: Cloudflare Workers is now the better zero-cost choice for Node.js + MongoDB use cases

---

## Open Questions

1. **Token format: opaque string vs signed JWT**
   - What we know: Opaque tokens are simpler, trivially revocable by removing from TOKEN_MAP, no signing key to manage. JWTs are stateless (no lookup needed), portable, self-expiring.
   - What's unclear: Whether the owner wants tokens to auto-expire (TTL) or be manually revoked.
   - Recommendation: **Use opaque tokens for Phase 2.** Store as `TOKEN_MAP` JSON secret in Cloudflare env. Revocation = remove entry and update secret. TTL can be added in Phase 2 by encoding expiry in the map value: `{"tok_xxx": {"projection": "professional", "expires": "2026-12-31"}}`. JWTs are appropriate if tokens must be distributed without server state (multi-worker scenario) — not the Phase 2 case.

2. **Audit trail: query plaintext vs query hash**
   - What we know: RCTR-05 requires every recruiter query be logged. Storing plaintext queries in GitHub (a repo the owner controls) is reasonable but makes the audit log itself sensitive.
   - What's unclear: Owner's preference for log verbosity vs privacy.
   - Recommendation: Log `query_preview` (first 80 chars) + `sha256(full_query)`. Owner can verify a specific query by hashing it. Avoids storing full sensitive text in a repo that may be inspected.

3. **gpt-4o-mini vs gpt-4o for chatbot**
   - What we know: `gpt-4o-mini` is 15x cheaper per token. For a recruiter chatbot with structured identity context, it is likely sufficient. `gpt-4o` gives better synthesis quality for complex reasoning.
   - Recommendation: Use `gpt-4o-mini` for Phase 2. Owner can change the model name in one env var if quality is insufficient.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Build + local dev | Yes | 22.22.0 | — |
| npm | Package management | Yes | 10.9.4 | — |
| wrangler CLI | Cloudflare Workers deploy | No | — | `npm install -g wrangler` — trivial install |
| MongoDB Atlas M0 | Identity data store | Yes (Phase 1 provisioned) | — | — |
| OpenAI API key | Chat completions | Yes (Phase 1 provisioned, openai in deps) | — | — |
| GitHub fine-grained PAT | Audit trail writes | Not yet created | — | Create during Phase 2 plan 02-05; needs Contents:Read+Write on private repo |
| Cloudflare account (free) | Worker deployment | Unknown — not verified | — | Sign up at cloudflare.com — free, no credit card |

**Missing dependencies with no fallback:**
- Cloudflare account (may not exist yet) — verify before executing Plan 02-03

**Missing dependencies with trivial setup:**
- wrangler CLI (`npm install -g wrangler`)
- GitHub fine-grained PAT for audit writes (create in GitHub settings)

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None detected — no test runner configured in Phase 1 |
| Config file | None — Wave 0 gap |
| Quick run command | TBD — pending Wave 0 test setup |
| Full suite command | TBD |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROJ-01 | `applyProjection()` returns only allowlisted fields | unit | `tsx --test src/projection/apply-projection.test.ts` | ❌ Wave 0 |
| PROJ-02 | Three built-in projection files load and validate | unit | `tsx --test scripts/validate-projections.test.ts` | ❌ Wave 0 |
| PROJ-03 | MCP tool handlers filter output through applyProjection | unit | test tool handlers with mock projection | ❌ Wave 0 |
| PROJ-04 | Custom projection JSON in projections/ loads without code change | integration | `tsx --test src/projection/load-projections.test.ts` | ❌ Wave 0 |
| PROJ-05 | Token tied to projection can only access that projection | unit | auth middleware test | ❌ Wave 0 |
| RCTR-01 | Scoped token endpoint returns only professional projection | integration | `curl` smoke test against Worker | manual |
| RCTR-02 | Chatbot refuses salary/personal queries | manual | Pre-scripted prompt test in Plan 02-05 | manual |
| RCTR-03 | Natural language questions return grounded answers | manual | Demo narrative in Plan 02-05 | manual |
| RCTR-04 | Static HTML UI works in browser without setup | manual | Browser smoke test | manual |
| RCTR-05 | Audit JSONL entry written after each query | integration | Worker test with mock GitHub | ❌ Wave 0 |

### Node.js Built-in Test Runner

Node.js 22 ships a built-in test runner (`node:test`) that requires no external install. Use it for unit tests in this project rather than pulling in Jest or Vitest, which add complexity and don't work inside Cloudflare Workers ESM context.

```bash
# Run a single test file
node --test src/projection/apply-projection.test.ts
# or via tsx for TypeScript
tsx --test src/projection/apply-projection.test.ts
```

### Wave 0 Gaps
- [ ] `src/projection/apply-projection.test.ts` — covers PROJ-01, PROJ-03
- [ ] `src/projection/load-projections.test.ts` — covers PROJ-02, PROJ-04
- [ ] `chatbot-worker/src/middleware/auth.test.ts` — covers PROJ-05
- [ ] `chatbot-worker/src/lib/audit.test.ts` — covers RCTR-05 (with mock Octokit)

---

## Project Constraints (from CLAUDE.md)

- Primary language targets: Swift/SwiftUI (iOS), **Python (ML/backend)** — Note: this project is Node.js/TypeScript; CLAUDE.md is workspace-level and this project predates it; the project-level language choice (Node.js/TypeScript ESM) from STATE.md takes precedence.
- Git is available; Homebrew at `/opt/homebrew/bin/brew`
- No permission prompts — work autonomously and completely
- Flag blockers immediately; log decisions clearly

---

## Sources

### Primary (HIGH confidence)
- [Cloudflare Workers Limits](https://developers.cloudflare.com/workers/platform/limits/) — CPU time vs wall time distinction, free tier 100k/day request limit
- [Hono Cloudflare Workers docs](https://hono.dev/docs/getting-started/cloudflare-workers) — routing, env var access pattern, streaming
- [Hono Streaming Helper](https://hono.dev/docs/helpers/streaming) — `streamText()` SSE pattern
- [MongoDB + Cloudflare Workers (March 2025)](https://alexbevi.com/blog/2025/03/25/cloudflare-workers-and-mongodb/) — `nodejs_compat_v2` flag, MongoClient config for Workers

### Secondary (MEDIUM confidence)
- [Fine-grained PATs GA (March 2025)](https://github.blog/changelog/2025-03-18-fine-grained-pats-are-now-generally-available/) — PAT capabilities for private repo Contents write
- Phase 1 SUMMARY files and source code — confirmed existing types, tool patterns, MongoDB schema, sensitivity tier system

### Tertiary (LOW confidence)
- WebSearch results on opaque token vs JWT tradeoffs — multiple consistent sources; standard knowledge

---

## Metadata

**Confidence breakdown:**
- Projection engine design: HIGH — builds directly on Phase 1 types and patterns; logic is deterministic
- Infrastructure (Cloudflare Workers + Hono): HIGH — verified via official docs and confirmed 2025 MongoDB compat
- Token format (opaque): MEDIUM — recommendation is clear but the "opaque vs JWT" decision is flagged as open in STATE.md; planner should confirm with owner before committing
- Audit trail (GitHub Contents API): HIGH — well-documented Octokit pattern; race condition acknowledged and mitigated
- Streaming UI: HIGH — fetch + ReadableStream is a browser standard; EventSource limitation for headers is well-known

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (Cloudflare/Hono stable; MongoDB compat flag recent but stable)
