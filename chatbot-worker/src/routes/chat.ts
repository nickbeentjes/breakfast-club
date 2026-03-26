import { Hono } from "hono";
import { streamText } from "hono/streaming";
import type { Env } from "../types.js";
import { authMiddleware } from "../middleware/auth.js";
import { getIdentityForProjection } from "../lib/identity.js";
import { buildSystemPrompt, createChatStream, type ChatMessage } from "../lib/openai.js";
import { appendAuditEntry } from "../lib/audit.js";

type Variables = { projectionName: string };

export const chatRoute = new Hono<{ Bindings: Env; Variables: Variables }>();

chatRoute.post("/", authMiddleware, async (c) => {
  const { message, history } = await c.req.json<{
    message: string;
    history?: ChatMessage[];
  }>();

  if (!message || typeof message !== "string" || message.trim().length === 0) {
    return c.json({ error: "message is required" }, 400);
  }

  const projectionName = c.get("projectionName");

  console.error(`chat: projection=${projectionName}, message="${message.slice(0, 60)}"`);

  const identityContext = await getIdentityForProjection(projectionName, c.env);
  const systemPrompt = buildSystemPrompt(identityContext, projectionName);

  const completion = await createChatStream(
    systemPrompt,
    history ?? [],
    message,
    c.env
  );

  // Fire audit write in background — NEVER block the streaming response
  // Use c.executionCtx.waitUntil for Cloudflare Workers background task
  c.executionCtx.waitUntil(
    appendAuditEntry(message, projectionName, c.env)
  );

  return streamText(c, async (stream) => {
    for await (const chunk of completion) {
      const delta = chunk.choices[0]?.delta?.content ?? "";
      if (delta) {
        await stream.write(delta);
      }
    }
  });
});
