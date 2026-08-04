/**
 * Map Simlish orthography to a Kokoro-friendly phoneme string.
 * Uses the same coarse Latin→phone inventory as v2 approx_phones, then
 * emits Misaki-style IPA so English G2P does not re-interpret nonsense.
 */

const SIMP = [
  ["ch", "tʃ"], ["sh", "ʃ"], ["zh", "ʒ"], ["th", "θ"], ["ph", "f"], ["qu", "kw"],
  ["ng", "ŋ"], ["ck", "k"], ["oo", "uː"], ["ee", "iː"], ["ou", "aʊ"],
  ["ai", "eɪ"], ["ay", "eɪ"], ["oi", "ɔɪ"], ["oy", "ɔɪ"], ["ea", "iː"],
  ["oa", "oʊ"], ["au", "ɔ"], ["aw", "ɔ"], ["ew", "u"], ["igh", "aɪ"],
];

const VOWEL = {
  a: "ɑ", e: "ɛ", i: "ɪ", o: "o", u: "ʊ", y: "i",
};

/** Common Simlish lexicon overrides (heard orthography → preferred IPA). */
const LEXICON = {
  hilla: "hɪlɑ",
  sho: "ʃo",
  vous: "vus",
  chika: "tʃikɑ",
  sheeky: "ʃiki",
  sul: "sʊl",
  dag: "dɑg",
  nooboo: "nubu",
  wawa: "wɑwɑ",
  ooh: "u",
  yibba: "jɪbɑ",
};

/**
 * @param {string} word
 * @returns {string} IPA without slashes
 */
export function wordToIpa(word) {
  const w = word.toLowerCase().replace(/[^a-z']/g, "");
  if (!w) return "";
  if (LEXICON[w]) return LEXICON[w];
  /** @type {string[]} */
  const phones = [];
  let i = 0;
  while (i < w.length) {
    let matched = false;
    for (const [pat, ipa] of SIMP) {
      if (w.startsWith(pat, i)) {
        phones.push(ipa);
        i += pat.length;
        matched = true;
        break;
      }
    }
    if (matched) continue;
    const ch = w[i++];
    if (ch === "'") continue;
    if (VOWEL[ch]) phones.push(VOWEL[ch]);
    else if (/[a-z]/.test(ch)) phones.push(ch);
  }
  return phones.join("");
}

/**
 * Wrap each alphabetic token as Misaki manual IPA: [token](/ipa/)
 * so Kokoro speaks the phones instead of English G2P guesses.
 * @param {string} text
 * @returns {string}
 */
export function simlishToKokoroInput(text) {
  if (!text) return "";
  return text.replace(/[A-Za-z']+/g, (tok) => {
    const ipa = wordToIpa(tok);
    if (!ipa) return tok;
    return `[${tok}](/${ipa}/)`;
  });
}
