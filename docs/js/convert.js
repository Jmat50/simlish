/**
 * Browser port of the English→Simlish converter (sound-alike + rhyme + meter + phrase memory).
 * Loads JSON models from ./models/.
 */

const FUNC = new Set([
  "the", "a", "an", "and", "or", "to", "of", "in", "on", "for",
  "is", "are", "be", "was", "were", "it", "at",
]);

const SIMP = [
  ["ch", "CH"], ["sh", "SH"], ["th", "TH"], ["ph", "F"], ["qu", "KW"],
  ["ng", "NG"], ["ck", "K"], ["oo", "U"], ["ee", "I"], ["ou", "AW"],
  ["ai", "AY"], ["ay", "AY"], ["oi", "OY"], ["oy", "OY"],
];

const VOWELS = new Set("aeiouy");
const NN_THRESHOLD = 0.82;

/** @type {null | {
 *   lexicon: Record<string, string[]>,
 *   phoneMap: Record<string, string[]>,
 *   functionWords: Record<string, string[]>,
 *   shortFillers: {simlish: string, n: number}[],
 *   endingBag: string[],
 *   rhyme: Record<string, {simlish: string, n: number}[]>,
 *   rhymeKeys: Record<string, string>,
 *   meter: {a: number, b: number},
 *   memory: {original: string, simlish: string}[],
 * }} */
let models = null;
/** @type {Promise<typeof models> | null} */
let loadPromise = null;

