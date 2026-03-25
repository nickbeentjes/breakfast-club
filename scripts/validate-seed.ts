import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { join, dirname } from "path";
import Ajv from "ajv/dist/2020.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const schemaPath = join(__dirname, "../src/schema/identity.schema.json");
const seedPath = join(__dirname, "../seed-data/nick-identity.json");

const schema = JSON.parse(readFileSync(schemaPath, "utf-8"));
const seedData = JSON.parse(readFileSync(seedPath, "utf-8"));

const ajv = new Ajv({ strict: false });
const validate = ajv.compile(schema);
const valid = validate(seedData);

if (valid) {
  console.error("VALID: nick-identity.json passes schema validation");
  process.exit(0);
} else {
  console.error("INVALID: nick-identity.json has schema validation errors:");
  for (const error of validate.errors ?? []) {
    console.error(`  ${error.instancePath || "/"}: ${error.message}`);
  }
  process.exit(1);
}
