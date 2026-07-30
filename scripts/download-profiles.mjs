import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const dest = path.join(root, "data", "profiles");

const candidates = [
  path.join("C:", "Users", "Josh", "Projects", "simlish-research", "simlish", "profiles"),
  process.env.SIMLISH_PROFILES,
].filter(Boolean);

const profiles = ["en_US", "en_UK"];

function copyFrom(srcRoot) {
  for (const p of profiles) {
    const from = path.join(srcRoot, p, "words.csv");
    if (!fs.existsSync(from)) throw new Error(`Missing ${from}`);
    const toDir = path.join(dest, p);
    fs.mkdirSync(toDir, { recursive: true });
    fs.copyFileSync(from, path.join(toDir, "words.csv"));
    console.log(`copied ${p}`);
  }
}

let done = false;
for (const c of candidates) {
  if (c && fs.existsSync(path.join(c, "en_US", "words.csv"))) {
    copyFrom(c);
    done = true;
    break;
  }
}

if (!done) {
  const tmp = path.join(root, "data", "_ipa-dict");
  console.log("Cloning open-dict-data/ipa-dict (shallow)…");
  fs.mkdirSync(path.dirname(tmp), { recursive: true });
  if (!fs.existsSync(path.join(tmp, ".git"))) {
    execSync(`git clone --depth 1 https://github.com/open-dict-data/ipa-dict.git "${tmp}"`, {
      stdio: "inherit",
    });
  }
  // Convert tab-delimited ENTRY\t/IPA/ lines into bare IPA words.csv
  for (const p of profiles) {
    const src = path.join(tmp, "data", `${p}.txt`);
    if (!fs.existsSync(src)) {
      console.error(`No ${src} in ipa-dict`);
      process.exitCode = 1;
      continue;
    }
    const text = fs.readFileSync(src, "utf8");
    const words = [];
    for (const line of text.split(/\r?\n/)) {
      const m = line.match(/\/([^/]+)\//);
      if (m) words.push(m[1].split(",")[0].trim());
    }
    const toDir = path.join(dest, p);
    fs.mkdirSync(toDir, { recursive: true });
    fs.writeFileSync(path.join(toDir, "words.csv"), words.join("\n"), "utf8");
    console.log(`extracted ${p}: ${words.length} words`);
  }
}

console.log("done — run npm run build:weights");
