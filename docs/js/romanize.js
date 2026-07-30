/**
 * English IPA inventory → ASCII approximations for readable “simlish”.
 * Digraphs must be checked before single phones.
 */

const DIGRAPHS = [
  ["dʒ", "j"],
  ["tʃ", "ch"],
  ["tʂ", "ch"],
];

/** @type {Record<string, string>} */
const MAP = {
  a: "a",
  ä: "a",
  ɑ: "ah",
  ɒ: "o",
  æ: "a",
  b: "b",
  β: "v",
  c: "k",
  ɔ: "aw",
  ɕ: "sh",
  ç: "h",
  d: "d",
  ð: "dh",
  e: "ay",
  ə: "uh",
  ɚ: "er",
  ɛ: "eh",
  ɝ: "er",
  f: "f",
  g: "g",
  h: "h",
  ʰ: "",
  i: "ee",
  ɪ: "i",
  ɨ: "i",
  j: "y",
  ʲ: "",
  k: "k",
  l: "l",
  ɫ: "l",
  ɬ: "l",
  m: "m",
  n: "n",
  ŋ: "ng",
  ɲ: "ny",
  o: "o",
  ɸ: "f",
  θ: "th",
  p: "p",
  q: "k",
  r: "r",
  ɹ: "r",
  ɾ: "r",
  ʀ: "r",
  ʁ: "r",
  s: "s",
  ʃ: "sh",
  t: "t",
  u: "oo",
  ʊ: "oo",
  ü: "u",
  v: "v",
  ʌ: "uh",
  ɣ: "g",
  w: "w",
  ʍ: "wh",
  x: "kh",
  χ: "kh",
  y: "y",
  ʎ: "ly",
  z: "z",
  ʒ: "zh",
  ʔ: "",
  ʕ: "",
  "ˈ": "",
  "ˌ": "",
  "ː": "",
  " ": "",
  "-": "",
  ".": "",
};

/**
 * @param {string} ipa
 * @returns {string} printable ASCII (letters only, lower)
 */
export function romanize(ipa) {
  let out = "";
  let i = 0;
  while (i < ipa.length) {
    let matched = false;
    for (const [from, to] of DIGRAPHS) {
      if (ipa.startsWith(from, i)) {
        out += to;
        i += from.length;
        matched = true;
        break;
      }
    }
    if (matched) continue;

    const ch = ipa[i];
    if (Object.prototype.hasOwnProperty.call(MAP, ch)) {
      out += MAP[ch];
    } else if (/[a-zA-Z]/.test(ch)) {
      out += ch.toLowerCase();
    }
    // unknown IPA phones: skip
    i += 1;
  }

  // Collapse empties / odd runs
  out = out.replace(/[^a-z]+/g, "");
  return out || "uh";
}
