# Risk Register: Breakfast Club

**Project:** Breakfast Club — self-sovereign AI identity system
**Researched:** 2026-03-26
**Overall confidence:** HIGH (infrastructure limits from official docs), MEDIUM (adoption and demo-day risks from patterns)

---

## How to Read This Document

Each risk has:
- **Likelihood:** LOW / MEDIUM / HIGH — probability of occurring without mitigation
- **Impact:** LOW / MEDIUM / HIGH — severity if it occurs
- **Risk level:** Composite (likelihood x impact)
- **Mitigation:** Concrete actions to reduce likelihood or impact

---

## Risk Area 1: Free Tier Sustainability

### 1.1 MongoDB Atlas M0 Storage Exhaustion

**Likelihood:** LOW (single user) / MEDIUM (multi-user open source adoption)
**Impact:** HIGH — writes fail completely when the 512 MB cap is hit; no graceful degradation
**Risk level:** LOW for personal use, MEDIUM for growth scenario

**What breaks first:** Storage. At 512 MB total (including indexes), the primary constraint is not identity JSON (which is kilobytes) but conversation memory embeddings. A text-embedding-3-small vector is 1536 float32 values = 6 KB per chunk. At 512 MB and assuming ~100 KB overhead for indexes and metadata, you can store roughly 85,000 memory chunks before hitting the wall. A moderately active user running 10 conversations/day with 20 chunks/conversation hits this in about 425 days.

**What the failure looks like:** MongoDB write operations start failing with `WriteError: exceeded storage limit`. The sync Action will fail. The MCP server will still read stale data but writes stop. No alert fires unless you build one.

**Mitigations:**
1. Add a storage monitor step to the sync Action that queries Atlas cluster stats and writes a warning to the public transparency repo if usage exceeds 80% (410 MB). This gives early warning before failure.
2. Implement a TTL index on conversation memory: `db.memories.createIndex({ created_at: 1 }, { expireAfterSeconds: 7776000 })` — 90-day rolling window, configurable. Identity documents are small and permanent; memories are the growth vector.
3. Document the upgrade path clearly in the template README: M10 dedicated is ~$57/month but eliminates the storage and connection limits. For a serious user, this is affordable. M0 is explicitly for development and personal use — MongoDB's own documentation states this directly.
4. For the open-source distribution, build storage usage reporting into the sync script so users see their consumption before they hit the wall.

