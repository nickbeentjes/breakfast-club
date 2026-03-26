import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { applyProjection } from "./apply-projection.js";
import type { ProjectionDefinition } from "./types.js";
import type { IdentityDocument } from "../types.js";

// Minimal mock document factory — only section, sensitivity, content, doc_type needed for filter logic
function makeDoc(
  section: IdentityDocument["section"],
  sensitivity: IdentityDocument["sensitivity"],
  content: Record<string, unknown>
): IdentityDocument {
  return {
    doc_type: "identity",
    section,
    sensitivity,
    schema_version: "1.0",
    content,
    embedding: [],
    embedding_model: "test",
    updated_at: new Date(),
  } as unknown as IdentityDocument;
}

const professionalProjection: ProjectionDefinition = {
  name: "professional",
  description: "Recruiter-facing projection",
  allowed_sections: ["skills", "projects"],
  allowed_sensitivity: ["public", "professional"],
};

const professionalWithFieldAllowlist: ProjectionDefinition = {
  name: "professional-filtered",
  description: "Professional with field allowlist",
  allowed_sections: ["persona", "skills"],
  allowed_sensitivity: ["public", "professional"],
  field_allowlist: {
    persona: ["name", "working_style"],
  },
};

const sampleDocs: IdentityDocument[] = [
  makeDoc("persona", "public", { name: "Nick", working_style: "async", location: "Sydney" }),
  makeDoc("skills", "public", { primary_stack: "TypeScript", domain_expertise: "AI" }),
  makeDoc("skills", "professional", { primary_stack: "Node.js", consulting_rate: "private" }),
  makeDoc("projects", "professional", { active: ["breakfast-club"], secret: "internal" }),
  makeDoc("values", "personal", { professional: ["autonomy"], personal_notes: "sensitive" }),
  makeDoc("persona", "private", { home_address: "redacted" }),
];

describe("applyProjection", () => {
  it("Test 1: filters documents by allowed_sections — returns only docs whose section is in the allowlist", () => {
    const result = applyProjection(sampleDocs, professionalProjection);
    const sections = result.map((d) => d.section);
    assert.ok(sections.every((s) => ["skills", "projects"].includes(s)),
      "Result should only contain skills and projects sections");
    assert.ok(!sections.includes("persona"), "persona section should be excluded");
    assert.ok(!sections.includes("values"), "values section should be excluded");
  });

  it("Test 2: filters by allowed_sensitivity — returns only docs whose sensitivity is in the allowlist", () => {
    const result = applyProjection(sampleDocs, professionalProjection);
    const sensitivities = result.map((d) => d.sensitivity);
    assert.ok(sensitivities.every((s) => ["public", "professional"].includes(s)),
      "Result should only contain public and professional sensitivity docs");
    assert.ok(!sensitivities.includes("personal"), "personal sensitivity should be excluded");
    assert.ok(!sensitivities.includes("private"), "private sensitivity should be excluded");
  });

  it("Test 3: applies field_allowlist to content — when field_allowlist is specified, only those content keys are present", () => {
    const result = applyProjection(sampleDocs, professionalWithFieldAllowlist);
    const personaDocs = result.filter((d) => d.section === "persona");
    assert.ok(personaDocs.length > 0, "Should have persona docs");
    for (const doc of personaDocs) {
      const keys = Object.keys(doc.content);
      assert.ok(keys.every((k) => ["name", "working_style"].includes(k)),
        `Content keys should be limited to allowlist, got: ${keys.join(", ")}`);
      assert.ok(!keys.includes("location"), "location should be filtered out by field_allowlist");
    }
  });

  it("Test 4: applyProjection with no field_allowlist returns full content for allowed sections", () => {
    const result = applyProjection(sampleDocs, professionalProjection);
    const skillsDocs = result.filter((d) => d.section === "skills");
    assert.ok(skillsDocs.length > 0, "Should have skills docs");
    // Without field_allowlist, skills docs should have full content
    const publicSkills = skillsDocs.find((d) => d.sensitivity === "public");
    assert.ok(publicSkills, "Should find public skills doc");
    assert.ok("primary_stack" in publicSkills.content, "Full content should be preserved");
    assert.ok("domain_expertise" in publicSkills.content, "Full content should be preserved");
  });

  it("Test 5: returns empty array when projection is null — fail closed", () => {
    const result = applyProjection(sampleDocs, null);
    assert.deepEqual(result, [], "Should return empty array when projection is null");
  });

  it("Test 6: returns empty array when projection is undefined — fail closed", () => {
    const result = applyProjection(sampleDocs, undefined);
    assert.deepEqual(result, [], "Should return empty array when projection is undefined");
  });

  it("Test 7: returns empty array when docs array is empty", () => {
    const result = applyProjection([], professionalProjection);
    assert.deepEqual(result, [], "Should return empty array when docs is empty");
  });

  it("Test 8: professional projection returns only skills and projects with public+professional sensitivity", () => {
    const result = applyProjection(sampleDocs, professionalProjection);
    assert.ok(result.length > 0, "Should return some docs");
    for (const doc of result) {
      assert.ok(["skills", "projects"].includes(doc.section),
        `Section ${doc.section} should be skills or projects`);
      assert.ok(["public", "professional"].includes(doc.sensitivity),
        `Sensitivity ${doc.sensitivity} should be public or professional`);
    }
  });

  it("Test 9: does not mutate input docs", () => {
    const doc = makeDoc("persona", "public", { name: "Nick", location: "Sydney" });
    const projection = professionalWithFieldAllowlist;
    const originalContent = { ...doc.content };
    applyProjection([doc], projection);
    assert.deepEqual(doc.content, originalContent, "Original doc content should not be mutated");
  });
});
