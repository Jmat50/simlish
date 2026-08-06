/**
 * Map Simlish orthography to a Kokoro-friendly phoneme string.
 * Uses the same coarse Latin→phone inventory as convert approx_phones, then
 * emits Misaki-style IPA so English G2P does not re-interpret nonsense.
 * Primary stress (ˈ) marks the first vowel nucleus for punchier cadence.
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

/** First vowel / diphthong nucleus for Misaki primary stress placement. */
const IPA_VOWEL_RE = /(?:aʊ|eɪ|aɪ|ɔɪ|oʊ|uː|iː|[ɑɛɪoʊuiæʌəɔ])/u;

/** Common Simlish lexicon overrides (heard orthography → preferred IPA, with stress). */
const LEXICON = {
  hilla: "hˈɪlɑ",
  sho: "ʃˈo",
  vous: "vˈus",
  chika: "tʃˈikɑ",
  sheeky: "ʃˈiki",
  sul: "sˈʊl",
  dag: "dˈɑg",
  nooboo: "nˈubu",
  wawa: "wˈɑwɑ",
  ooh: "ˈu",
  yibba: "jˈɪbɑ",
};

/**
 * Insert Misaki primary stress before the first vowel nucleus.
 * @param {string} ipa
 * @returns {string}
 */
export function withPrimaryStress(ipa) {
  if (!ipa || ipa.includes("ˈ") || ipa.includes("ˌ")) return ipa;
  const m = IPA_VOWEL_RE.exec(ipa);
  if (!m || m.index == null) return ipa;
  return ipa.slice(0, m.index) + "ˈ" + ipa.slice(m.index);
}

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
  return withPrimaryStress(phones.join(""));
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
