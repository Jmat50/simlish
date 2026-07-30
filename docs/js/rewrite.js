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
  // mixed: mirror char-by-char against original letter casing
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
 * @param {import("./markov.js").WeightTable} table
 * @param {string} profile
 * @returns {{ display: string, ipa: string }}
 */
function rewriteWord(token, table, profile) {
  const casing = detectCasing(token);
  const normalized = token.normalize("NFKC").toLowerCase();

  if (normalized.length === 1 && SHORT[normalized]) {
    return {
      display: applyCasing(SHORT[normalized], casing, token),
      ipa: normalized,
    };
  }

  const seed = tokenSeed(profile, normalized);
  // Scale target by source length; romanized length often > IPA length
  const targetLen = Math.max(2, Math.round(normalized.length * 0.95));
  const ipa = generateWord(table, seed, {
    targetLen,
    minLen: Math.min(2, normalized.length),
    maxLen: Math.min(18, Math.max(4, normalized.length + 4)),
  });
  let ascii = romanize(ipa);

  // Nudge romanized length toward source when wildly off
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
 * @param {string} text
 * @param {import("./markov.js").WeightTable} table
 * @param {string} profile
 * @returns {{ display: string, ipa: string }}
 */
export function rewriteText(text, table, profile) {
  if (!text) return { display: "", ipa: "" };

  let display = "";
  let ipaOut = "";
  const parts = text.match(TOKEN_RE) || [];

  for (const part of parts) {
    if (/^\p{N}+$/u.test(part) || /^[^\p{L}\p{N}]+$/u.test(part)) {
      display += part;
      ipaOut += part;
      continue;
    }
    // letter word
    const { display: d, ipa } = rewriteWord(part, table, profile);
    display += d;
    ipaOut += ipa;
  }

  return { display, ipa: ipaOut };
}
