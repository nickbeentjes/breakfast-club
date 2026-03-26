import { getDb } from "./db.js";
import type { Env } from "../types.js";

// Inline the projection logic to avoid cross-project import issues with wrangler bundler.
// The projection definitions are embedded as constants since the Worker can't read the filesystem at runtime.

interface ProjectionDef {
  name: string;
  allowed_sections: string[];
  allowed_sensitivity: string[];
  field_allowlist?: Record<string, string[]>;
}

const PROJECTIONS: Record<string, ProjectionDef> = {
  public: {
    name: "public",
    allowed_sections: ["persona", "skills"],
    allowed_sensitivity: ["public"],
    field_allowlist: { persona: ["name"], skills: ["primary_stack"] },
  },
  professional: {
    name: "professional",
    allowed_sections: ["persona", "skills", "projects"],
    allowed_sensitivity: ["public", "professional"],
    field_allowlist: { persona: ["name", "working_style", "communication_style"] },
  },
};

function applyProjectionFilter(
  docs: Array<{ section: string; sensitivity: string; content: Record<string, unknown> }>,
  projection: ProjectionDef | undefined
): typeof docs {
  if (!projection) return []; // fail closed
  return docs
    .filter((d) => projection.allowed_sections.includes(d.section))
    .filter((d) => projection.allowed_sensitivity.includes(d.sensitivity))
    .map((d) => {
      const allowlist = projection.field_allowlist?.[d.section];
      if (!allowlist) return d;
      return {
        ...d,
        content: Object.fromEntries(
          Object.entries(d.content).filter(([key]) => allowlist.includes(key))
        ),
      };
    });
}

export async function getIdentityForProjection(
  projectionName: string,
  env: Env
): Promise<string> {
  const db = await getDb(env.MONGODB_URI);
  const docs = await db
    .collection("identity")
    .find({ doc_type: "identity" })
    .project({ section: 1, sensitivity: 1, content: 1, _id: 0 })
    .toArray();

  const projection = PROJECTIONS[projectionName];
  const filtered = applyProjectionFilter(
    docs as Array<{ section: string; sensitivity: string; content: Record<string, unknown> }>,
    projection
  );

  if (filtered.length === 0) {
    return "No identity data available for this projection scope.";
  }

  // Format as structured text for the system prompt
  const parts: string[] = [];
  for (const doc of filtered) {
    parts.push(`## ${doc.section}`);
    parts.push(JSON.stringify(doc.content, null, 2));
    parts.push("");
  }
  return parts.join("\n");
}
