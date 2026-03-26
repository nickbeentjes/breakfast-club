import { Hono } from "hono";
import { cors } from "hono/cors";
import type { Env } from "./types.js";

type Variables = {
  projectionName: string;
};

const app = new Hono<{ Bindings: Env; Variables: Variables }>();

// CORS for browser requests
app.use("/*", cors());

// Health check (no auth needed)
app.get("/health", (c) => {
  return c.json({ status: "ok", service: "breakfast-club-chatbot" });
});

// Chat routes will be added in Plan 02-03
// app.post("/chat", authMiddleware, chatHandler);

export default app;
