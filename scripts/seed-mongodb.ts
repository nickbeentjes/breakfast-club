import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { join, dirname } from "path";
import { embedText, EMBEDDING_MODEL } from "../src/embed.js";
import { getDb, closeDb } from "../src/db.js";
import type { IdentityDocument, IdentitySection, SensitivityLevel } from "../src/types.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const SECTIONS: IdentitySection[] = ["persona", "skills", "projects", "values"];

function sectionToText(sectionName: IdentitySection, sectionData: Record<string, unknown>): string {
  // Create a human-readable text representation that captures semantic meaning
  // JSON.stringify with formatting preserves structure while being readable for embeddings
  const { _sensitivity, ...content } = sectionData;
  void _sensitivity; // excluded from text; it's metadata
  return `Section: ${sectionName}\n${JSON.stringify(content, null, 2)}`;
}

async function main(): Promise<void> {
  const dryRun = process.argv.includes("--dry-run");

  const seedPath = join(__dirname, "../seed-data/nick-identity.json");
  const identityData = JSON.parse(readFileSync(seedPath, "utf-8")) as Record<string, unknown>;

  const schemaVersion = identityData["schema_version"] as string;

  if (dryRun) {
    console.error("DRY RUN — no MongoDB writes will occur");
    console.error("");
  }

  for (const sectionName of SECTIONS) {
    const rawSection = identityData[sectionName] as Record<string, unknown>;
    if (!rawSection) {
      console.error(`WARNING: Section "${sectionName}" not found in seed data — skipping`);
      continue;
    }

    const sensitivity = rawSection["_sensitivity"] as SensitivityLevel;

    // Strip _sensitivity from content before storing (it's a top-level field on the document)
    const { _sensitivity, ...content } = rawSection;
    void _sensitivity;

    const text = sectionToText(sectionName, rawSection);

    if (dryRun) {
      console.error(`[DRY RUN] Would embed and upsert: ${sectionName}`);
      console.error(`  sensitivity: ${sensitivity}`);
      console.error(`  schema_version: ${schemaVersion}`);
      console.error(`  doc_type: identity`);
      console.error(`  embedding: <${EMBEDDING_MODEL} vector, 1536 dims>`);
      console.error(`  content keys: ${Object.keys(content).join(", ")}`);
      console.error(`  filter: { doc_type: "identity", section: "${sectionName}" }`);
      console.error("");
      continue;
    }

    console.error(`Embedding section: ${sectionName}...`);
    const embedding = await embedText(text);

    const doc: Omit<IdentityDocument, "_id"> = {
      doc_type: "identity",
      section: sectionName,
      sensitivity,
      schema_version: schemaVersion,
      content,
      embedding,
      embedding_model: EMBEDDING_MODEL,
      updated_at: new Date(),
    };

    const db = await getDb();
    const collection = db.collection<IdentityDocument>("identity");

    await collection.updateOne(
      { doc_type: "identity", section: sectionName },
      { $set: doc },
      { upsert: true }
    );

    console.error(`Embedded and upserted: ${sectionName}`);
  }

  if (!dryRun) {
    await closeDb();
    console.error("Done — 4 identity sections loaded into MongoDB");
  } else {
    console.error(`DRY RUN complete — ${SECTIONS.length} sections would be upserted`);
  }
}

main().catch((err: unknown) => {
  console.error("Seed script failed:", err);
  process.exit(1);
});
