import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { Hono } from "hono";
import { authMiddleware } from "./auth.js";
import type { Env } from "../types.js";

type Variables = {
  projectionName: string;
};

/**
 * Build a minimal test app that runs authMiddleware and echoes the projectionName.
 */
function makeApp(tokenMap: Record<string, string>): Hono<{ Bindings: Env; Variables: Variables }> {
  const app = new Hono<{ Bindings: Env; Variables: Variables }>();
  app.use("/*", authMiddleware);
  app.get("/test", (c) => {
    return c.json({ projectionName: c.get("projectionName") });
  });
  return app;
}

function makeEnv(tokenMap: Record<string, string> | string): Env {
  return {
    MONGODB_URI: "mongodb://localhost",
    OPENAI_API_KEY: "test-key",
    GITHUB_TOKEN: "test-token",
    GITHUB_OWNER: "test-owner",
    GITHUB_PRIVATE_REPO: "test-repo",
    TOKEN_MAP: typeof tokenMap === "string" ? tokenMap : JSON.stringify(tokenMap),
  };
}

describe("authMiddleware", () => {
  test("no token defaults to public projection", async () => {
    const app = makeApp({});
    const env = makeEnv({});
    const res = await app.request("/test", {}, env);
    assert.equal(res.status, 200);
    const body = await res.json() as { projectionName: string };
    assert.equal(body.projectionName, "public");
  });

  test("valid token in Authorization header resolves to correct projection", async () => {
    const tokenMap = { "tok_abc": "professional" };
    const app = makeApp(tokenMap);
    const env = makeEnv(tokenMap);
    const res = await app.request(
      "/test",
      { headers: { Authorization: "Bearer tok_abc" } },
      env
    );
    assert.equal(res.status, 200);
    const body = await res.json() as { projectionName: string };
    assert.equal(body.projectionName, "professional");
  });

  test("valid token in query string resolves to correct projection", async () => {
    const tokenMap = { "tok_xyz": "public" };
    const app = makeApp(tokenMap);
    const env = makeEnv(tokenMap);
    const res = await app.request("/test?token=tok_xyz", {}, env);
    assert.equal(res.status, 200);
    const body = await res.json() as { projectionName: string };
    assert.equal(body.projectionName, "public");
  });

  test("invalid token returns 401", async () => {
    const tokenMap = { "tok_abc": "professional" };
    const app = makeApp(tokenMap);
    const env = makeEnv(tokenMap);
    const res = await app.request(
      "/test",
      { headers: { Authorization: "Bearer tok_not_in_map" } },
      env
    );
    assert.equal(res.status, 401);
    const body = await res.json() as { error: string };
    assert.equal(body.error, "Invalid token");
  });

  test("token mapped to personal projection returns 403", async () => {
    const tokenMap = { "tok_danger": "personal" };
    const app = makeApp(tokenMap);
    const env = makeEnv(tokenMap);
    const res = await app.request(
      "/test",
      { headers: { Authorization: "Bearer tok_danger" } },
      env
    );
    assert.equal(res.status, 403);
    const body = await res.json() as { error: string };
    assert.equal(body.error, "Invalid token configuration");
  });

  test("token mapped to owner projection returns 403", async () => {
    const tokenMap = { "tok_owner": "owner" };
    const app = makeApp(tokenMap);
    const env = makeEnv(tokenMap);
    const res = await app.request(
      "/test",
      { headers: { Authorization: "Bearer tok_owner" } },
      env
    );
    assert.equal(res.status, 403);
    const body = await res.json() as { error: string };
    assert.equal(body.error, "Invalid token configuration");
  });

  test("malformed TOKEN_MAP returns 500", async () => {
    const app = makeApp({});
    const env = makeEnv("this is not valid json {{{{");
    const res = await app.request("/test", {}, env);
    assert.equal(res.status, 500);
    const body = await res.json() as { error: string };
    assert.equal(body.error, "Server configuration error");
  });
});
