# Feature Landscape: Breakfast Club

**Domain:** Self-sovereign AI identity system with MCP delivery and projection-based sharing
**Researched:** 2026-03-26
**Overall confidence:** HIGH (data models, MCP patterns, chunking), MEDIUM (identity schema fields, recruiter UX)

---

## 1. AI Identity Schema: Recommended Data Model

### Minimum Viable Identity Schema

No single standard exists yet for AI-consumable personal identity. The closest relevant prior art comes from three sources: JSON Resume (professional schema, MIT-licensed, widely adopted), Personal AI Infrastructure / PAI (open-source, identity-as-markdown files), and W3C Verifiable Credentials v2.0 (published May 15, 2025, for claims and attestations). Breakfast Club should synthesize from all three.

**Confidence:** MEDIUM. No authoritative cross-AI identity standard has shipped. W3C VC and DID standards exist for credential exchange but not for AI personalization context injection.

### Recommended Schema Sections

The identity document lives as structured JSON in the private GitHub repo. Fields are organized by disclosure sensitivity — a key design decision that enables the projection system.

```json
{
  "schema_version": "1.0",
  "id": "did:github:username",
  "display_name": "Full Name",

  "basics": {
    "headline": "Senior iOS Engineer",
    "summary": "2-3 sentence bio for AI context injection",
    "location": { "city": "Amsterdam", "country": "NL" },
    "email": "PRIVATE",
    "phone": "PRIVATE",
    "url": "https://example.com",
    "profiles": [
      { "network": "GitHub", "username": "username", "url": "https://github.com/username" },
      { "network": "LinkedIn", "url": "PRIVATE" }
    ]
  },

  "experience": [
    {
      "company": "Acme Corp",
      "title": "Staff Engineer",
      "start": "2020-01",
      "end": null,
      "summary": "Led platform team of 6 engineers...",
      "highlights": ["Shipped X", "Reduced Y by 30%"],
      "tech_stack": ["Swift", "Python", "Kubernetes"]
    }
  ],

  "education": [
    {
      "institution": "University of Amsterdam",
      "degree": "BSc Computer Science",
      "year": 2014
    }
  ],

  "skills": {
    "primary": ["Swift", "SwiftUI", "Python"],
    "secondary": ["TypeScript", "Kubernetes", "ML pipelines"],
    "learning": ["Rust", "formal verification"]
  },

  "values": {
    "work_style": "async-first, deep work blocks",
    "preferences": ["open source", "documentation-first", "boring tech"],
    "anti_patterns": ["meetings without agendas", "premature optimization"]
  },

  "personality": {
    "communication_style": "direct, concise",
    "humor": "dry",
    "interests": ["sailing", "applied ML", "urban cycling"]
  },

  "goals": {
    "short_term": ["Ship Breakfast Club MVP", "Speak at WWDC"],
    "long_term": ["Build developer tools company"]
  },

  "ai_preferences": {
    "response_style": "concise, no preamble",
    "preferred_formats": ["markdown", "code blocks"],
    "avoid": ["sycophancy", "over-hedging"],
    "context_injection_budget_tokens": 800
  },

  "conversation_memory": {
    "sources": ["claude", "chatgpt", "gemini"],
    "memory_collection": "breakfast_club_memories",
    "last_synced": "2026-03-25T14:00:00Z"
  },

  "meta": {
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-03-25T00:00:00Z",
    "visibility_default": "private"
  }
}
```

### Field Sensitivity Classification (Used by Projection System)

Every field must carry a sensitivity label. Recommended taxonomy:

| Sensitivity | Fields | Example Use |
|-------------|--------|-------------|
| `public` | display_name, headline, skills.primary, experience[].company, experience[].title | Recruiter chatbot, public profile |
| `professional` | summary, experience[].highlights, education, goals.short_term, values.work_style | Recruiter with explicit consent |
| `personal` | personality, values.anti_patterns, goals.long_term, ai_preferences | Owner's own AI assistants only |
| `private` | email, phone, profiles[].url (LinkedIn), salary expectations | Never in projections |

This classification lives in a `_sensitivity` sidecar map, not inline in the document, so projections can be enforced structurally rather than by field inspection logic in every tool.

