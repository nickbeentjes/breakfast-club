import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { getDb } from "../db.js";

export function registerBreakfastClubStatusTool(server: McpServer): void {
  server.registerTool(
    "breakfast_club_status",
    {
      description:
        "Health check — reports status of MongoDB connection, projection engine, and chatbot Worker endpoint.",
      inputSchema: {
        chatbot_url: z
          .string()
          .optional()
          .describe("Chatbot Worker URL to health-check (e.g. https://breakfast-club-chatbot.workers.dev)"),
      },
    },
    async ({ chatbot_url }) => {
      const checks: Array<{ name: string; status: "ok" | "error"; detail: string }> = [];

      // Check 1: MongoDB connection
      try {
        const db = await getDb();
        const count = await db.collection("identity").countDocuments({ doc_type: "identity" });
        checks.push({
          name: "MongoDB",
          status: "ok",
          detail: `Connected — ${count} identity documents`,
        });
      } catch (error) {
        checks.push({
          name: "MongoDB",
          status: "error",
          detail: `Connection failed: ${error instanceof Error ? error.message : String(error)}`,
        });
      }

      // Check 2: Projection engine
      try {
        const { loadProjections } = await import("../projection/load-projections.js");
        const { dirname, join } = await import("node:path");
        const { fileURLToPath } = await import("node:url");
        const __dirname = dirname(fileURLToPath(import.meta.url));
        const projections = loadProjections(join(__dirname, "../../projections"));
        checks.push({
          name: "Projections",
          status: "ok",
          detail: `Loaded ${projections.size} projections: ${Array.from(projections.keys()).join(", ")}`,
        });
      } catch (error) {
        checks.push({
          name: "Projections",
          status: "error",
          detail: `Load failed: ${error instanceof Error ? error.message : String(error)}`,
        });
      }

      // Check 3: Chatbot Worker (optional — only if URL provided)
      if (chatbot_url) {
        try {
          const healthUrl = chatbot_url.replace(/\/$/, "") + "/health";
          const res = await fetch(healthUrl, { signal: AbortSignal.timeout(5000) });
          if (res.ok) {
            const data = await res.json() as { status?: string; service?: string };
            checks.push({
              name: "Chatbot Worker",
              status: "ok",
              detail: `${data.service ?? "unknown"} — status: ${data.status ?? "unknown"}`,
            });
          } else {
            checks.push({
              name: "Chatbot Worker",
              status: "error",
              detail: `HTTP ${res.status}: ${res.statusText}`,
            });
          }
        } catch (error) {
          checks.push({
            name: "Chatbot Worker",
            status: "error",
            detail: `Unreachable: ${error instanceof Error ? error.message : String(error)}`,
          });
        }
      }

      const allOk = checks.every((c) => c.status === "ok");
      const summary = checks
        .map((c) => `${c.status === "ok" ? "+" : "x"} ${c.name}: ${c.detail}`)
        .join("\n");

      const header = allOk
        ? "## Breakfast Club Status: ALL SYSTEMS GO"
        : "## Breakfast Club Status: ISSUES DETECTED";

      console.error(`breakfast_club_status: ${allOk ? "all ok" : "issues detected"}`);

      return {
        content: [{ type: "text" as const, text: `${header}\n\n${summary}` }],
      };
    }
  );
}
