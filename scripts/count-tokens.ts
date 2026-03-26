import { readFileSync } from "fs";
import { resolve } from "path";

const BUDGET = 600;
const MULTIPLIER = 1.3;

const filePath = process.argv[2] ?? "SKILL.md";
const absolutePath = resolve(filePath);

let content: string;
try {
  content = readFileSync(absolutePath, "utf-8");
} catch (err) {
  console.error(`Error: Could not read file "${filePath}"`);
  console.error(err);
  process.exit(1);
}

const words = content.split(/\s+/).filter((w) => w.length > 0).length;
const estimatedTokens = Math.ceil(words * MULTIPLIER);
const status = estimatedTokens < BUDGET ? "PASS" : "FAIL";

console.error(`File: ${filePath}`);
console.error(`Words: ${words}`);
console.error(`Estimated tokens: ${estimatedTokens}`);
console.error(`Budget: ${BUDGET}`);
console.error(`Status: ${status}`);

process.exit(status === "PASS" ? 0 : 1);
