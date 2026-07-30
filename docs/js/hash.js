/**
 * @param {string} text
 * @returns {number} unsigned 32-bit FNV-1a
 */
export function fnv1a32(text) {
  let hash = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

/**
 * mulberry32 PRNG — returns a function yielding floats in [0, 1).
 * @param {number} seed
 * @returns {() => number}
 */
export function mulberry32(seed) {
  let t = seed >>> 0;
  return function next() {
    t = (t + 0x6d2b79f5) >>> 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Combine profile id + normalized token into a stable seed.
 * @param {string} profile
 * @param {string} normalizedToken
 */
export function tokenSeed(profile, normalizedToken) {
  return fnv1a32(`${profile}\0${normalizedToken}`);
}
