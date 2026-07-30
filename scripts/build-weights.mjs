import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const profiles = ["en_US", "en_UK"];
const START = "^";
const END = "$";
const MIN_PROB = 1e-6;

/**
 * Discover inventory from corpus, drop ultra-rare junk.
 * @param {string[]} words
 */
function discoverAllowlist(words) {
  /** @type {Map<string, number>} */
  const counts = new Map();
  for (const w of words) {
    for (const ch of w) {
      counts.set(ch, (counts.get(ch) || 0) + 1);
    }
  }
  // Keep phones seen at least a handful of times
  const allow = new Set();
  for (const [ch, n] of counts) {
    if (n >= 3 && ch !== START && ch !== END) allow.add(ch);
  }
  return allow;
}

/**
 * @param {string} profile
 * @param {string} csvPath
 */
function buildProfile(profile, csvPath) {
  const raw = fs.readFileSync(csvPath, "utf8");
  const words = raw
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  const allow = discoverAllowlist(words);

  /** @type {Map<string, Map<string, number>>} */
  const counts = new Map();

  const bump = (from, to) => {
    if (!counts.has(from)) counts.set(from, new Map());
    const row = counts.get(from);
    row.set(to, (row.get(to) || 0) + 1);
  };

  let usedWords = 0;
  for (const word of words) {
    // Filter to allowlist phones only
    let cleaned = "";
    for (const ch of word) {
      if (allow.has(ch)) cleaned += ch;
    }
    if (!cleaned) continue;
    usedWords += 1;
    const seq = START + cleaned + END;
    for (let i = 1; i < seq.length; i++) {
      bump(seq[i - 1], seq[i]);
    }
  }

  /** @type {Record<string, [string, number][]>} */
  const t = {};
  let edgeCount = 0;

  for (const [from, row] of counts) {
    let sum = 0;
    for (const n of row.values()) sum += n;
    if (sum === 0) continue;
    /** @type {[string, number][]} */
    const edges = [];
    for (const [to, n] of row) {
      const p = n / sum;
      if (p >= MIN_PROB) edges.push([to, Number(p.toFixed(6))]);
    }
    edges.sort((a, b) => b[1] - a[1]);
    // Renormalize after prune
    const pSum = edges.reduce((s, [, p]) => s + p, 0);
    if (pSum > 0 && Math.abs(pSum - 1) > 1e-6) {
      for (const e of edges) e[1] = Number((e[1] / pSum).toFixed(6));
    }
    t[from] = edges;
    edgeCount += edges.length;
  }

  return {
    meta: {
      profile,
      order: 1,
      source: "open-dict-data/ipa-dict",
      wordCount: usedWords,
      edgeCount,
      inventorySize: allow.size,
      builtAt: new Date().toISOString(),
    },
    start: START,
    end: END,
    t,
  };
}

function main() {
  const outDir = path.join(root, "docs", "weights");
  fs.mkdirSync(outDir, { recursive: true });

  for (const profile of profiles) {
    const csvPath = path.join(root, "data", "profiles", profile, "words.csv");
    if (!fs.existsSync(csvPath)) {
      console.error(`Missing ${csvPath}`);
      process.exitCode = 1;
      continue;
    }
    const table = buildProfile(profile, csvPath);
    const outPath = path.join(outDir, `${profile}.json`);
    fs.writeFileSync(outPath, JSON.stringify(table), "utf8");
    const kb = (fs.statSync(outPath).size / 1024).toFixed(1);
    console.log(
      `${profile}: words=${table.meta.wordCount} edges=${table.meta.edgeCount} → ${outPath} (${kb} KB)`
    );
  }
}

main();
