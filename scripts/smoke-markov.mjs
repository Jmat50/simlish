import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import initSqlJs from "sql.js";

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

for (let i = 0; i < 100; i++) {
  const w = generateWord(table, (i * 2654435761) >>> 0, { targetLen: 5 });
  assert(w.length > 0, `empty word at ${i}`);
  const ascii = romanize(w);
  assert(/^[a-z]+$/.test(ascii), `romanize not ascii: ${w} → ${ascii}`);
}

const seed = tokenSeed("en_US", "hello");
const a = generateWord(table, seed, { targetLen: 5 });
for (let i = 0; i < 20; i++) {
  assert(generateWord(table, seed, { targetLen: 5 }) === a, "nondeterministic");
}

const { display } = rewriteText("Hello, world!", table, "en_US");
assert(/^[A-Z][a-z]+, [a-z]+!$/.test(display), `rewrite fixture failed: ${display}`);

assert(detectCasing("HELLO") === "upper", "upper");
assert(detectCasing("Hello") === "title", "title");
assert(applyCasing("sim", "title", "Hi") === "Sim", "title apply");

// sql.js read-only open of docs/dictionary.sqlite
const wasmPath = path.join(root, "node_modules", "sql.js", "dist");
const SQL = await initSqlJs({
  locateFile: (file) => path.join(wasmPath, file),
});
const dbBuf = fs.readFileSync(path.join(root, "docs", "dictionary.sqlite"));
const db = new SQL.Database(dbBuf);
try {
  db.run("PRAGMA query_only = ON");
} catch {
  /* optional */
}
const stmt = db.prepare(`
  SELECT simlish_1, simlish_2, simlish_3, simlish_4, simlish_5,
         simlish_6, simlish_7, simlish_8, simlish_9, simlish_10
  FROM dictionary WHERE original_word = ?
`);
stmt.bind(["smile"]);
assert(stmt.step(), "smile missing from dictionary.sqlite");
const smileRow = stmt.getAsObject();
stmt.free();
const smileForms = Object.values(smileRow).filter((v) => typeof v === "string" && v);
assert(smileForms.includes("asmil") || smileForms.length > 0, "smile forms empty");

const orth = rewriteText("smile pressure xyzzy", table, "en_US", {
  mode: "orthodox",
  lookupForms: (key) => {
    const s = db.prepare(`
      SELECT simlish_1, simlish_2, simlish_3, simlish_4, simlish_5,
             simlish_6, simlish_7, simlish_8, simlish_9, simlish_10
      FROM dictionary WHERE original_word = ?
    `);
    s.bind([key]);
    /** @type {string[]} */
    const forms = [];
    if (s.step()) {
      const row = s.getAsObject();
      for (let i = 1; i <= 10; i++) {
        const v = row[`simlish_${i}`];
        if (typeof v === "string" && v) forms.push(v.toLowerCase());
      }
    }
    s.free();
    return forms;
  },
});
assert(/asmil|akawua|smurf/i.test(orth.display.split(/\s+/)[0]), `orthodox smile: ${orth.display}`);
assert(/westesho/i.test(orth.display), `orthodox pressure: ${orth.display}`);
db.close();

console.log("smoke ok");
console.log("sample:", rewriteText("Hello, world!", table, "en_US"));
console.log("orthodox sample:", orth);
