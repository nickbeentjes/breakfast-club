import { createMiddleware } from "hono/factory";
import type { Env } from "../types.js";

type Variables = {
  projectionName: string;
};

export const authMiddleware = createMiddleware<{
  Bindings: Env;
  Variables: Variables;
}>(async (c, next) => {
  // Extract token from Authorization header or query string
  const authHeader = c.req.header("Authorization");
  const token = authHeader?.startsWith("Bearer ")
    ? authHeader.slice(7)
    : new URL(c.req.url).searchParams.get("token");

  let tokenMap: Record<string, string> = {};
  try {
    tokenMap = JSON.parse(c.env.TOKEN_MAP || "{}");
  } catch {
    console.error("auth: failed to parse TOKEN_MAP");
    return c.json({ error: "Server configuration error" }, 500);
  }

  if (token) {
    const projectionName = tokenMap[token];
    if (!projectionName) {
      return c.json({ error: "Invalid token" }, 401);
    }
    // NEVER default to "owner" or "personal" — locked decision
    if (projectionName === "personal" || projectionName === "owner") {
      console.error(`auth: BLOCKED — token mapped to forbidden projection "${projectionName}"`);
      return c.json({ error: "Invalid token configuration" }, 403);
    }
    c.set("projectionName", projectionName);
  } else {
    // No token = public projection (NEVER owner/personal)
    c.set("projectionName", "public");
  }

  await next();
});