function tokenize(text) {
  return (text.toLowerCase().match(/[A-Za-z']+/g) || []);
}

function simlishSyllableCount(word) {
  const w = word.toLowerCase();
  if (!w) return 0;
  const groups = w.match(/[aeiouy]+/g) || [];
  let n = Math.max(1, groups.length);
  if (w.endsWith("e") && n > 1 && !w.endsWith("le") && !w.endsWith("ye")) n -= 1;
  return Math.max(1, n);
}

function englishSyllableCount(word) {
  return simlishSyllableCount(word);
}

function lineSyllables(text) {
  return tokenize(text).reduce((s, t) => s + englishSyllableCount(t), 0);
}

function englishRhymeKey(word, m) {
  const w = word.toLowerCase().replace(/^'+|'+$/g, "");
  if (m.rhymeKeys[w]) return m.rhymeKeys[w];
  return w.length >= 3 ? w.slice(-3) : w;
}

function approxPhones(word) {
  const w = word.toLowerCase();
  /** @type {string[]} */
  const phones = [];
  let i = 0;
  while (i < w.length) {
    let matched = false;
    for (const [pat, sym] of SIMP) {
      if (w.startsWith(pat, i)) {
        phones.push(sym);
        i += pat.length;
        matched = true;
        break;
      }
    }
    if (matched) continue;
    const ch = w[i++];
    if (ch === "'" || ch === "-") continue;
    if (VOWELS.has(ch)) {
      phones.push({ a: "A", e: "E", i: "I", o: "O", u: "U", y: "I" }[ch]);
    } else if (/[a-z]/.test(ch)) {
      phones.push(ch.toUpperCase());
    }
  }
  return phones.length ? phones : ["X"];
}

function phoneEditDistance(a, b) {
  const n = a.length;
  const m = b.length;
  let dp = Array.from({ length: m + 1 }, (_, j) => j);
  for (let i = 1; i <= n; i++) {
    const prev = dp;
    dp = [i];
    for (let j = 1; j <= m; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      dp[j] = Math.min(prev[j] + 1, dp[j - 1] + 1, prev[j - 1] + cost);
    }
  }
  return dp[m];
}

function phoneSimilarity(a, b) {
  if (!a.length && !b.length) return 1;
  return 1 - phoneEditDistance(a, b) / Math.max(a.length, b.length, 1);
}

function phonesToSpelling(phones) {
  const special = {
    CH: "ch", SH: "sh", TH: "th", NG: "ng", KW: "qu",
    AY: "ai", OY: "oi", AW: "aw", A: "a", E: "e", I: "i", O: "o", U: "u",
  };
  return phones.filter((p) => p && p !== "X").map((p) => special[p] || p.toLowerCase()).join("");
}

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function weightedPick(entries, field = "simlish") {
  if (!entries?.length) return "";
  /** @type {string[]} */
  const bag = [];
  for (const e of entries) {
    const s = e[field] || e.to || "";
    if (!s || String(s).includes("X")) continue;
    const n = Math.max(1, e.n || 1);
    for (let i = 0; i < n; i++) bag.push(s);
  }
  return bag.length ? pick(bag) : "";
}

function expandWeighted(entries, field) {
  /** @type {string[]} */
  const bag = [];
  for (const e of entries || []) {
    const s = e[field];
    if (!s || String(s).includes("X")) continue;
    const n = Math.max(1, e.n || 1);
    for (let i = 0; i < n; i++) bag.push(s);
  }
  return bag;
}

function onsetLetters(word) {
  const w = word.toLowerCase().replace(/^'+|'+$/g, "");
  if (!w) return "";
  let i = 0;
  while (i < w.length && !VOWELS.has(w[i]) && w[i] !== "'") i++;
  return i ? w.slice(0, i) : w[0];
}

function composeOnsetEnding(enWord, ending) {
  const onset = onsetLetters(enWord);
  const e = (ending || "").toLowerCase().replace(/^'+|'+$/g, "");
  if (!e) return onset || enWord.toLowerCase();
  if (onset && e.startsWith(onset)) return e;
  let j = 0;
  while (j < e.length && !VOWELS.has(e[j]) && e[j] !== "'") j++;
  const coda = j < e.length ? e.slice(j) : e;
  if (!coda) return onset ? onset + e : e;
  return onset ? onset + coda : coda;
}

function transformWord(word, targetSyll, m, preferElide = false) {
  const w = word.toLowerCase();
  if (m.functionWords[w]?.length) return pick(m.functionWords[w]);
  if (m.lexicon[w]?.length) {
    const choice = pick(m.lexicon[w].slice(0, 3));
    if (targetSyll == null || Math.abs(simlishSyllableCount(choice) - targetSyll) <= 1) {
      return choice;
    }
  }
  if (FUNC.has(w)) {
    if (preferElide) return "";
    return weightedPick(m.shortFillers) || "na";
  }
  return generateContent(w, targetSyll, m);
}

function generateContent(w, targetSyll, m) {
  const phones = approxPhones(w);
  const bag = m.endingBag?.length ? m.endingBag : ["na", "la", "oh", "wa", "zor"];
  if (bag.length) {
    let spelling = composeOnsetEnding(w, pick(bag));
    if (targetSyll != null) {
      const sample = [];
      const n = Math.min(8, bag.length);
      const used = new Set();
      while (sample.length < n) {
        const e = pick(bag);
        if (used.has(e)) continue;
        used.add(e);
        sample.push(composeOnsetEnding(w, e));
      }
      spelling = sample.reduce((best, s) =>
        Math.abs(simlishSyllableCount(s) - targetSyll) < Math.abs(simlishSyllableCount(best) - targetSyll)
          ? s
          : best
      );
    }
    if (spelling && phoneSimilarity(phones, approxPhones(spelling)) >= 0.15) {
      return spelling;
    }
  }

  /** @type {string[]} */
  const out = [];
  let i = 0;
  while (i < phones.length) {
    if (i + 1 < phones.length) {
      const big = `${phones[i]}+${phones[i + 1]}`;
      if (m.phoneMap[big]?.length) {
        out.push(...pick(m.phoneMap[big]).split("+").filter((p) => p && p !== "X"));
        i += 2;
        continue;
      }
    }
    if (m.phoneMap[phones[i]]?.length) {
      const p = pick(m.phoneMap[phones[i]]);
      if (p && p !== "X") out.push(p);
    } else if ("AEIOU".includes(phones[i])) {
      out.push(pick(["A", "E", "I", "O", "U"]));
    } else if (phones[i] !== "X") {
      out.push(phones[i]);
    }
    i += 1;
  }
  let spelling = phonesToSpelling(out);
  if (targetSyll != null) {
    const candidates = [spelling];
    for (let k = 0; k < 6; k++) candidates.push(composeOnsetEnding(w, pick(bag)));
    spelling = candidates.reduce((best, s) =>
      Math.abs(simlishSyllableCount(s || w) - targetSyll) < Math.abs(simlishSyllableCount(best || w) - targetSyll)
        ? s
        : best
    );
  }
  if (phoneSimilarity(phones, approxPhones(spelling)) < 0.25 && w[0]) {
    spelling = composeOnsetEnding(w, spelling || pick(bag));
  }
  return spelling || composeOnsetEnding(w, "na");
}

function endingFor(enWord, m) {
  const key = englishRhymeKey(enWord, m);
  const opts = m.rhyme[key] || [];
  if (opts.length) {
    /** @type {string[]} */
    const bag = [];
    for (const o of opts) {
      const n = Math.max(1, o.n || 1);
      for (let i = 0; i < n; i++) bag.push(o.simlish);
    }
    return composeOnsetEnding(enWord, pick(bag));
  }
  return transformWord(enWord, null, m, false);
}

function allocate(tokens, target) {
  if (!tokens.length) return [];
  const weights = tokens.map((t) => Math.max(1, englishSyllableCount(t)));
  const s = weights.reduce((a, b) => a + b, 0);
  const raw = weights.map((w) => Math.max(1, Math.round((target * w) / s)));
  let guard = 0;
  while (raw.reduce((a, b) => a + b, 0) > target && raw.some((x) => x > 1) && guard < 100) {
    for (let i = 0; i < raw.length; i++) {
      if (raw[i] > 1 && raw.reduce((a, b) => a + b, 0) > target) raw[i]--;
    }
    guard++;
  }
  guard = 0;
  while (raw.reduce((a, b) => a + b, 0) < target && guard < 100) {
    raw[raw.reduce((a, b) => a + b, 0) % raw.length]++;
    guard++;
  }
  return raw;
}

function charNgrams(text, n0 = 3, n1 = 5) {
  const t = `  ${text.toLowerCase()}  `;
  /** @type {Map<string, number>} */
  const counts = new Map();
  for (let n = n0; n <= n1; n++) {
    for (let i = 0; i <= t.length - n; i++) {
      const g = t.slice(i, i + n);
      counts.set(g, (counts.get(g) || 0) + 1);
    }
  }
  return counts;
}

function cosineSparse(a, b) {
  let dot = 0;
  let na = 0;
  let nb = 0;
  for (const [, v] of a) na += v * v;
  for (const [, v] of b) nb += v * v;
  for (const [k, v] of a) {
    if (b.has(k)) dot += v * b.get(k);
  }
  if (!na || !nb) return 0;
  return dot / (Math.sqrt(na) * Math.sqrt(nb));
}

function memoryLookup(line, m) {
  const q = charNgrams(line);
  let best = -1;
  let bestSim = 0;
  for (let i = 0; i < m.memory.length; i++) {
    const sim = cosineSparse(q, charNgrams(m.memory[i].original));
    if (sim > bestSim) {
      bestSim = sim;
      best = i;
    }
  }
  if (best >= 0 && bestSim >= NN_THRESHOLD) return m.memory[best].simlish;
  return null;
}

function matchCase(src, dst) {
  if (!dst) return "";
  if (src === src.toUpperCase()) return dst.toUpperCase();
  if (src[0] === src[0].toUpperCase() && src.slice(1) === src.slice(1).toLowerCase()) {
    return dst.charAt(0).toUpperCase() + dst.slice(1).toLowerCase();
  }
  return dst.toLowerCase();
}

function reassemble(original, enTokens, simTokens) {
  const pieces = original.match(/[A-Za-z']+|[^\w\s]+|\s+/g) || [];
  let ti = 0;
  /** @type {string[]} */
  const out = [];
  for (const p of pieces) {
    if (/^[A-Za-z']+$/.test(p)) {
      if (ti < simTokens.length) {
        const sim = simTokens[ti++];
        if (sim) out.push(matchCase(p, sim));
      } else out.push(p);
    } else out.push(p);
  }
  while (ti < simTokens.length) {
    if (simTokens[ti]) out.push(" " + simTokens[ti]);
    ti++;
  }
  return out.join("").replace(/ {2,}/g, " ").trim();
}

function convertLine(line, m) {
  const hit = memoryLookup(line, m);
  if (hit) return line === line.toUpperCase() ? hit.toUpperCase() : hit;
  const tokens = tokenize(line);
  if (!tokens.length) return line;
  const target = Math.max(1, Math.round(m.meter.a * lineSyllables(line) + m.meter.b));
  const budgets = allocate(tokens, target);
  const contentIdx = tokens.map((t, i) => (FUNC.has(t) ? -1 : i)).filter((i) => i >= 0);
  const rhymeI = contentIdx.length ? contentIdx[contentIdx.length - 1] : tokens.length - 1;
  const contentBudget = contentIdx.reduce((s, i) => s + budgets[i], 0);
  const preferElide = contentBudget >= Math.max(1, target - 1);
  const outWords = tokens.map((tok, i) =>
    i === rhymeI ? endingFor(tok, m) : transformWord(tok, budgets[i], m, preferElide)
  );
  return reassemble(line, tokens, outWords);
}

/**
 * @param {string} text
 * @returns {string}
 */
export function convertText(text) {
  if (!models) throw new Error("models not loaded");
  if (!text) return "";
  const parts = text.split(/(\n+)/);
  return parts
    .map((part) => {
      if (!part || /^\s*$/.test(part) || /^[\n]+$/.test(part)) return part;
      return part
        .split(/(?<=[.!?])\s+/)
        .map((ch) => (ch.trim() ? convertLine(ch.trim(), models) : ch))
        .join(" ");
    })
    .join("");
}

export async function loadModels() {
  if (models) return models;
  if (loadPromise) return loadPromise;
  loadPromise = (async () => {
    const files = [
      "soundalike_rules.json",
      "rhyme_classes.json",
      "syllable_templates.json",
      "phrase_memory.json",
      "function_words.json",
      "short_fillers.json",
      "rhyme_keys.json",
    ];
    // Module-relative URLs (not document-relative) so /simlish and /simlish/ both work.
    // no-cache avoids sticky 404s after the models/ path rename.
    const base = new URL("../models/", import.meta.url);
    const [sa, rhyme, meter, memory, fw, shortFillers, rhymeKeys] = await Promise.all(
      files.map(async (f) => {
        const res = await fetch(new URL(f, base), { cache: "no-cache" });
        if (!res.ok) throw new Error(`Failed to load models/${f} (${res.status})`);
        return res.json();
      })
    );
    const lexicon = Object.fromEntries(
      Object.entries(sa.lexicon || {}).map(([k, v]) => [k, v.map((x) => x.simlish)])
    );
    /** @type {string[]} */
    const endingBag = [];
    for (const opts of Object.values(lexicon)) {
      endingBag.push(...opts.slice(0, 2));
    }
    models = {
      lexicon,
      phoneMap: Object.fromEntries(
        Object.entries(sa.phone_map || {}).map(([k, v]) => [k, expandWeighted(v, "to")])
      ),
      functionWords: Object.fromEntries(
        Object.entries(fw || {}).map(([k, v]) => [k, expandWeighted(v, "simlish")])
      ),
      shortFillers: shortFillers || [],
      endingBag: endingBag.length ? endingBag : ["na", "la", "oh", "wa", "zor"],
      rhyme,
      rhymeKeys: rhymeKeys || {},
      meter: { a: meter.a ?? 1, b: meter.b ?? 0 },
      memory: memory || [],
    };
    return models;
  })().catch((err) => {
    loadPromise = null;
    throw err;
  });
  return loadPromise;
}
