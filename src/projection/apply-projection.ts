import type { IdentityDocument } from "../types.js";
import type { ProjectionDefinition } from "./types.js";

/**
 * Whitelist filter function — the core IP of Breakfast Club.
 *
 * Returns only IdentityDocuments that pass both section and sensitivity
 * allowlists in the given projection. Applies optional field-level allowlists
 * to content objects for fine-grained filtering.
 *
 * CRITICAL INVARIANT (PROJ-01): If projection is null or undefined, returns []
 * — NEVER the full document set. "Fail closed" is the safety contract.
 */
export function applyProjection(
  docs: IdentityDocument[],
  projection: ProjectionDefinition | null | undefined
): IdentityDocument[] {
  if (!projection) {
    return [];
  }

  return docs
    .filter((doc) => projection.allowed_sections.includes(doc.section))
    .filter((doc) => projection.allowed_sensitivity.includes(doc.sensitivity))
    .map((doc) => ({
      ...doc,
      content: filterContent(doc.content, projection.field_allowlist?.[doc.section]),
    }));
}

function filterContent(
  content: Record<string, unknown>,
  allowlist?: string[]
): Record<string, unknown> {
  if (!allowlist) {
    return content;
  }
  return Object.fromEntries(
    Object.entries(content).filter(([key]) => allowlist.includes(key))
  );
}