### What the PAI Project Teaches Us

The Personal AI Infrastructure project (Daniel Miessler, open-source) uses 10 markdown files (MISSION.md, GOALS.md, BELIEFS.md, etc.) plus a three-tier memory system (hot/warm/cold). This works for personal AI enhancement but is too narrative-heavy for the recruiter projection use case, which needs structured queryable fields. Breakfast Club should use structured JSON as the canonical format and generate markdown projections from it — not the reverse.

### AGENTS.md / OpenAI Standard (2026)

AGENTS.md (originally Codex CLI, now stewarded by the Linux Foundation as an Agentic AI Foundation project) is an emerging universal AI config format. It is plain Markdown with no required schema. It has wide cross-tool support (Claude Code, Codex, Cursor, Continue, Aider, Windsurf, Gemini CLI). This is relevant for Breakfast Club's SKILL.md injection pattern — the system prompt injected into AI sessions should follow AGENTS.md conventions for maximum compatibility.

---

## 2. Projection / View System

### Design Pattern: Whitelist-First with Named Profiles

A "projection" is a named, reusable filter that produces a subset of the identity document. The system enforces projections at the MCP tool boundary — no caller can receive fields outside their granted projection.

**Recommended pattern: whitelist fields + depth controls, not blacklist.**

Whitelisting is measurably more secure than blacklisting. API security research shows whitelist validation reduces vulnerabilities by 66% vs blacklist approaches. For an identity system, the stakes justify this. Blacklists require you to enumerate everything sensitive in advance — an enumeration that will always be incomplete as the schema evolves.

### Projection Definition Format

Projections live as JSON files in the private repo alongside the identity document:

```json
// projections/recruiter.json
{
  "projection_id": "recruiter",
  "display_name": "Recruiter View",
  "description": "Professional profile for recruiter access",
  "created_at": "2026-03-01T00:00:00Z",
  "expires_at": null,
  "allow_fields": [
    "display_name",
    "basics.headline",
    "basics.location.city",
    "basics.location.country",
    "basics.url",
    "basics.profiles[network=GitHub]",
    "experience[].company",
    "experience[].title",
    "experience[].start",
    "experience[].end",
    "experience[].summary",
    "experience[].highlights",
    "experience[].tech_stack",
    "education[].institution",
    "education[].degree",
    "education[].year",
    "skills.primary",
    "skills.secondary",
    "values.work_style"
  ],
  "deny_fields": [],
  "allow_tools": ["query_professional_profile", "list_skills", "search_experience"],
  "rate_limit": { "requests_per_hour": 20 }
}
```

```json
// projections/owner.json
{
  "projection_id": "owner",
  "display_name": "Full Owner Access",
  "allow_fields": ["*"],
  "allow_tools": ["*"]
}
```

### MCP Enforcement Architecture

MCP's November 2025 specification introduces OAuth 2.1 with scope-based access control. The projection system maps to OAuth scopes:

```
identity:read:public      → public projection
identity:read:professional → recruiter projection
identity:read:personal     → owner projection
identity:write             → owner only
```

At the MCP tool handler level, enforcement works as follows:

```typescript
// Tool handler pseudocode
server.registerTool("query_professional_profile", ..., async (input, context) => {
  const projection = resolveProjection(context.auth.scope);
  const identity = await loadIdentity();
  const filtered = applyProjection(identity, projection);
  return formatForLLM(filtered);
});

function applyProjection(doc: IdentityDoc, projection: Projection): Partial<IdentityDoc> {
  if (projection.allow_fields.includes("*")) return doc;
  return pick(doc, projection.allow_fields); // deep pick, handles dotpath notation
}
```

Key property: **projection is enforced server-side in the MCP tool handler**. The MCP client (Claude Desktop, ChatGPT, etc.) never receives unapproved fields. There is no reliance on client-side filtering.

### Selective Disclosure Analogy

W3C Verifiable Credentials (v2.0, May 2025) uses BBS+ signatures for cryptographic selective disclosure — the holder proves they have a credential without revealing hidden fields, and proofs are unlinkable across verifications. Breakfast Club does not need this level of cryptographic rigor for MVP (the MCP server itself is the trust anchor, not a cryptographic proof), but the design should allow future migration to VC-based disclosure. Use field sensitivity labels now, reserve BBS+ for a future "verified identity" tier.

