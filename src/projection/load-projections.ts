import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { z } from "zod";
import type { ProjectionDefinition } from "./types.js";

const projectionSchema = z.object({
  name: z.string().min(1),
  description: z.string(),
  allowed_sections: z
    .array(z.enum(["persona", "skills", "projects", "values"]))
    .min(1),
  allowed_sensitivity: z
    .array(z.enum(["public", "professional", "personal", "private"]))
    .min(1),
  field_allowlist: z.record(z.string(), z.array(z.string())).optional(),
});

/**
 * Reads all .json files from projectionsDir, validates each against Zod schema,
 * and returns a Map keyed by projection name.
 *
 * Throws on any invalid JSON syntax or schema validation failure — fail loud,
 * never silently skip a malformed projection file (per Pitfall 5 in RESEARCH.md).
 */
export function loadProjections(
  projectionsDir: string
): Map<string, ProjectionDefinition> {
  const projections = new Map<string, ProjectionDefinition>();

  const files = readdirSync(projectionsDir).filter((f) => f.endsWith(".json"));

  for (const file of files) {
    const filePath = join(projectionsDir, file);
    let raw: string;
    try {
      raw = readFileSync(filePath, "utf8");
    } catch (err) {
      throw new Error(`Failed to read projection file ${file}: ${String(err)}`);
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch (err) {
      throw new Error(
        `Invalid JSON in projection file ${file}: ${String(err)}`
      );
    }

    let validated: ProjectionDefinition;
    try {
      validated = projectionSchema.parse(parsed) as ProjectionDefinition;
    } catch (err) {
      throw new Error(
        `Projection file ${file} failed schema validation: ${String(err)}`
      );
    }

    projections.set(validated.name, validated);
  }

  return projections;
}

/**
 * Simple Map.get() wrapper for clarity — returns undefined if projection not found.
 * Callers should treat undefined as "use public projection" — never "use full access".
 */
export function getProjection(
  projections: Map<string, ProjectionDefinition>,
  name: string
): ProjectionDefinition | undefined {
  return projections.get(name);
}
