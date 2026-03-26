import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { getDb } from "../db.js";
import type { IdentityDocument, PersonaSection, SkillsSection, ProjectsSection } from "../types.js";
import { applyProjection } from "../projection/apply-projection.js";
import { loadProjections, getProjection } from "../projection/load-projections.js";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type { ProjectionDefinition } from "../projection/types.js";

/**
 * Assembles a synthesized context string from identity documents within a token budget.
 * Token estimate: Math.ceil(words * 1.3) per RESEARCH.md pattern.
 */
function estimateTokens(text: string): number {
  return Math.ceil(text.split(/\s+/).length * 1.3);
}

let cachedProjections: Map<string, ProjectionDefinition> | null = null;

function getProjections(): Map<string, ProjectionDefinition> {
  if (!cachedProjections) {
    const __dirname = dirname(fileURLToPath(import.meta.url));
    const projectionsDir = join(__dirname, "../../projections");
    cachedProjections = loadProjections(projectionsDir);
  }
  return cachedProjections;
}

export function registerIdentityContextTool(server: McpServer): void {
  server.registerTool(
    "identity_context",
    {
      description:
        "Return synthesized identity context for system prompt injection. Covers persona, skills, and active projects within a configurable token budget.",
      inputSchema: {
        max_tokens: z
          .number()
          .optional()
          .default(1200)
          .describe("Token budget ceiling for the returned context"),
        projection_name: z
          .string()
          .optional()
          .default("personal")
          .describe("Projection to apply — defaults to personal (full owner access)"),
      },
    },
    async ({ max_tokens, projection_name }) => {
      try {
        const db = await getDb();
        const docs = await db
          .collection<IdentityDocument>("identity")
          .find({ doc_type: "identity" })
          .toArray();

        // Apply projection filtering
        const projections = getProjections();
        const projection = getProjection(projections, projection_name);
        const filteredDocs = applyProjection(docs, projection);

        // Index filtered docs by section for easy lookup
        const bySection: Record<string, IdentityDocument> = {};
        for (const doc of filteredDocs) {
          bySection[doc.section] = doc;
        }

        const persona = bySection["persona"]?.content as PersonaSection | undefined;
        const skills = bySection["skills"]?.content as SkillsSection | undefined;
        const projects = bySection["projects"]?.content as ProjectsSection | undefined;

        const lines: string[] = ["## Identity Context", ""];

        // Persona section
        if (persona) {
          lines.push("### Persona");
          if (persona.name) lines.push(`Name: ${String(persona.name)}`);
          if (persona.communication_style?.primary) {
            lines.push(`Style: ${String(persona.communication_style.primary)}`);
          }
          if (persona.working_style?.approach) {
            lines.push(`Approach: ${String(persona.working_style.approach)}`);
          }
          if (persona.working_style?.tools) {
            lines.push(`Tools: ${String(persona.working_style.tools)}`);
          }
          if (Array.isArray(persona.working_style?.strengths)) {
            lines.push(`Key strengths: ${persona.working_style.strengths.join(", ")}`);
          }
          lines.push("");
        }

        // Skills section
        if (skills) {
          lines.push("### Skills");
          const stack = skills.primary_stack as Record<string, unknown> | undefined;
          if (stack) {
            const stackParts: string[] = [];
            if (Array.isArray(stack["languages"])) stackParts.push(...(stack["languages"] as string[]));
            if (Array.isArray(stack["databases"])) stackParts.push(...(stack["databases"] as string[]));
            if (Array.isArray(stack["infrastructure"])) stackParts.push(...(stack["infrastructure"] as string[]));
            if (stackParts.length > 0) {
              lines.push(`Primary stack: ${stackParts.join(", ")}`);
            }
          }
          const expertise = skills.domain_expertise as Record<string, { depth: string; details?: string }> | undefined;
          if (expertise) {
            const domainParts = Object.entries(expertise).map(
              ([domain, info]) => `${domain} (${info.depth})`
            );
            lines.push(`Domain expertise: ${domainParts.join(", ")}`);
          }
          lines.push("");
        }

        // Projects section — may be trimmed to fit token budget
        if (projects) {
          lines.push("### Active Projects");
          const active = Array.isArray(projects.active) ? projects.active : [];

          // Build full projects list first, then trim if over budget
          const projectLines = active.map(
            (p) => `- ${String(p.name)} (${String(p.status)}): ${String(p.description)}`
          );

          const contextSoFar = lines.join("\n");
          const remaining = (max_tokens ?? 1200) - estimateTokens(contextSoFar);

          // Add projects until we'd exceed the budget; always include at least 1
          let added = 0;
          for (const pl of projectLines) {
            if (added > 0 && estimateTokens(pl) > remaining - estimateTokens(lines.join("\n"))) {
              break;
            }
            lines.push(pl);
            added++;
            if (added >= 3) break; // hard cap at 3 for token budget safety
          }
          lines.push("");
        }

        const contextString = lines.join("\n").trim();
        console.error(
          `identity_context: projection=${projection_name}, assembled ${estimateTokens(contextString)} estimated tokens`
        );

        return { content: [{ type: "text" as const, text: contextString }] };
      } catch (error) {
        console.error("identity_context tool error:", error);
        throw error;
      }
    }
  );
}