### Named Projection URLs

For the recruiter chatbot use case, projections should be addressable as shareable URLs with an access token:

```
https://breakfast-club.example.com/chatbot?projection=recruiter&token=abc123
```

The token grants the `identity:read:professional` MCP scope for the duration of the token's TTL. The recruiter never sees or touches the private GitHub repo.

---

## 3. Conversation Memory Chunking

### Storage Architecture

Conversation memory is the most complex data domain in Breakfast Club. The goal is cross-source retrieval — a user's interactions with Claude, ChatGPT, and Gemini should be searchable together. This requires a unified storage schema regardless of source.

**Recommended schema per memory chunk:**

```json
{
  "_id": "ObjectId",
  "owner_id": "did:github:username",
  "source": "claude | chatgpt | gemini | custom",
  "conversation_id": "source-native-id or UUID",
  "session_date": "2026-03-20",
  "chunk_index": 3,
  "role": "user | assistant | system",
  "content": "The actual text of the chunk...",
  "content_tokens": 412,
  "topics": ["swift", "performance", "instruments"],
  "entities": ["Xcode", "Instruments", "Time Profiler"],
  "embedding": [0.12, -0.34, ...],
  "chunk_type": "episodic | semantic | summary",
  "created_at": "ISODate",
  "source_metadata": {
    "model": "claude-sonnet-4-5",
    "conversation_title": "Debugging Swift performance"
  }
}
```

### Chunk Size Recommendation

Evidence from Weaviate, Pinecone, NVIDIA, and Milvus research converges on:

- **Baseline chunk size: 512 tokens** with 10-15% overlap (50-75 tokens)
- **For conversational turns**: chunk at semantic boundaries, not fixed size. A single assistant response that covers one topic = one chunk. Use recursive/semantic splitting, not naive fixed-size.
- **For session summaries**: one summary chunk per conversation session (~200 tokens), stored separately with `chunk_type: "summary"`
- **For long responses**: split at paragraph boundaries, maintain 10-15% overlap to preserve context across chunk edges

Chunk types to maintain:

| Type | Size | When Created | Purpose |
|------|------|--------------|---------|
| `turn` | 100-800 tokens | Per message | Raw episodic memory |
| `summary` | 150-300 tokens | Per session | Fast session recall |
| `semantic` | 200-600 tokens | Extracted facts | "User prefers X", "User works at Y" |
| `entity` | 50-100 tokens | Per extracted entity | Fast entity lookup |

The single Atlas M0 vector index covers the `embedding` field across all chunk types. Use the `chunk_type` field as a pre-filter on `$vectorSearch` to scope retrieval.

### Multi-Source Normalization

Each AI provider exports conversations differently:

| Source | Export Format | Key Challenge |
|--------|--------------|---------------|
| Claude | JSON (via claude.ai export) | Structured, well-formed |
| ChatGPT | JSON (via data export) | `conversations.json`, nested structure |
| Gemini | Google Takeout JSON | Multiple file format, activity-based |
| Custom | OpenAI-compatible chat format | Normalize to shared schema |

Normalization pipeline (GitHub Actions or local script):
1. Parse source-specific format
2. Extract turns (role, content, timestamp)
3. Apply semantic chunking (split long turns, preserve short turns)
4. Extract entities and topics via LLM call (cheap: use flash-tier model)
5. Generate embedding (text-embedding-3-small or equivalent)
6. Upsert to MongoDB with `source` field

### Retrieval Pattern

```typescript
// Hybrid retrieval: vector similarity + recency weighting
const results = await memories.aggregate([
  {
    $vectorSearch: {
      index: "memory_vector_index",
      path: "embedding",
      queryVector: queryEmbedding,
      numCandidates: 150,
      limit: 20,
      filter: { owner_id: "did:github:username" }
    }
  },
  {
    $addFields: {
      recency_score: {
        $divide: [1, { $add: [1, { $dateDiff: { startDate: "$session_date", endDate: "$$NOW", unit: "day" } }] }]
      },
      combined_score: { $add: [{ $multiply: ["$score", 0.7] }, { $multiply: ["$recency_score", 0.3] }] }
    }
  },
  { $sort: { combined_score: -1 } },
  { $limit: 5 }
]);
```

