import { tokenSeed } from "./hash.js";
import { generateWord } from "./markov.js";
import { romanize } from "./romanize.js";

const TOKEN_RE = /(\p{L}+(?:['’]\p{L}+)?|\p{N}+|[^\p{L}\p{N}]+)/gu;

/** Fixed single-letter fallbacks for ultra-short tokens */
const SHORT = {
  a: "ah",
  i: "ee",
  o: "oh",
  u: "oo",
  y: "yuh",
};

/**
 * @param {string} token
 * @returns {"upper"|"title"|"lower"|"mixed"}
 */
export function detectCasing(token) {
  const letters = token.replace(/[^A-Za-zÀ-ÿ]/g, "");
  if (!letters) return "lower";
  if (letters === letters.toUpperCase()) return "upper";
  if (letters === letters.toLowerCase()) return "lower";
  if (
    letters[0] === letters[0].toUpperCase() &&
    letters.slice(1) === letters.slice(1).toLowerCase()
  ) {
    return "title";
  }
  return "mixed";
}

/**
 * @param {string} text
 * @param {"upper"|"title"|"lower"|"mixed"} casing
 * @param {string} original
 */
export function applyCasing(text, casing, original) {
  if (!text) return text;
  if (casing === "upper") return text.toUpperCase();
  if (casing === "lower") return text.toLowerCase();
  if (casing === "title") {
    return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
  }
  let oi = 0;
  let out = "";
  for (const ch of text) {
    while (oi < original.length && !/[A-Za-zÀ-ÿ]/.test(original[oi])) oi++;
    const src = original[oi] || "";
    oi++;
    if (src && src === src.toUpperCase() && src !== src.toLowerCase()) {
      out += ch.toUpperCase();
    } else {
      out += ch.toLowerCase();
    }
  }
  return out;
}

/**
 * @param {string} token
 * @returns {string}
 */
function normalizeKey(token) {
  return token.normalize("NFKC").toLowerCase().replace(/’/g, "'");
}

/**
 * @param {string[] | null | undefined} forms
 * @returns {string | null}
 */
function pickForm(forms) {
  if (!forms || !forms.length) return null;
  if (forms.length === 1) return forms[0];
  return forms[Math.floor(Math.random() * forms.length)];
}

/**
 * @param {string} token
 * @param {import("./markov.js").WeightTable} table
 * @param {string} profile
 * @returns {{ display: string, ipa: string }}
 */
function rewriteWordGenerative(token, table, profile) {
  const casing = detectCasing(token);
  const normalized = normalizeKey(token);

  if (normalized.length === 1 && SHORT[normalized]) {
    return {
      display: applyCasing(SHORT[normalized], casing, token),
      ipa: normalized,
    };
  }

  const seed = tokenSeed(profile, normalized);
  const targetLen = Math.max(2, Math.round(normalized.length * 0.95));
  const ipa = generateWord(table, seed, {
    targetLen,
    minLen: Math.min(2, normalized.length),
    maxLen: Math.min(18, Math.max(4, normalized.length + 4)),
  });
  let ascii = romanize(ipa);

  if (ascii.length < 2) ascii = romanize(ipa + "ə");
  if (ascii.length > normalized.length + 6) {
    ascii = ascii.slice(0, Math.max(2, normalized.length + 2));
  }

  return {
    display: applyCasing(ascii, casing, token),
    ipa,
  };
}

/**
 * @param {string} token
 * @param {import("./markov.js").WeightTable} table
 * @param {string} profile
 * @param {(key: string) => string[]} lookupForms
 * @returns {{ display: string, ipa: string }}
 */
function rewriteWordOrthodox(token, table, profile, lookupForms) {
  const casing = detectCasing(token);
  const key = normalizeKey(token);
  const hit = pickForm(lookupForms(key));
  if (hit) {
    return {
      display: applyCasing(hit, casing, token),
      ipa: hit,
    };
  }
  return rewriteWordGenerative(token, table, profile);
}

/**
 * @param {string} text
 * @param {import("./markov.js").WeightTable} table
 * @param {string} profile
 * @param {{
 *   mode?: "generative" | "orthodox",
 *   lookupForms?: (key: string) => string[],
 * }} [options]
 * @returns {{ display: string, ipa: string }}
 */
export function rewriteText(text, table, profile, options = {}) {
  if (!text) return { display: "", ipa: "" };

  const mode = options.mode === "orthodox" ? "orthodox" : "generative";
  const lookupForms = options.lookupForms ?? (() => []);

  let display = "";
  let ipaOut = "";
  const parts = text.match(TOKEN_RE) || [];

  for (const part of parts) {
    if (/^\p{N}+$/u.test(part) || /^[^\p{L}\p{N}]+$/u.test(part)) {
      display += part;
      ipaOut += part;
      continue;
    }
    const result =
      mode === "orthodox"
        ? rewriteWordOrthodox(part, table, profile, lookupForms)
        : rewriteWordGenerative(part, table, profile);
    display += result.display;
    ipaOut += result.ipa;
  }

  return { display, ipa: ipaOut };
}
