# Breakfast Club

**A personal operating system for your AI instances. Every Claude knows who you are. No manager. No hierarchy. Just shared context.**

You're running 4 Claude Code sessions across 3 projects. Each one starts cold — no idea who you are, what you've built, what you hate, how you work. You spend the first 10 messages getting it up to speed. Again.

Breakfast Club fixes that.

It's an MCP server that gives every Claude instance access to a shared identity store — your persona, your skills, your active projects, your values. Any Claude that connects to it already knows you. They share the same picture of who you are and what you're working on. No hierarchy, no manager Claude, no delegation — just peers with shared context.

---

## How it works

Your identity lives in MongoDB Atlas as a set of documents — one per section (persona, skills, projects, values). Each document is embedded with OpenAI's `text-embedding-3-small` for semantic search.

The MCP server exposes four tools:

| Tool | What it does |
|------|-------------|
| `identity_context` | Synthesized context blob for system prompt injection (~600–1200 tokens) |
| `identity_query` | Semantic search — "what databases does this person use?", "what are they building?" |
| `projects_list` | Active projects with status and stack |
| `verify_integrity` | Git tree SHA attestation — confirm the identity hasn't been tampered with |
| `breakfast_club_status` | Health check — MongoDB, projections, optional chatbot worker |

**Projections** control what different audiences see. Point a recruiter at the `professional` projection and they get skills and public projects. Point a collaborator at `personal` and they get everything. You define the boundaries.

---

## Setup

### 1. Prerequisites

- Node.js 18+
- MongoDB Atlas account (free tier works — you need Vector Search)
- OpenAI API key (for embeddings)

### 2. Install

```sh
git clone git@github.com:nickbeentjes/breakfast-club.git
cd breakfast-club
npm install
cp .env.example .env
# edit .env with your MongoDB URI and OpenAI key
```

### 3. Create your identity file

```sh
cp seed-data/example-identity.json seed-data/my-identity.json
# edit my-identity.json — fill in your actual persona, skills, projects, values
```

### 4. Create the MongoDB vector index

```sh
npm run build
node build/scripts/create-vector-index.js
```

Or create it manually in Atlas:
- Collection: `identity`
- Field: `embedding`
- Dimensions: `1536`
- Similarity: `cosine`
- Pre-filter on: `doc_type`

### 5. Seed your identity

```sh
npm run seed
# or dry-run first:
npm run seed:dry-run
```

### 6. Connect to Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "breakfast-club": {
      "command": "node",
      "args": ["/path/to/breakfast-club/build/index.js"],
      "env": {
        "MONGODB_URI": "your-uri",
        "MONGODB_DB_NAME": "breakfast-club",
        "OPENAI_API_KEY": "your-key"
      }
    }
  }
}
```

Restart Claude Desktop. You'll see the breakfast-club tools available.

### 7. Load context in any Claude session

Tell Claude to call `identity_context` at the start of a conversation — or add it to your system prompt instructions in `SKILL.md` / `CLAUDE.md`.

---

## Identity schema

Your identity is defined in a single JSON file with four top-level sections:

```json
{
  "persona":   { "_sensitivity": "personal",      ... },
  "skills":    { "_sensitivity": "professional",  ... },
  "projects":  { "_sensitivity": "professional",  ... },
  "values":    { "_sensitivity": "personal",      ... }
}
```

Each section has a `_sensitivity` level: `public`, `professional`, `personal`, or `private`. Projections use this to filter what gets returned for different audiences.

See `seed-data/example-identity.json` for a complete template.

---

## Projections

Three projections are included out of the box:

| Projection | What's visible |
|-----------|----------------|
| `personal` | Everything (default — for your own Claude sessions) |
| `professional` | Skills, public projects, professional persona |
| `public` | Public-only sections |

Add your own in `projections/` — each is a JSON file defining which sensitivity levels are allowed.

---

## The name

The Breakfast Club. A group of very different people who have nothing in common except that they're all in the same room together. No leader. No hierarchy. They share what they know, form their own picture of each other, and go from there.

That's the idea. Multiple AI instances — different models, different sessions, different personalities they've developed with you over time — all with access to the same shared context about who you are. Not because a manager told them. Because it's just there.

---

## License

MIT — build on it, fork it, corporatify it with enterprise security and eye-stabbing auth flows if that's your thing.
