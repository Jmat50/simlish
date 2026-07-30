/**
 * Sync DICTIONARY/dictionary.sqlite → docs/dictionary.sqlite and refresh
 * vendored sql.js wasm assets from node_modules when present.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");

const srcDb = path.join(root, "DICTIONARY", "dictionary.sqlite");
const destDb = path.join(root, "docs", "dictionary.sqlite");
const vendorDir = path.join(root, "docs", "vendor", "sql.js");
const nmDist = path.join(root, "node_modules", "sql.js", "dist");

if (!fs.existsSync(srcDb)) {
  console.error(`missing ${srcDb}`);
  process.exit(1);
}

fs.mkdirSync(path.dirname(destDb), { recursive: true });
fs.copyFileSync(srcDb, destDb);
console.log(`copied ${path.relative(root, srcDb)} → ${path.relative(root, destDb)}`);

if (fs.existsSync(nmDist)) {
  fs.mkdirSync(vendorDir, { recursive: true });
  for (const name of ["sql-wasm.js", "sql-wasm.wasm"]) {
    const from = path.join(nmDist, name);
    const to = path.join(vendorDir, name);
    if (!fs.existsSync(from)) {
      console.warn(`skip missing ${from}`);
      continue;
    }
    fs.copyFileSync(from, to);
    console.log(`vendored ${name}`);
  }
} else {
  console.log("node_modules/sql.js not found — keeping existing docs/vendor/sql.js");
}

const jsonLegacy = path.join(root, "docs", "dictionary.json");
if (fs.existsSync(jsonLegacy)) {
  fs.unlinkSync(jsonLegacy);
  console.log("removed legacy docs/dictionary.json");
}
