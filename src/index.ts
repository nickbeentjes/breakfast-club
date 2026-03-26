import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { registerIdentityContextTool } from "./tools/identity-context.js";
import { registerProjectsListTool } from "./tools/projects-list.js";
import { registerIdentityQueryTool } from "./tools/identity-query.js";
import { registerVerifyIntegrityTool } from "./tools/verify-integrity.js";

const server = new McpServer({
  name: "breakfast-club-identity",
  version: "1.0.0",
});

// Register tools
registerIdentityContextTool(server);
registerProjectsListTool(server);
registerIdentityQueryTool(server);
registerVerifyIntegrityTool(server);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Breakfast Club MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});

// Graceful shutdown
process.on("SIGINT", () => {
  console.error("Shutting down...");
  process.exit(0);
});
