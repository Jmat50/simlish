import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");

const { generateWord } = await import(
  pathToFileURL(path.join(root, "docs/js/markov.js")).href
);
const { romanize } = await import(
  pathToFileURL(path.join(root, "docs/js/romanize.js")).href
);
const { rewriteText, detectCasing, applyCasing } = await import(
  pathToFileURL(path.join(root, "docs/js/rewrite.js")).href
);
const { tokenSeed } = await import(
  pathToFileURL(path.join(root, "docs/js/hash.js")).href
);

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

const table = JSON.parse(
  fs.readFileSync(path.join(root, "docs/weights/en_US.json"), "utf8")
);

// 100 generations
for (let i = 0; i < 100; i++) {
  const w = generateWord(table, (i * 2654435761) >>> 0, { targetLen: 5 });
  assert(w.length > 0, `empty word at ${i}`);
  const ascii = romanize(w);
  assert(/^[a-z]+$/.test(ascii), `romanize not ascii: ${w} → ${ascii}`);
}

// Determinism
const seed = tokenSeed("en_US", "hello");
const a = generateWord(table, seed, { targetLen: 5 });
for (let i = 0; i < 20; i++) {
  assert(generateWord(table, seed, { targetLen: 5 }) === a, "nondeterministic");
}

// Rewrite casing + punct
const { display } = rewriteText("Hello, world!", table, "en_US");
assert(/^[A-Z][a-z]+, [a-z]+!$/.test(display), `rewrite fixture failed: ${display}`);

assert(detectCasing("HELLO") === "upper", "upper");
assert(detectCasing("Hello") === "title", "title");
assert(applyCasing("sim", "title", "Hi") === "Sim", "title apply");

console.log("smoke ok");
console.log("sample:", rewriteText("Hello, world!", table, "en_US"));
