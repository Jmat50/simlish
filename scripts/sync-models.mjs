/**
 * Copy induced engine model JSON into docs/models for the Pages site.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");

const src = path.join(root, "engine", "models");
const dest = path.join(root, "docs", "models");
const files = [
  "soundalike_rules.json",
  "rhyme_classes.json",
  "syllable_templates.json",
  "phrase_memory.json",
  "function_words.json",
];

if (!fs.existsSync(src)) {
  console.log("engine/models not found — keeping existing docs/models");
  process.exit(0);
}

fs.mkdirSync(dest, { recursive: true });
for (const name of files) {
  const from = path.join(src, name);
  if (!fs.existsSync(from)) {
    console.warn(`skip missing ${from}`);
    continue;
  }
  fs.copyFileSync(from, path.join(dest, name));
  console.log(`copied model ${name}`);
}
