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
  return phones.map((p) => special[p] || p.toLowerCase()).join("");
}

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function transformWord(word, targetSyll, m) {
  const w = word.toLowerCase();
  if (m.functionWords[w]?.length) return pick(m.functionWords[w]);
  if (m.lexicon[w]?.length) {
    const choice = pick(m.lexicon[w].slice(0, 3));
    if (targetSyll == null || Math.abs(simlishSyllableCount(choice) - targetSyll) <= 1) {
      return choice;
    }
  }
  const phones = approxPhones(w);
  /** @type {string[]} */
  const out = [];
  let i = 0;
  while (i < phones.length) {
    if (i + 1 < phones.length) {
      const big = `${phones[i]}+${phones[i + 1]}`;
      if (m.phoneMap[big]?.length) {
        out.push(...pick(m.phoneMap[big]).split("+"));
        i += 2;
        continue;
      }
    }
    if (m.phoneMap[phones[i]]?.length) {
      out.push(pick(m.phoneMap[phones[i]]));
    } else if ("AEIOU".includes(phones[i])) {
      out.push(pick(["A", "E", "I", "O", "U"]));
    } else {
      out.push(phones[i]);
    }
    i += 1;
  }
  let spelling = phonesToSpelling(out);
  if (targetSyll != null) {
    let guard = 0;
    while (simlishSyllableCount(spelling) < targetSyll && guard < 12) {
      spelling += pick(["ba", "di", "ko", "su", "la"]);
      guard++;
    }
    guard = 0;
    while (simlishSyllableCount(spelling) > targetSyll + 1 && spelling.length > 2 && guard < 24) {
      spelling = spelling.slice(0, -1);
      guard++;
    }
  }
  if (phoneSimilarity(phones, approxPhones(spelling)) < 0.25 && w[0]) {
    spelling = w[0] + spelling.slice(1);
  }
  return spelling || w;
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
    return pick(bag);
  }
  return transformWord(enWord, null, m);
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
        out.push(matchCase(p, simTokens[ti]));
        ti++;
      } else out.push(p);
    } else out.push(p);
  }
  while (ti < simTokens.length) {
    out.push(" " + simTokens[ti++]);
  }
  return out.join("");
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
  const outWords = tokens.map((tok, i) =>
    i === rhymeI ? endingFor(tok, m) : transformWord(tok, budgets[i], m)
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
      "rhyme_keys.json",
    ];
    const [sa, rhyme, meter, memory, fw, rhymeKeys] = await Promise.all(
      files.map(async (f) => {
        const res = await fetch(`./models/${f}`, { cache: "force-cache" });
        if (!res.ok) throw new Error(`Failed to load models/${f} (${res.status})`);
        return res.json();
      })
    );
    models = {
      lexicon: Object.fromEntries(
        Object.entries(sa.lexicon || {}).map(([k, v]) => [k, v.map((x) => x.simlish)])
      ),
      phoneMap: Object.fromEntries(
        Object.entries(sa.phone_map || {}).map(([k, v]) => [k, v.map((x) => x.to)])
      ),
      functionWords: Object.fromEntries(
        Object.entries(fw || {}).map(([k, v]) => [k, v.map((x) => x.simlish)])
      ),
      rhyme,
      rhymeKeys: rhymeKeys || {},
      meter: { a: meter.a ?? 1, b: meter.b ?? 0 },
      memory: memory || [],
    };
    return models;
  })();
  return loadPromise;
}
