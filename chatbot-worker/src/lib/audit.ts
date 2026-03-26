import { Octokit } from "@octokit/rest";
import type { Env } from "../types.js";

async function sha256(text: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(text);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function appendAuditEntry(
  query: string,
  projectionName: string,
  env: Env,
  octokitOverride?: Octokit
): Promise<void> {
  try {
    const octokit = octokitOverride ?? new Octokit({ auth: env.GITHUB_TOKEN });
    const path = "audit/recruiter-queries.jsonl";

    // Get current file content and SHA
    let currentContent = "";
    let fileSha: string | undefined;
    try {
      const { data } = await octokit.repos.getContent({
        owner: env.GITHUB_OWNER,
        repo: env.GITHUB_PRIVATE_REPO,
        path,
      });
      if ("content" in data && typeof data.content === "string") {
        currentContent = atob(data.content.replace(/\n/g, ""));
        fileSha = data.sha;
      }
    } catch {
      // File doesn't exist yet — will create it
    }

    const queryHash = await sha256(query);
    const entry = JSON.stringify({
      timestamp: new Date().toISOString(),
      projection: projectionName,
      query_hash: queryHash,
      query_preview: query.slice(0, 80),
    });

    const newContent = currentContent + entry + "\n";

    await octokit.repos.createOrUpdateFileContents({
      owner: env.GITHUB_OWNER,
      repo: env.GITHUB_PRIVATE_REPO,
      path,
      message: "audit: recruiter query [skip ci]",
      content: btoa(newContent),
      sha: fileSha,
    });

    console.error(`audit: logged query for projection=${projectionName}`);
  } catch (error) {
    // Audit write failure MUST NOT break the chat response
    console.error("audit: write failed (non-fatal):", error);
  }
}
