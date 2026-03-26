import { describe, it, mock } from "node:test";
import assert from "node:assert/strict";
import { appendAuditEntry } from "./audit.js";
import type { Env } from "../types.js";

const mockEnv: Env = {
  MONGODB_URI: "mongodb://localhost:27017",
  OPENAI_API_KEY: "test-key",
  GITHUB_TOKEN: "test-token",
  GITHUB_OWNER: "test-owner",
  GITHUB_PRIVATE_REPO: "test-repo",
  TOKEN_MAP: "{}",
};

function makeOctokit(opts: {
  getContentResult?: unknown;
  getContentThrows?: boolean;
  createOrUpdateCalled?: boolean[];
  createOrUpdateArgs?: unknown[];
  createOrUpdateThrows?: boolean;
}) {
  const called: unknown[] = [];
  return {
    repos: {
      getContent: mock.fn(async () => {
        if (opts.getContentThrows) {
          throw Object.assign(new Error("Not Found"), { status: 404 });
        }
        return opts.getContentResult;
      }),
      createOrUpdateFileContents: mock.fn(async (...args: unknown[]) => {
        called.push(args[0]);
        if (opts.createOrUpdateThrows) {
          throw Object.assign(new Error("Conflict"), { status: 409 });
        }
        return { data: {} };
      }),
    },
    _called: called,
  };
}

// Minimal polyfill for atob/btoa — they exist in Workers but may not in tsx test runner
if (typeof globalThis.atob === "undefined") {
  Object.defineProperty(globalThis, "atob", {
    value: (s: string) => Buffer.from(s, "base64").toString("utf8"),
    writable: true,
  });
}
if (typeof globalThis.btoa === "undefined") {
  Object.defineProperty(globalThis, "btoa", {
    value: (s: string) => Buffer.from(s, "utf8").toString("base64"),
    writable: true,
  });
}

describe("appendAuditEntry", () => {
  it("creates a new file when the file does not exist (getContent throws 404)", async () => {
    const octokit = makeOctokit({ getContentThrows: true });

    // @ts-expect-error mock octokit doesn't implement full interface
    await appendAuditEntry("What is your availability?", "professional", mockEnv, octokit);

    assert.equal(octokit.repos.createOrUpdateFileContents.mock.calls.length, 1);
    const callArgs = octokit.repos.createOrUpdateFileContents.mock.calls[0].arguments[0] as Record<string, unknown>;
    // No sha should be passed when file doesn't exist
    assert.equal(callArgs.sha, undefined);
    assert.equal(callArgs.owner, "test-owner");
    assert.equal(callArgs.repo, "test-repo");
    assert.equal(callArgs.path, "audit/recruiter-queries.jsonl");
  });

  it("appends to existing file and passes current SHA", async () => {
    const existingContent = JSON.stringify({ timestamp: "2026-01-01T00:00:00.000Z", projection: "professional" }) + "\n";
    const encodedContent = btoa(existingContent);
    const octokit = makeOctokit({
      getContentResult: { data: { content: encodedContent, sha: "abc123sha" } },
    });

    // @ts-expect-error mock octokit doesn't implement full interface
    await appendAuditEntry("What stack do you use?", "professional", mockEnv, octokit);

    assert.equal(octokit.repos.createOrUpdateFileContents.mock.calls.length, 1);
    const callArgs = octokit.repos.createOrUpdateFileContents.mock.calls[0].arguments[0] as Record<string, unknown>;
    assert.equal(callArgs.sha, "abc123sha");

    // Verify the new content includes the existing content plus a new entry
    const writtenContent = atob(callArgs.content as string);
    assert.ok(writtenContent.startsWith(existingContent), "New content should start with existing content");
    assert.ok(writtenContent.length > existingContent.length, "New content should be longer than existing");
  });

  it("audit entry contains timestamp, projection name, query_hash, and query_preview", async () => {
    const octokit = makeOctokit({ getContentThrows: true });

    const query = "Tell me about your projects.";
    // @ts-expect-error mock octokit doesn't implement full interface
    await appendAuditEntry(query, "professional", mockEnv, octokit);

    const callArgs = octokit.repos.createOrUpdateFileContents.mock.calls[0].arguments[0] as Record<string, unknown>;
    const writtenContent = atob(callArgs.content as string);
    const entry = JSON.parse(writtenContent.trim());

    assert.ok(typeof entry.timestamp === "string", "entry has timestamp");
    assert.equal(entry.projection, "professional");
    assert.ok(typeof entry.query_hash === "string" && entry.query_hash.length === 64, "entry has 64-char sha256 hash");
    assert.ok(typeof entry.query_preview === "string", "entry has query_preview");
    assert.equal(entry.query_preview, query);
  });

  it("query_preview is truncated to 80 chars max", async () => {
    const octokit = makeOctokit({ getContentThrows: true });

    const longQuery = "a".repeat(200);
    // @ts-expect-error mock octokit doesn't implement full interface
    await appendAuditEntry(longQuery, "public", mockEnv, octokit);

    const callArgs = octokit.repos.createOrUpdateFileContents.mock.calls[0].arguments[0] as Record<string, unknown>;
    const writtenContent = atob(callArgs.content as string);
    const entry = JSON.parse(writtenContent.trim());

    assert.equal(entry.query_preview.length, 80, "query_preview truncated to 80 chars");
    assert.equal(entry.query_preview, "a".repeat(80));
  });

  it("swallows errors without throwing (simulating 409 conflict)", async () => {
    const octokit = makeOctokit({
      getContentThrows: true,
      createOrUpdateThrows: true,
    });

    // Must not throw even when createOrUpdateFileContents rejects
    await assert.doesNotReject(async () => {
      // @ts-expect-error mock octokit doesn't implement full interface
      await appendAuditEntry("Any query", "public", mockEnv, octokit);
    });
  });
});