Recency weighting (30%) prevents old conversations from dominating. Adjust ratio based on query type — factual queries should weight semantic similarity higher, "what did I do recently" queries should weight recency higher.

---

## 4. SKILL.md / System Prompt Injection Patterns

### Format Recommendation: Markdown with XML Section Tags

Research finding: Markdown is 34-38% more token-efficient than JSON and ~10% more efficient than YAML for the same information. XML is 80% more verbose than Markdown. However, Claude specifically interprets XML tags well as reasoning delimiters. The optimal format for cross-model compatibility is **Markdown headings as primary structure + XML tags for logical sections the LLM needs to distinguish clearly**.

This is consistent with how AGENTS.md works in practice (plain Markdown, no required schema).

### Recommended SKILL.md / Identity Injection Format

The projection system generates this document on-demand from the identity JSON. It is injected into the system prompt when an AI session starts.

```markdown
<identity>
# Who I Am

**Name:** Kees
**Role:** Senior iOS/ML Engineer
**Location:** Amsterdam, NL
**Website:** https://example.com

## Summary

2-3 sentence bio optimized for AI context. Written in third person for AI consumption.
Focus on domain expertise and working style, not biography.

## Skills

**Primary:** Swift, SwiftUI, Python, ML pipelines
**Secondary:** TypeScript, Kubernetes, distributed systems
**Currently Learning:** Rust

## Work History

**Acme Corp** — Staff Engineer (2020–present)
Shipped X platform, reduced Y by 30%. Led team of 6.
Tech: Swift, Python, Kubernetes

**Previous Corp** — iOS Engineer (2017–2020)
Built consumer app with 2M users. Tech: Swift, Objective-C.

## Education

BSc Computer Science, University of Amsterdam (2014)

## Values & Working Style

- Async-first, deep work in AM
- Documentation before code
- Prefers boring, proven technology
- Direct communication, no preamble

## Current Goals

- Ship Breakfast Club MVP (Q2 2026)
- Contribute to MCP ecosystem

## AI Interaction Preferences

- Be concise, skip the preamble
- Use code blocks for code
- Flag uncertainty explicitly
- Don't ask "is there anything else I can help with"
</identity>
```

### Token Budget Guidelines

| Model | Context Window | Budget for Identity | Rationale |
|-------|---------------|--------------------|-|
| Claude Sonnet 4.6 | 1M tokens | 800-1200 tokens | Plenty of room; optimize for quality |
| GPT-4o | 128K tokens | 600-900 tokens | Leave room for conversation history |
| Gemini 1.5 Pro | 1M tokens | 800-1200 tokens | Same as Claude |
| GPT-4o-mini | 128K tokens | 400-600 tokens | Tighter budget, use compressed format |

The `ai_preferences.context_injection_budget_tokens` field in the identity schema lets the owner configure this per-model or globally.

### Projection-Aware Injection

The owner projection injects the full SKILL.md. The recruiter projection injects a stripped version with only `public` + `professional` fields. The system generates these from the same identity JSON — no manual maintenance of multiple files.

### Cross-Model Compatibility Notes

- **Claude**: Responds best to XML tags for logical sections. Markdown headings work. JSON in system prompt works but is verbose.
- **ChatGPT (GPT-4o)**: Responds well to Markdown. JSON also works but wastes tokens. Does not require XML tags.
- **Gemini**: Markdown is well-supported. XML tags are understood but not required.
- **Universal recommendation**: Markdown headings + XML `<identity>` wrapper tag. Works across all three with no model-specific branching.

---

## 5. Recruiter Use Case: Chatbot Scope and UX

### What Recruiters Actually Ask

Based on analysis of recruiter screening patterns in 2025, the recruiter chatbot needs to answer these question categories reliably:

**Role Fit**
- "What is their primary programming language?"
- "Have they worked in [industry]?"
- "Do they have experience with [technology]?"
- "What is their most recent role and company?"

**Experience Depth**
- "How many years of iOS development experience?"
- "Have they led a team? How large?"
- "Can you describe a major project they shipped?"
- "What was the scale of the systems they worked on?"

