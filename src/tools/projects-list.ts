import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { getDb } from "../db.js";
import type { IdentityDocument, ProjectsSection, ProjectEntry } from "../types.js";
import { applyProjection } from "../projection/apply-projection.js";
import { loadProjections, getProjection } from "../projection/load-projections.js";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type { ProjectionDefinition } from "../projection/types.js";

let cachedProjections: Map<string, ProjectionDefinition> | null = null;

function getProjections(): Map<string, ProjectionDefinition> {
  if (!cachedProjections) {
    const __dirname = dirname(fileURLToPath(import.meta.url));
    const projectionsDir = join(__dirname, "../../projections");
    cachedProjections = loadProjections(projectionsDir);
  }
  return cachedProjections;
}

export function registerProjectsListTool(server: McpServer): void {
  server.registerTool(
    "projects_list",
    {
      description:
        "Return active projects with name, status, and description. Optionally includes completed projects.",
      inputSchema: {
        include_completed: z
          .boolean()
          .optional()
          .default(false)
          .describe("Include completed projects in the response"),
        projection_name: z
          .string()
          .optional()
          .default("personal")
          .describe("Projection to apply — defaults to personal (full owner access)"),
      },
    },
    async ({ include_completed, projection_name }) => {
      try {
        const db = await getDb();
        const doc = await db
          .collection<IdentityDocument>("identity")
          .findOne({ doc_type: "identity", section: "projects" });

        // Apply projection filtering — wrap doc in array, filter, unwrap
        const projections = getProjections();
        const projection = getProjection(projections, projection_name);
        const filtered = applyProjection(doc ? [doc] : [], projection);
        const projectsDoc = filtered[0];

        if (!projectsDoc) {
          return {
            content: [{ type: "text" as const, text: "No projects data available for this projection." }],
          };
        }

        const projects = projectsDoc.content as ProjectsSection;
        const active = Array.isArray(projects.active) ? projects.active : [];
        const completed = Array.isArray(projects.completed) ? projects.completed : [];

        const lines: string[] = [];

        if (active.length > 0) {
          lines.push("## Active Projects", "");
          for (const project of active) {
            const p = project as ProjectEntry;
            const stackStr =
              Array.isArray(p.stack) && p.stack.length > 0
                ? `\n  Stack: ${p.stack.join(", ")}`
                : "";
            lines.push(`- **${String(p.name)}** [${String(p.status)}] — ${String(p.description)}${stackStr}`);
          }
        } else {
          lines.push("No active projects found.");
        }

        if (include_completed && completed.length > 0) {
          lines.push("", "## Completed Projects", "");
          for (const project of completed) {
            const p = project as Record<string, unknown>;
            const name = typeof p["name"] === "string" ? p["name"] : "Unknown";
            const description = typeof p["description"] === "string" ? p["description"] : "";
            lines.push(`- **${name}** — ${description}`);
          }
        }

        const projectsList = lines.join("\n");
        console.error(
          `projects_list: projection=${projection_name}, returning ${active.length} active${include_completed ? `, ${completed.length} completed` : ""} projects`
        );

        return { content: [{ type: "text" as const, text: projectsList }] };
      } catch (error) {
        console.error("projects_list tool error:", error);
        throw error;
      }
    }
  );
}
