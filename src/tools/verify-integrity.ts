import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { execSync } from "node:child_process";

/**
 * verify_integrity — returns the current git tree SHA for attestation purposes.
 *
 * Phase 1 scope: git SHA retrieval only. Cross-verification with the public
 * attestation chain log is deferred to Phase 3.
 */
export function registerVerifyIntegrityTool(server: McpServer): void {
  server.registerTool(
    "verify_integrity",
    {
      description:
        "Return the current git tree SHA for the identity repository. Used as the first step in verifying data integrity. Full attestation chain verification is available in Phase 3.",
      inputSchema: {
        repo: z
          .string()
          .optional()
          .default("breakfast-club-identity")
          .describe("GitHub repository name"),
      },
    },
    async ({ repo }) => {
      const repoName = repo ?? "breakfast-club-identity";
      const timestamp = new Date().toISOString();

      let gitTreeSha: string;

      try {
        gitTreeSha = execSync("git rev-parse HEAD", { encoding: "utf8" }).trim();
      } catch (error) {
        console.error("verify_integrity: git rev-parse failed:", error);
        const errorMsg = error instanceof Error ? error.message : String(error);
        return {
          content: [
            {
              type: "text" as const,
              text: [
                "## Integrity Check",
                "",
                `**Repository:** ${repoName}`,
                `**Timestamp:** ${timestamp}`,
                `**Git Tree SHA:** Error — could not retrieve SHA: ${errorMsg}`,
                "**Attestation Chain:** Pending — attestation log verification will be available in Phase 3",
                "",
                "Status: Unable to retrieve git SHA. Ensure the MCP server is running from within the repository directory.",
              ].join("\n"),
            },
          ],
        };
      }

      console.error(`verify_integrity: git_tree_sha=${gitTreeSha.slice(0, 8)}`);

      return {
        content: [
          {
            type: "text" as const,
            text: [
              "## Integrity Check",
              "",
              `**Git Tree SHA:** ${gitTreeSha}`,
              `**Repository:** ${repoName}`,
              `**Timestamp:** ${timestamp}`,
              "**Attestation Chain:** Pending — attestation log verification will be available in Phase 3",
              "",
              "Status: SHA retrieved successfully. Cross-verification with public attestation chain is not yet implemented.",
            ].join("\n"),
          },
        ],
      };
    }
  );
}