**Logistics**
- "Are they open to relocation?"
- "What is their current location?"
- "Are they open to contract/full-time/remote?"
- **NOTE:** Salary questions should be explicitly out of scope — identity owner controls this via projection.

**Culture/Values**
- "What is their preferred working style?"
- "Do they prefer startup vs enterprise?"

### Chatbot Scope Definition

The recruiter chatbot should be **tightly scoped by design**. This is not a general-purpose assistant — it is a professional profile query interface.

**In scope:**
- Answering questions about professional experience, skills, and education
- Summarizing the person's background
- Answering "have they done X" with evidence from experience fields
- Directing the recruiter to contact channels (if in the projection)

**Out of scope (explicitly refused by system prompt):**
- Personal information (location beyond city/country, contact info not in projection)
- Opinion questions ("what do they think about X company")
- Generating cover letters or modifying the presented identity
- Any field not in the recruiter projection

### System Prompt for Recruiter Chatbot

```markdown
<system>
You are a professional profile assistant for [Name]. You help recruiters and hiring
managers understand [Name]'s professional background.

You have access to [Name]'s professional profile through the Breakfast Club identity
system. The profile contains verified information about their experience, skills,
and professional background.

**Your capabilities:**
- Answer questions about [Name]'s work experience, skills, and education
- Summarize their background for specific roles
- Clarify details about specific projects or technologies

**Your limits:**
- You only have access to professional information. Do not speculate about
  personal details, opinions, or information not in the profile.
- If asked something outside your scope, say so clearly and suggest the recruiter
  reach out directly if needed.
- You represent [Name]'s professional record accurately. Do not embellish.
- Do not generate content [Name] hasn't authored (cover letters, reference letters).

The profile data is injected below. Answer questions based only on this data.
</system>

[recruiter projection SKILL.md injected here]
```

### UX Design Pattern: Scoped Chatbot with Clear Boundary Signaling

Good recruiter chatbot UX (based on 2025 recruitment chatbot research):

1. **Opening message states capabilities explicitly** — "I can tell you about [Name]'s experience in iOS development, their recent work history, and their technical skills. What would you like to know?"
2. **Boundary refusals are graceful** — "That's outside what I can share — you'd need to reach out to [Name] directly."
3. **Evidence-based answers** — cite the specific experience entry when answering skill questions ("In their role at Acme Corp from 2020–present, they...")
4. **Do not hallucinate** — if a question can't be answered from the profile data, say so ("The profile doesn't include information about that.")
5. **Session is stateless** — no memory of previous recruiter queries. Each session starts fresh.

### Recruiter Chatbot as MCP Tool vs Standalone App

Two implementation options:

| Option | How | Best For |
|--------|-----|---------|
| Shareable URL with embedded chatbot | Static GitHub Pages + API call to MCP server | Easy to share, no app install required |
| MCP server tool `query_profile` | Recruiter's AI assistant calls the tool | Recruiter already uses MCP-compatible tools |

**Recommended for MVP:** Shareable URL. The recruiter pastes a link into their browser and chats. Zero friction. The URL encodes the projection token, which grants `identity:read:professional` scope to that session.

---

## Table Stakes Features

Features expected by users of this system. Missing = product feels broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Full owner access via MCP | Core use case: AI knows who you are | Medium | stdio MCP server with owner projection |
| SKILL.md injection in system prompt | Primary AI personalization mechanism | Low | Generate from identity JSON on demand |
| GitHub repo as source of truth | Self-sovereign = I own the files | Low | Octokit reads, Actions syncs |
| Recruiter projection + shareable link | The killer use case for others | Medium | Projection system + token auth |
| Field-level sensitivity controls | Privacy is the whole point | Medium | Whitelist projection engine |
| Conversation memory storage | Cross-session continuity | High | MongoDB vector store + chunking pipeline |

## Differentiators

Features that make Breakfast Club distinct from general memory systems.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Projection system | Share tailored views without exposing private data | Medium | Named projection files, server-enforced |
| Cross-AI memory unification | Claude + ChatGPT + Gemini memories in one store | High | Source normalization pipeline |
| Git-backed identity versioning | Full history of your identity evolution | Low | It's just a git repo |
| SKILL.md auto-generation from structured data | No manual format maintenance | Low | Template rendering from JSON |
| Self-hostable, no vendor | True data sovereignty | Low | It's Node + GitHub + MongoDB free tier |