**Sources:** [MongoDB Atlas M0 limits (community confirmed)](https://www.mongodb.com/community/forums/t/mongodb-m0-cluster-limits-clarifications/124122), [Atlas Free Cluster Limits (official)](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/)

---

### 1.2 MongoDB Atlas M0 Connection Limit

**Likelihood:** LOW (single user with one MCP server process)
**Impact:** MEDIUM — new connections are refused; existing ones continue
**Risk level:** LOW

**What breaks:** The M0 free cluster allows 500 concurrent connections maximum (confirmed by MongoDB community moderators — some third-party sources incorrectly state 100). The MongoDB Node.js driver uses a connection pool. With `maxPoolSize: 5` as recommended in STACK.md, a single MCP server process uses at most 5 connections. Even with 10 concurrent Claude sessions running simultaneously, that is 50 connections — well within limits.

**The realistic scenario where this bites:** If users of the open-source template all point at a shared MongoDB Atlas cluster (unlikely by design, since each user forks their own), or if someone misconfigures `maxPoolSize` to a large value.

**Mitigations:**
1. Enforce `maxPoolSize: 5` in the template MCP server code. Document why in comments.
2. Keep `minPoolSize: 1` to avoid reconnect overhead without holding unnecessary connections.
3. Do not share a single Atlas M0 cluster across multiple users — the template must provision one cluster per user. This is already the correct design (each fork = one user = one cluster).

---

### 1.3 MongoDB Atlas M0 Vector Index Limit

**Likelihood:** MEDIUM — this is easy to hit if you create indexes iteratively
**Impact:** MEDIUM — cannot create a second vector index; existing queries continue
**Risk level:** MEDIUM

**What breaks:** M0 free clusters allow exactly one vector search index. This is a hard limit. If you create a vector index for identity embeddings and then try to create another for conversation memory, the second creation silently fails or returns an error.

**Design implication:** The single vector index must cover all vector search use cases. This is achievable: use one index on the `embedding` field and filter by `collection_type` field to differentiate identity vs memory queries. Alternatively, store identity and memory in the same collection with a `doc_type` discriminator field.

**Mitigations:**
1. Design the data schema from day one to use a single unified `embedding` field across all document types (identity chunks, memory chunks, etc.).
2. Use pre-filters on `$vectorSearch` with the `filter` parameter to scope queries by document type.
3. Create the vector index via the Atlas UI or driver `createSearchIndex()` during initial setup — include this as a required step in the template's setup instructions.
4. Document in the README: "Do not create a second vector search index — M0 supports only one. The setup script creates this for you."

**Source:** [MongoDB community confirmed one vector index on M0](https://www.mongodb.com/community/forums/t/is-vector-search-feature-paid-or-free/267191)

---

### 1.4 GitHub Actions Minute Exhaustion

**Likelihood:** LOW for personal use
**Impact:** MEDIUM — sync stops until the monthly cycle resets; data goes stale
**Risk level:** LOW

**Budget reality:** GitHub Free gives 2,000 minutes/month for private repository Actions. A typical sync workflow (checkout + npm ci + sync script) runs in 60–90 seconds. At 2 minutes per run, you get 1,000 runs/month, or ~33 runs/day. A developer committing to their identity repo multiple times per day will stay well within this. Even at 10 pushes/day with 2-minute runs, that is 600 minutes/month — 30% of the free budget.

**The scenario where this bites:** If you add large npm installs to every sync run without caching, or if you add expensive steps (LLM embedding generation in the Action rather than locally). An uncached `npm ci` with OpenAI SDK and MongoDB driver takes 45–90 seconds. Cached, it takes 5–10 seconds.

**2026 pricing note:** As of January 1, 2026, GitHub added a $0.002/minute platform charge on top of minute consumption for paid overages. Free tier usage is unaffected — the 2,000 minutes remain genuinely free.

**Mitigations:**
1. Add `actions/cache@v4` for `node_modules` in the sync workflow — saves 60–80 seconds per run.
2. Use `paths:` filtering in the workflow trigger (already recommended in STACK.md) so the sync only runs when identity files actually change.
3. Offload embedding generation to the local machine or a dedicated script run by the user — not in the Action. The Action syncs data; embedding happens as a pre-commit hook or separate CLI command.
4. Monitor minutes via GitHub Settings → Billing and usage to catch unexpected consumption early.

---

### 1.5 GitHub API Rate Limit

**Likelihood:** LOW for single-user personal use
**Impact:** MEDIUM — sync workflow fails mid-run
**Risk level:** LOW

**Reality:** A GitHub App installation token provides 5,000–12,500 requests/hour. A sync run reading one identity file and writing one attestation file uses approximately 10 API calls. At that rate, you would need 500+ sync runs per hour to hit the limit. This is not a realistic personal use concern.

**The scenario where this bites:** Open-source adoption at scale, where many users share one GitHub App installation (they should not), or where the sync script iterates over files with individual API calls instead of batching.

**Mitigations:**
1. Use the Git Trees API (`/git/trees/{sha}?recursive=1`) to fetch the full file tree in one call rather than per-file `getContent` calls.
2. Each forked user repository has its own rate limit budget — the open-source design naturally distributes this.

---

## Risk Area 2: Template Repo Adoption

### 2.1 Setup Complexity Exceeds 30-Minute Promise

**Likelihood:** HIGH without careful UX design
**Impact:** HIGH — most open-source tools die here; users abandon before they see value
**Risk level:** HIGH

**What goes wrong:** Template repos that require multi-step account creation, API key acquisition, secret configuration, and schema population before anything works have extremely high abandonment rates. The specific failure points for Breakfast Club are:

1. **MongoDB Atlas account creation** — requires email verification, credit card for account (even free tier asks for it in some regions), cluster provisioning takes 3–5 minutes
2. **GitHub App setup** — App ID, private key PEM generation, installation on two repos — this is developer-hostile for non-platform engineers
3. **MONGODB_URI secret** — users copy the wrong connection string format (`mongodb://` vs `mongodb+srv://`), use wrong username/password encoding, or forget to whitelist their IP
4. **Identity JSON population** — blank schema is daunting; users do not know what is required vs optional
5. **Vector index creation** — Atlas UI is not obvious for first-time users; the CLI equivalent may fail on M0

**Evidence from adjacent tools:** The Anthropic Claude Code credential setup has documented failure modes where users "paste the wrong token" and the system appears to work but is broken. Developer tools targeting non-platform engineers (recruiters forking this) have compounded friction — each additional required step loses a significant fraction of users.

**Mitigations:**
1. **Provide a setup script**, not a README walk-through. A `scripts/setup.sh` that runs `mongosh` commands to create the database, creates the vector index, validates the connection string, and prints a success message reduces copy-paste errors dramatically.
2. **Validate before proceeding.** Each step of setup should print clear success/failure. "Connected to MongoDB: OK" before moving to the next step.
3. **Pre-populate the identity JSON with the template author's own data (anonymised) and clear `# TODO` comments.** An example that works is more instructive than a blank schema. Seeing the MCP server respond with real data immediately after `npm start` is the moment users commit to the tool.
4. **Use PAT instead of GitHub App for the initial MVP template.** A PAT requires one step: generate a fine-grained token with `Contents: Read`. GitHub Apps require App creation, key generation, installation on two repos. For the first 100 users, PAT friction is acceptable — upgrade the architecture later.
5. **Record a 5-minute setup video.** Written instructions have ambiguity that video removes. This is particularly important for the MongoDB Atlas UI steps.
6. **Provide a `make check` or `npm run verify` command** that validates all secrets are set, MongoDB is reachable, and the MCP server starts without errors.

---

### 2.2 The "Works on My Machine" Problem

**Likelihood:** MEDIUM
**Impact:** MEDIUM — reduces adoption, increases support burden
**Risk level:** MEDIUM

**What goes wrong:** Node.js version mismatches, platform-specific path handling (Windows vs macOS vs Linux), and environment variable loading differences cause the MCP server or sync script to work for the author but fail for adopters.

**Specific failure modes:**
- MCP SDK requires Node 16+; Claude Desktop ships its own Node runtime on some platforms
- `"type": "module"` in package.json breaks `require()` calls in older patterns
- Windows users face path separator issues in file glob patterns
- `.env` file loading differences between `dotenv`, `tsx --env-file`, and environment-injected secrets

**Mitigations:**
1. Pin `"engines": { "node": ">=18.0.0" }` in package.json and enforce it.
2. Test the template on macOS, Linux, and Windows before publishing — GitHub Actions provides all three runner types for free on public repos.
3. Use `tsx` for running TypeScript directly (already in STACK.md) — it handles ESM correctly without a build step.
4. Include a `npx envinfo` step in the `verify` command output to capture environment details when users report issues.

---

### 2.3 The "I Don't Know What to Put In" Problem

**Likelihood:** HIGH without good defaults
**Impact:** MEDIUM — users get it working but abandon before it delivers value
**Risk level:** MEDIUM

**What goes wrong:** A blank identity JSON schema with field descriptions is not enough. Users do not know how much detail is "enough" for the AI to be useful. They fill in a few fields, run the MCP server, ask Claude "what do you know about me?" and get a sparse response that does not feel valuable.

**Mitigations:**
1. Include a comprehensive example identity file (`identity/example.json`) that shows a fully populated schema with realistic data.
2. Include SKILL.md output generated from the example — let users see the end state before they start.
3. Add a `How much to fill in` section to the README that explains: "The minimum viable identity for AI usefulness is: headline (1 sentence), summary (2-3 sentences), skills.primary (3-5 items), and 2-3 experience entries."
4. Consider a CLI `breakfast-club init` command that asks questions interactively and generates the initial identity JSON.

---

## Risk Area 3: Privacy and Security

### 3.1 Accidental Repository Visibility Change (Private to Public)

**Likelihood:** LOW (but non-zero — GitHub UI makes this possible in Settings)
**Impact:** HIGH — personal data in commit history is permanently public once exposed
**Risk level:** MEDIUM

**What goes wrong:** GitHub's repository settings page allows visibility changes with a single confirmation dialog. If a user accidentally makes their private identity repo public, the current files are immediately exposed. More critically, if they revert it to private, **the data is not gone** — any actor who forked the repo, or any search engine that indexed the files during the public window, retains the data. GitHub's Cross Fork Object Reference (CFOR) vulnerability means commit data persists as long as any fork of the repository network exists.

**Specific data at risk:** email addresses, phone numbers, LinkedIn URLs, salary expectations, personal goals, and anything marked `private` in the sensitivity taxonomy.

**Mitigations:**
1. **Default `.gitignore` for sensitive fields.** Have a `secrets/` directory that is gitignored and document that truly sensitive fields (email, phone, salary) should live there or in GitHub Actions secrets — never in the committed identity JSON.
2. **Add a repo-settings lockdown script** in the template that uses the GitHub API to enforce branch protection and disable visibility changes via API. This cannot prevent all changes but adds friction.
3. **Documentation warning, prominently placed:** "Your private repo contains personal data. Never make it public. Review Settings > Danger Zone periodically."
4. **Sensitivity taxonomy enforcement:** Design the identity schema so `private` fields are in a clearly separate section. Make it obvious what should never be committed.
5. **Encrypt sensitive fields at rest** in the committed JSON using a key stored as a GitHub Actions secret. This is complex to implement but ensures that even if the repo goes public, the sensitive fields are ciphertext. For MVP, rely on field separation instead.

**Source:** [Truffle Security CFOR vulnerability research](https://trufflesecurity.com/blog/anyone-can-access-deleted-and-private-repo-data-github)

---

### 3.2 GitHub Actions Secret Exposure

**Likelihood:** MEDIUM — the attack surface is real and actively exploited
**Impact:** HIGH — MONGODB_URI, OpenAI API key, GitHub App private key all exposed
**Risk level:** HIGH

**What goes wrong:** Three distinct attack surfaces in the Actions pipeline:

**Surface A: Third-party action supply chain compromise.** In March 2025, the `tj-actions/changed-files` action was compromised and exposed CI/CD secrets in workflow logs across 23,000+ repositories. Secrets printed to logs become public in repos with public workflow logs. Breakfast Club's sync workflow uses `actions/checkout@v4`, `actions/setup-node@v4`, and `actions/create-github-app-token@v2` — all official GitHub-owned actions. The risk is lower for official actions but not zero.

**Surface B: Workflow injection.** If the sync workflow ever processes content from issue titles, PR bodies, or other user-controlled input and runs it in a shell context (using `${{ github.event.issue.title }}` in a `run:` step), an attacker can inject shell commands. For Breakfast Club's sync workflow (triggered only by owner pushes to main), this surface is minimal.

**Surface C: Log exposure.** GitHub Actions may log secret values if they appear in error output. MongoDB connection strings contain credentials. If the sync script throws an unhandled exception that includes the URI in its stack trace, the credentials appear in logs. For public repos, these logs are public.

**Mitigations:**
1. **Pin third-party actions to commit SHA, not version tags.** Use `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683` (the v4 commit SHA) rather than `actions/checkout@v4`. Tags are mutable; SHAs are not. Document this practice in the template workflow files.
2. **Wrap all MongoDB operations in error handlers** that catch exceptions and log a generic error message without including the URI. Use `console.error('MongoDB sync failed:', error.message)` not `console.error(error)` (which may include the full stack trace with the URI in it).
3. **Use GitHub's secret scanning.** Enable it on the private repo — it will alert if a known secret pattern (connection string, API key) appears in a commit.
4. **Principle of least privilege for secrets:** The MONGODB_URI secret should use a MongoDB Atlas database user with read+write on only the `breakfast-club` database — not an admin user.
5. **Rotate secrets on a schedule.** The GitHub App private key and MongoDB user password should be rotated periodically. Document this in the maintenance section of the README.

**Sources:** [Wiz tj-actions supply chain attack analysis](https://www.wiz.io/blog/github-action-tj-actions-changed-files-supply-chain-attack-cve-2025-30066), [GitHub Actions security best practices](https://docs.github.com/en/actions/reference/security/secure-use)

---

### 3.3 MongoDB Atlas Public Access

**Likelihood:** LOW if set up correctly; MEDIUM for non-expert users following quick-start guides
**Impact:** HIGH — database with personal identity data is internet-accessible with only username/password as protection
**Risk level:** MEDIUM

**What goes wrong:** MongoDB Atlas M0 clusters require network access configuration. The default for many quick-start guides recommends adding `0.0.0.0/0` (all IPs) to the IP access list to avoid connection errors. This means the database is reachable from anywhere on the internet, with only username/password protecting personal identity data.

GitHub Actions runners use dynamic IP addresses that change per run, which is why the quick-start `0.0.0.0/0` pattern exists for CI/CD. But for an always-running MCP server on a personal machine, a static IP or VPN exit IP could be whitelisted instead.

**Mitigations:**
1. **For the MCP server (personal machine):** Whitelist only your home/office static IP or IP range in Atlas. This eliminates the global attack surface.
2. **For GitHub Actions sync:** This genuinely requires open IP access (or Atlas Private Link, which requires paid tier). Acknowledge this in the README and compensate with a strong, unique database user password and least-privilege database user permissions.
3. **Create a dedicated Atlas database user** for the Actions sync with write access to only the identity collection — not cluster admin. Document this in setup instructions.
4. **Enable Atlas audit logs** (available on M0 for connection events) and review periodically.
5. **Do not use the Atlas admin user credentials in Actions.** Create a separate `sync-user` database user.

---

### 3.4 Projection Bypass / Data Leakage via MCP Tool

**Likelihood:** LOW (requires MCP client compromise or server coding error)
**Impact:** HIGH — private identity fields exposed to recruiters or third parties
**Risk level:** MEDIUM

**What goes wrong:** The projection system is server-side enforcement in the MCP tool handler. If the tool handler has a bug — such as accidentally returning the full identity document before applying the projection filter, or a JSON serialization issue that includes extra fields — private data leaks to callers.

Separately: if the MCP client (Claude Desktop) were compromised or a malicious MCP server were installed alongside the legitimate one, it could attempt to call tools with elevated scope parameters.

**Mitigations:**
1. **Test projections explicitly.** Write unit tests for `applyProjection()` that assert that private fields are NOT present in the output for recruiter and public projections. This is the most important mitigation.
2. **Use a whitelist, not a blacklist.** As documented in FEATURES.md, whitelist-based projection (`allow_fields: [...]`) is measurably safer than blacklisting. A blacklist can always miss a newly added field.
3. **Log projection application.** In the MCP server, log (to stderr) which projection was applied and how many fields were included vs excluded. This creates an audit trail.
4. **Treat the recruiter projection token as sensitive.** It should be a short-lived signed JWT, not a plain string, and should be included in the transparency log when issued.
5. **Never return raw database documents from MCP tools.** Always pass identity data through `applyProjection()` before returning it, even for owner access (owner gets `projection_id: "owner"`, which includes `allow_fields: ["*"]`, but still passes through the projection function for audit consistency).

---

### 3.5 Transparency Repo Attestation Tampering

**Likelihood:** LOW (requires write access to public repo)
**Impact:** MEDIUM — undermines the verification model's integrity claim
**Risk level:** LOW

**What goes wrong:** The public transparency repo is the verification anchor. If an attacker gains write access (via a compromised GitHub App private key or a stolen PAT), they could rewrite attestation history. The hash chain design catches this for any verifier who checks the chain, but most users will not run the verification algorithm themselves — they will trust the dashboard.

**Mitigations:**
1. **Enable branch protection on the public repo's main branch.** Require that only the GitHub App can push — not humans, not other tokens. This prevents direct push attacks.
2. **The hash chain's self-healing property is a mitigation:** Any tampered entry breaks the chain validation in the dashboard. The dashboard should display a prominent "CHAIN INVALID" state — not just a missing green checkmark.
3. **Keep the GitHub App private key rotated and stored only as a GitHub Actions secret** in the private repo. It should never appear in code or in the public repo.

---

## Risk Area 4: MCP Ecosystem

### 4.1 MCP Spec Breaking Changes

**Likelihood:** MEDIUM — the spec has broken things before (HTTP+SSE replaced in March 2025)
**Impact:** MEDIUM — MCP server stops working until updated; users on old Claude Desktop cannot use it
**Risk level:** MEDIUM

**What the history shows:** The March 2025 MCP specification made the following breaking changes from the November 2024 spec:
- Replaced HTTP+SSE transport with Streamable HTTP transport (old transport deprecated)
- Added OAuth 2.1 authorization framework (new requirement for remote servers)

For Breakfast Club's stdio transport specifically, these changes had no impact — stdio is stable and unchanged across all spec versions. The risk is primarily for any future HTTP/remote deployment.

**The 2026 roadmap** (per official MCP blog) is organized around transport evolution and enterprise readiness. The core protocol stability is improving as the project matures from experimental to production deployments. Breaking changes are becoming less frequent as the spec stabilizes.

**Mitigations:**
1. **Use stdio transport for the MCP server** (already recommended in STACK.md). Stdio is the most stable transport — it has not changed across any spec version and is unlikely to change.
2. **Pin the MCP SDK version** (`@modelcontextprotocol/sdk@1.27.1`) and test before upgrading. Do not use `^` (caret) in package.json for the SDK — use an exact version.
3. **Monitor the MCP changelog** at `modelcontextprotocol.io/specification` and the MCP blog. Breaking changes are announced with advance notice.
4. **The spec is date-versioned** (e.g., `2025-03-26`). Your server's protocol version is negotiated during the `initialize` handshake — clients and servers that support different spec versions can negotiate backwards compatibility. This is built into the protocol.

**Source:** [MCP Changelog 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26/changelog), [MCP 2026 Roadmap](http://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/)

---

### 4.2 Claude Desktop Auto-Update Breaks MCP Configuration

**Likelihood:** MEDIUM — this has already happened in the wild (confirmed bug report)
**Impact:** MEDIUM — MCP server silently stops working after Claude Desktop update
**Risk level:** MEDIUM

**What goes wrong:** Claude Desktop introduced a new desktop extensions system alongside the legacy JSON config (`claude_desktop_config.json`). When Claude Desktop auto-updates to a version with the new extension system, it may install extension-based versions of configured servers that conflict with the manually-configured JSON entries. The result: both the old config-based server and the new extension-based server attempt to launch, causing conflicts. Tools appear enabled in the UI but are non-functional.

This is a documented real-world bug (GitHub issue #31864 in the claude-code repo, referenced in search results).

**Mitigations:**
1. **Document the specific claude_desktop_config.json entry** for Breakfast Club in the README and keep it updated after every Claude Desktop major release.
2. **Include a health-check tool in the MCP server** (`ping` or `status`) that returns the server version and MongoDB connection status. Users can call this to verify the server is actually responding.
3. **Subscribe to Claude Desktop release notes.** Breaking config changes are announced in release notes — set up a GitHub watch on the claude-code repo or follow the Anthropic changelog.
4. **Test the MCP server after every Claude Desktop update** — make this part of the personal workflow. A 30-second `status` tool call catches silent failures before a demo.

---

### 4.3 MCP Ecosystem Fragmentation (Multi-Client Support)

**Likelihood:** MEDIUM
**Impact:** LOW — Breakfast Club works for some clients but not others
**Risk level:** LOW

**What goes wrong:** MCP clients vary in how they implement the spec. Claude Desktop and Claude Code are the reference implementations. Cursor, Windsurf, and Copilot all have MCP support but with varying levels of completeness. Features like OAuth scopes (used by the projection system for access control) may not be implemented uniformly.

For the recruiter chatbot use case, this matters: if the recruiter's tool does not support OAuth scopes, the projection enforcement must fall back to a different mechanism (e.g., token in the tool call parameters rather than in the auth context).

**Mitigations:**
1. **Design the projection system with a fallback.** If no auth scope is present in the MCP context, default to the most restrictive projection (`public`). Never default to `owner` scope.
2. **The recruiter chatbot is not an MCP client scenario** — it is a web app that makes HTTP calls to a deployed MCP endpoint (or a standalone API that reads from MongoDB directly). For this use case, MCP client compatibility is not the concern.
3. **Test with Claude Desktop and Claude Code first.** These are the primary targets. Other client support is a bonus.

---

### 4.4 Anthropic Deprecates or Changes MCP

**Likelihood:** LOW — MCP is now multi-stakeholder (Linux Foundation governance model)
**Impact:** HIGH if it happens — the entire delivery mechanism is invalidated
**Risk level:** LOW

**What the evidence shows:** MCP was transferred to a multi-stakeholder governance model (with contributors from Google, Microsoft, OpenAI, Anthropic, and others). The 2026 roadmap emphasizes enterprise adoption and production stability. The protocol has reached sufficient adoption that Anthropic cannot unilaterally deprecate it without ecosystem consequences. The risk of complete abandonment is low.

**The residual risk** is that Anthropic could implement proprietary extensions to Claude's MCP support that the open standard does not have, creating a Claude-specific fast path that makes Breakfast Club less useful on other clients.

**Mitigations:**
1. No actionable mitigation needed for MVP — the risk is too low and the timeline too long to design around.
2. The architecture (private git repo + MongoDB) is not MCP-specific. If MCP were replaced by another protocol, the storage layer is unchanged. Only the server transport layer would need updating.

---

## Risk Area 5: Demo-Day Risks (James MacDonald Recruiter Demo)

### 5.1 MongoDB Atlas Connection Failure During Demo

**Likelihood:** LOW — Atlas is generally reliable
**Impact:** HIGH — chatbot cannot answer any questions
**Risk level:** MEDIUM

**What breaks:** If the MongoDB Atlas cluster is down, unreachable (IP whitelist issue), or the connection times out during the demo, the MCP server fails to retrieve the identity document. The chatbot either errors out or gives empty responses.

**Mitigations:**
1. **Run a full end-to-end test 24 hours before the demo**, not the morning of. This catches Atlas provisioning issues, expired tokens, and network problems.
2. **Add a `serverSelectionTimeoutMS: 10000` timeout** so failures are reported quickly rather than hanging indefinitely.
3. **Implement an in-memory fallback.** The MCP server can cache the identity document in memory on first successful load. If MongoDB becomes unreachable during a session, the in-memory cached version continues to serve requests. Add a startup pre-load that runs immediately at server start (not lazily on first tool call) to ensure the cache is warm.
4. **Whitelist the demo machine's IP in Atlas**, not `0.0.0.0/0`. Verify the IP is whitelisted the day before.
5. **Have a static fallback identity document.** If Atlas fails completely, the server can serve a pre-built JSON file on disk. This is not ideal but it means the demo proceeds.

---

### 5.2 Claude Desktop MCP Server Not Responding

**Likelihood:** MEDIUM — MCP server cold starts, config issues, and Claude Desktop updates are common failure modes
**Impact:** HIGH — the entire demo fails
**Risk level:** HIGH (highest priority pre-demo hardening)

**What breaks:** Claude Desktop may fail to start the MCP server subprocess, or the server may start but the tools are not visible in the Claude UI. This happens after Claude Desktop updates, after `node_modules` changes, or when the `claude_desktop_config.json` path is wrong.

**Mitigations:**
1. **Disable Claude Desktop auto-updates** the week before the demo (or at minimum, test immediately after any update).
2. **Add a visible `status` tool** that Claude can call: `breakfast-club-status`. It should return the server version, MongoDB connection state, identity document summary, and current projection. James (the recruiter) calling this tool confirms the whole stack is live.
3. **Test the exact config path** on the demo machine. The `claude_desktop_config.json` must reference the exact Node.js binary path and the exact absolute path to the built server file. Test with `node --version` from the exact path specified in config.
4. **Pre-build the TypeScript** before the demo. Do not rely on `tsx` JIT compilation during the demo — compile to JS with `tsc` and point the config at the compiled output. This eliminates any TypeScript compilation failure mode.
5. **Have a screenshot/screen recording** of a successful run as a fallback. This is not ideal but preserves the narrative if the live system fails.
6. **Test the demo flow the night before** in the same environment (same machine, same network, same Claude Desktop version) that will be used during the actual demo.

---

### 5.3 Recruiter Projection Reveals Wrong Data

**Likelihood:** LOW with correct projection setup
**Impact:** HIGH — private data (email, salary, personal opinions) shown to a recruiter
**Risk level:** MEDIUM

**What breaks:** A misconfigured `recruiter.json` projection that accidentally includes `allow_fields: ["*"]` or that fails to exclude private fields. Or a bug in `applyProjection()` that returns more fields than specified.

**Mitigations:**
1. **Manually verify the recruiter projection output** before the demo. Call the `query_professional_profile` tool and read the raw JSON response — confirm no private fields are present.
2. **Run a test with a separate Claude session** acting as the recruiter, using only the recruiter projection. Ask it for email, salary, and personal goals — confirm it refuses or states it doesn't have access.
3. **Sanitize the identity JSON of any data you would not want shown** in the recruiter view, even if it is in a "private" field — defence in depth means not relying solely on the projection filter.

---

### 5.4 Live Demo Hallucination or Incorrect Response

**Likelihood:** MEDIUM — LLMs hallucinate
**Impact:** MEDIUM — recruiter gets wrong information about your background
**Risk level:** MEDIUM

**What breaks:** Claude confidently states something about your experience that is slightly wrong — wrong dates, inflated scope, wrong technology name. The recruiter may fact-check.

**Mitigations:**
1. **Use concrete, unambiguous language in the identity JSON.** "Led a team of 6 engineers" not "led a team." "2020–present" not "several years."
2. **Ground the system prompt explicitly.** The recruiter chatbot system prompt should include: "Answer questions based only on the profile data below. If the profile does not contain the information requested, say so directly."
3. **Test the exact recruiter questions James MacDonald is likely to ask** (technology stack, years of experience, team leadership, availability) — run these against the chatbot before the demo and verify the answers.
4. **Prepare the profile data specifically for this recruiter's role.** If the role is iOS engineering, make sure the iOS experience section is detailed and prominent.

---

### 5.5 Network Reliability at Demo Location

**Likelihood:** MEDIUM — conference rooms, client offices, and co-working spaces have unreliable WiFi
**Impact:** HIGH — MongoDB Atlas, Claude API, and GitHub all require internet access
**Risk level:** MEDIUM

**What breaks:** The MCP server requires Atlas (internet). Claude Desktop requires the Anthropic API (internet). Without both, the demo fails entirely.

**Mitigations:**
1. **Have mobile hotspot ready** as a backup network. Test MongoDB Atlas reachability over the hotspot IP before the demo — if the hotspot IP is not whitelisted in Atlas, add it.
2. **Pre-warm the identity cache** before the demo starts (while on reliable network) so the MCP server has the identity document in memory and can serve basic queries even if Atlas becomes temporarily unreachable during the demo.
3. **Test the demo over mobile hotspot** at least once before demo day — some Atlas regions have connectivity issues with certain mobile carriers.
4. **If using Claude Desktop**, note that it requires the Anthropic API. There is no local-only fallback. This is a hard dependency on internet connectivity.

---

### 5.6 The Demo Scope Is Too Ambitious

**Likelihood:** HIGH if not explicitly scoped in advance
**Impact:** MEDIUM — demo is confusing or fails to deliver a clear message
**Risk level:** MEDIUM

**What goes wrong:** Trying to demonstrate identity, projection system, transparency attestation, MCP tool introspection, and conversation memory retrieval in a single recruiter demo is too much. The recruiter cares about one thing: "Tell me about this person's experience." The verification architecture is a trust mechanism for them but not the headline.

**Mitigations:**
1. **Narrow the demo to three interactions maximum:**
   - James asks about technical background → chatbot answers from identity
   - James asks about leadership experience → chatbot answers with evidence
   - James asks for email → chatbot declines gracefully (demonstrating privacy control)
2. **Prepare a one-sentence explanation of what they are seeing:** "This is a recruiter view of my professional profile — it answers questions about my work history and skills but protects my personal contact information until I choose to share it."
3. **Have a follow-up URL ready** (the transparency dashboard) that James can visit independently to verify the attestation chain. Do not demo this live — just mention it exists.

---

## Summary Risk Matrix

| Risk | Likelihood | Impact | Risk Level | Top Mitigation |
|------|-----------|--------|------------|----------------|
| 1.1 Storage exhaustion (M0) | L/M | HIGH | LOW/MED | TTL on memories + storage monitor in Action |
| 1.2 Connection limit (M0) | LOW | MED | LOW | maxPoolSize: 5 enforced in template |
| 1.3 Single vector index limit | MED | MED | MED | Design unified embedding field from day one |
| 1.4 Actions minute exhaustion | LOW | MED | LOW | Cache node_modules; use paths: filter |
| 1.5 GitHub API rate limit | LOW | MED | LOW | Git Trees API for batch reads |
| 2.1 Setup complexity > 30 min | HIGH | HIGH | HIGH | Setup script + validation command |
| 2.2 Platform/environment issues | MED | MED | MED | CI test on all platforms; pin Node version |
| 2.3 Identity JSON adoption | HIGH | MED | MED | Pre-populated example + init CLI |
| 3.1 Accidental repo visibility | LOW | HIGH | MED | Sensitive fields outside committed JSON |
| 3.2 Actions secret exposure | MED | HIGH | HIGH | Pin actions to SHA; sanitize error output |
| 3.3 MongoDB public access | MED | HIGH | MED | Whitelist IPs; dedicated sync user |
| 3.4 Projection bypass | LOW | HIGH | MED | Unit test projections; whitelist approach |
| 3.5 Attestation tampering | LOW | MED | LOW | Branch protection; hash chain validates |
| 4.1 MCP spec breaking changes | MED | MED | MED | stdio transport; exact SDK version pin |
| 4.2 Claude Desktop update breaks config | MED | MED | MED | Health-check tool; disable auto-update pre-demo |
| 4.3 MCP client fragmentation | MED | LOW | LOW | Default to most restrictive projection |
| 4.4 Anthropic deprecates MCP | LOW | HIGH | LOW | Storage layer is MCP-independent |
| 5.1 Atlas connection failure in demo | LOW | HIGH | MED | In-memory cache; pre-demo test |
| 5.2 MCP server not responding | MED | HIGH | HIGH | Pre-build TypeScript; status tool; test night before |
| 5.3 Projection reveals wrong data | LOW | HIGH | MED | Manual verify recruiter output before demo |
| 5.4 Hallucination in demo | MED | MED | MED | Concrete identity data; grounded system prompt |
| 5.5 Network failure in demo | MED | HIGH | MED | Mobile hotspot backup; pre-warm cache |
| 5.6 Demo scope too ambitious | HIGH | MED | MED | Three interactions max; pre-script the demo |

---

## Pre-Demo Hardening Checklist

These items must be done before the James MacDonald demo, in this order:

- [ ] Build TypeScript to JS (`tsc`) and verify the compiled output runs
- [ ] Verify `claude_desktop_config.json` points to the correct compiled file path
- [ ] Call `breakfast-club-status` tool in Claude Desktop — confirm MongoDB connection state is "connected"
- [ ] Call `query_professional_profile` as recruiter — manually read the JSON response and confirm no private fields
- [ ] Test all three demo interactions (background, leadership, email refusal) and verify the responses
- [ ] Whitelist demo machine IP and hotspot IP in MongoDB Atlas
- [ ] Disable Claude Desktop auto-updates
- [ ] Run the full demo flow on mobile hotspot to verify Atlas reachability
- [ ] Confirm the demo narrative is three interactions maximum
- [ ] Have screen recording of a successful run ready as fallback

---

## Sources

- [MongoDB Atlas M0 limits confirmed](https://www.mongodb.com/community/forums/t/mongodb-m0-cluster-limits-clarifications/124122)
- [MongoDB Atlas free cluster official limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/)
- [Vector search on M0 confirmed free](https://www.mongodb.com/community/forums/t/is-vector-search-feature-paid-or-free/267191)
- [GitHub Actions free tier billing](https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions)
- [GitHub Actions reference limits](https://docs.github.com/en/actions/reference/limits)
- [GitHub Actions 2026 pricing changes](https://resources.github.com/actions/2026-pricing-changes-for-github-actions/)
- [MCP spec changelog 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26/changelog)
- [MCP 2026 roadmap](http://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/)
- [Claude Desktop MCP extension conflict bug](https://github.com/anthropics/claude-code/issues/31864)
- [tj-actions supply chain attack (CVE-2025-30066)](https://www.wiz.io/blog/github-action-tj-actions-changed-files-supply-chain-attack-cve-2025-30066)
- [GitHub Actions security best practices](https://docs.github.com/en/actions/reference/security/secure-use)
- [GitHub CFOR vulnerability (deleted/private repo data)](https://trufflesecurity.com/blog/anyone-can-access-deleted-and-private-repo-data-github)
- [GitHub secrets in public repos — 39M leaked in 2024](https://github.blog/security/application-security/security-alert-expiring-github-personal-access-tokens/)
