import { Hono } from "hono";
import { cors } from "hono/cors";
import type { Env } from "./types.js";
import { chatRoute } from "./routes/chat.js";

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

app.route("/chat", chatRoute);

export default app;
