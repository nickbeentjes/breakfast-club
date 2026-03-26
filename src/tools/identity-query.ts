import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { getDb } from "../db.js";
import { embedText } from "../embed.js";
import { applyProjection } from "../projection/apply-projection.js";
import { loadProjections, getProjection } from "../projection/load-projections.js";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type { ProjectionDefinition } from "../projection/types.js";

/**
 * identity_query — semantic search over the owner's identity documents.
 *
 * Accepts a natural-language question, embeds it with OpenAI text-embedding-3-small,
 * then runs a $vectorSearch aggregation against the identity collection.
 * Pre-filters by doc_type=identity so future memory chunks (Phase 4) are excluded.
 */

let cachedProjections: Map<string, ProjectionDefinition> | null = null;

function getProjections(): Map<string, ProjectionDefinition> {
  if (!cachedProjections) {
    const __dirname = dirname(fileURLToPath(import.meta.url));
    const projectionsDir = join(__dirname, "../../projections");
    cachedProjections = loadProjections(projectionsDir);
  }
  return cachedProjections;
}

export function registerIdentityQueryTool(server: McpServer): void {
  server.registerTool(
    "identity_query",
    {
      description:
        "Search the owner's identity using a natural-language question. Returns semantically relevant sections from persona, skills, projects, and values.",
      inputSchema: {
        question: z
          .string()
          .describe("Natural-language question about the owner's identity"),
        limit: z
          .number()
          .optional()
          .default(5)
          .describe("Number of results to return (1–10)"),
        projection_name: z
          .string()
          .optional()
          .default("personal")
          .describe("Projection to apply — defaults to personal (full owner access)"),
      },
    },
    async ({ question, limit, projection_name }) => {
      const effectiveLimit = Math.max(1, Math.min(10, limit ?? 5));

      try {
        const queryEmbedding = await embedText(question);
        const db = await getDb();

        const results = await db
          .collection("identity")
          .aggregate([
            {
              $vectorSearch: {
                index: "identity_vector_index",
                path: "embedding",
                queryVector: queryEmbedding,
                numCandidates: 50,
                limit: effectiveLimit,
                filter: { doc_type: "identity" },
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
          ])
          .toArray();

        // Apply projection filtering — map results to IdentityDocument shape
        const projections = getProjections();
        const projection = getProjection(projections, projection_name);
        const docsForProjection = results.map((r) => ({
          doc_type: "identity" as const,
          section: r["section"] as import("../types.js").IdentitySection,
          sensitivity: r["sensitivity"] as import("../types.js").SensitivityLevel,
          content: r["content"] as Record<string, unknown>,
          score: r["score"], // preserve score for output
        }));
        const filtered = applyProjection(docsForProjection as any, projection);

        console.error(
          `identity_query: projection=${projection_name}, "${question.slice(0, 60)}" → ${filtered.length} results (${results.length} before projection)`
        );

        if (filtered.length === 0) {
          return {
            content: [
              {
                type: "text" as const,
                text: "No identity data found matching your question.",
              },
            ],
          };
        }

        const lines: string[] = [
          `## Identity Search Results for: "${question}"`,
          "",
        ];

        for (const doc of filtered) {
          const result = doc as typeof doc & { score?: unknown };
          const score = typeof result["score"] === "number" ? result["score"] : 0;
          const section = String(doc.section ?? "unknown");
          const sensitivity = String(doc.sensitivity ?? "unknown");
          const content = doc.content;

          lines.push(
            `### ${section} (relevance: ${score.toFixed(3)}, sensitivity: ${sensitivity})`
          );
          lines.push(JSON.stringify(content, null, 2));
          lines.push("---");
          lines.push("");
        }

        return {
          content: [{ type: "text" as const, text: lines.join("\n").trim() }],
        };
      } catch (error) {
        console.error("identity_query tool error:", error);
        throw error;
      }
    }
  );
}