## Anti-Features

Features to explicitly not build, at least for MVP.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| AI that edits your identity | Loss of user control; trust violation | Only the owner edits identity files via git |
| Automatic PII detection and redaction | Complex, error-prone, creates false security | Use sensitivity labels in schema, enforce via projection |
| Public API with no auth | First-mover risk; PII exposure | All projections require signed tokens even for "public" views |
| Ingesting third-party data (LinkedIn scrape) | Legal risk, stale data | User manually maintains their identity files |
| Multi-user sharing of a single identity | Scope creep; trust model gets complex | One identity per repo per user, explicit projection grants |
| Vector search from recruiter chatbot | Overkill; recruiters ask structured questions | Simple field lookup from projection document |

## Feature Dependencies

```
Identity JSON schema
  → Projection engine (needs schema field taxonomy)
    → Recruiter chatbot (needs projection with fields defined)
    → SKILL.md generator (needs identity + projection)
      → System prompt injection (needs SKILL.md format)

MongoDB vector store
  → Conversation memory chunking (needs storage layer)
    → Cross-session retrieval (needs chunks + embeddings)

GitHub repo source of truth
  → GitHub Actions sync pipeline
    → MongoDB upsert (needs sync to be working)
    → Public manifest generation (needs sync to be working)
```

## MVP Recommendation

Prioritize:
1. Identity JSON schema + owner projection (MCP server reads and injects identity)
2. SKILL.md generator (system prompt injection, works immediately for personal use)
3. Recruiter projection + shareable link (the demonstrable external value)
4. Conversation memory ingestion for at least one source (Claude export)

Defer:
- Cross-AI memory unification (ChatGPT/Gemini ingestion): complex normalization, low MVP value
- BBS+ cryptographic selective disclosure: architectural future-proofing, not needed for single-user MVP
- Rate limiting on recruiter projection: needed before public launch, not for personal testing

---

## Sources

- JSON Resume schema — [jsonresume.org/schema](https://jsonresume.org/schema)
- Personal AI Infrastructure (PAI) — [github.com/danielmiessler/Personal_AI_Infrastructure](https://github.com/danielmiessler/Personal_AI_Infrastructure)
- W3C Verifiable Credentials v2.0 — [Recommendation, May 2025](https://www.w3.org/TR/vc-data-model-2.0/)
- Selective Disclosure (BBS+ signatures) — [dock.io/post/selective-disclosure](https://www.dock.io/post/selective-disclosure)
- MCP November 2025 Specification — [modelcontextprotocol.io/specification/2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25)
- MCP OAuth 2.1 Authorization — [auth0.com/blog/mcp-specs-update-all-about-auth/](https://auth0.com/blog/mcp-specs-update-all-about-auth/)
- Mem0 memory architecture (arxiv 2025) — [arxiv.org/abs/2504.19413](https://arxiv.org/abs/2504.19413)
- Weaviate chunking strategies — [weaviate.io/blog/chunking-strategies-for-rag](https://weaviate.io/blog/chunking-strategies-for-rag)
- AGENTS.md format guide — [deployhq.com/blog/ai-coding-config-files-guide](https://www.deployhq.com/blog/ai-coding-config-files-guide)
- Markdown vs XML vs JSON token efficiency — [wonderwhy-er.github.io/format-token-comparison/](https://wonderwhy-er.github.io/format-token-comparison/)
- AAIF / AGENTS.md Linux Foundation — [OpenAI AAIF announcement](https://openai.com/index/agentic-ai-foundation/)
- Recruiter chatbot UX patterns — [assesscandidates.com/ai-chatbots-for-recruitment/](https://www.assesscandidates.com/ai-chatbots-for-recruitment/)
- API security whitelisting effectiveness — [API Security Checklist 2026, Qodex.ai](https://qodex.ai/blog/api-security-checklist-every-developer-should-follow)
- Memoria multi-granularity chunking — [arxiv.org/html/2512.12686v1](https://arxiv.org/html/2512.12686v1)
