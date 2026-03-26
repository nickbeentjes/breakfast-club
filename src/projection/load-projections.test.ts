import { describe, it, after } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, rmSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { loadProjections, getProjection } from "./load-projections.js";

// Resolve real projections directory relative to project root
const __filename = fileURLToPath(import.meta.url);
const projectRoot = join(__filename, "..", "..", "..");
const projectionsDir = join(projectRoot, "projections");

// Temp directory for malformed file tests
let tempDir: string;
tempDir = mkdtempSync(join(tmpdir(), "bc-test-projections-"));

after(() => {
  rmSync(tempDir, { recursive: true, force: true });
});

describe("loadProjections", () => {
  it("Test 1: returns a Map with 3 entries when pointed at projections/ directory", () => {
    const projections = loadProjections(projectionsDir);
    assert.equal(projections.size, 3, `Expected 3 projections, got ${projections.size}`);
  });

  it("Test 2: returns Map keyed by projection name (public, professional, personal)", () => {
    const projections = loadProjections(projectionsDir);
    assert.ok(projections.has("public"), "Map should have 'public' key");
    assert.ok(projections.has("professional"), "Map should have 'professional' key");
    assert.ok(projections.has("personal"), "Map should have 'personal' key");
  });

  it("Test 3: throws on malformed JSON file (invalid JSON syntax)", () => {
    const badFile = join(tempDir, "bad.json");
    writeFileSync(badFile, "{ this is not valid json }");
    assert.throws(
      () => loadProjections(tempDir),
      /JSON|parse|bad\.json/i,
      "Should throw an error mentioning JSON or the filename"
    );
  });

  it("Test 4: throws when a projection file has invalid schema (missing required fields)", () => {
    const schemaDir = mkdtempSync(join(tmpdir(), "bc-schema-test-"));
    try {
      writeFileSync(
        join(schemaDir, "invalid.json"),
        JSON.stringify({ name: "invalid" }) // missing required fields
      );
      assert.throws(
        () => loadProjections(schemaDir),
        /invalid|validation|required|ZodError/i,
        "Should throw a validation error for invalid schema"
      );
    } finally {
      rmSync(schemaDir, { recursive: true, force: true });
    }
  });

  it("Test 5: each built-in projection validates against the Zod schema", () => {
    // If loadProjections doesn't throw, all files passed Zod validation
    assert.doesNotThrow(() => {
      loadProjections(projectionsDir);
    }, "Built-in projections should all validate successfully");
  });

  it("Test 6: public projection has allowed_sections with only summary-level data", () => {
    const projections = loadProjections(projectionsDir);
    const pub = projections.get("public");
    assert.ok(pub, "public projection should exist");
    // Public should only have minimal sections — not values (personal), not projects
    assert.ok(pub.allowed_sections.includes("persona") || pub.allowed_sections.includes("skills"),
      "Public should include at least persona or skills");
    assert.ok(!pub.allowed_sections.includes("values"),
      "Public should not include values section");
    // Only public sensitivity
    assert.deepEqual(pub.allowed_sensitivity, ["public"],
      "Public projection should only allow public sensitivity");
  });

  it("Test 7: professional projection includes skills and projects with public+professional sensitivity", () => {
    const projections = loadProjections(projectionsDir);
    const pro = projections.get("professional");
    assert.ok(pro, "professional projection should exist");
    assert.ok(pro.allowed_sections.includes("skills"),
      "professional should include skills section");
    assert.ok(pro.allowed_sections.includes("projects"),
      "professional should include projects section");
    assert.ok(pro.allowed_sensitivity.includes("public"),
      "professional should allow public sensitivity");
    assert.ok(pro.allowed_sensitivity.includes("professional"),
      "professional should allow professional sensitivity");
  });
});

describe("getProjection", () => {
  it("returns the projection by name from the Map", () => {
    const projections = loadProjections(projectionsDir);
    const pub = getProjection(projections, "public");
    assert.ok(pub, "Should return public projection");
    assert.equal(pub?.name, "public");
  });

  it("returns undefined for unknown projection name", () => {
    const projections = loadProjections(projectionsDir);
    const missing = getProjection(projections, "nonexistent");
    assert.equal(missing, undefined, "Should return undefined for missing key");
  });
});
