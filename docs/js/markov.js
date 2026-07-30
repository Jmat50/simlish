import { mulberry32 } from "./hash.js";

/**
 * @typedef {{ meta: object, start: string, end: string, t: Record<string, [string, number][]> }} WeightTable
 */

/**
 * Roulette-wheel sample from sparse [symbol, probability] rows.
 * @param {[string, number][]} edges
 * @param {() => number} rand
 */
function pick(edges, rand) {
  if (!edges || edges.length === 0) return null;
  let r = rand();
  let acc = 0;
  for (const [sym, p] of edges) {
    acc += p;
    if (r <= acc) return sym;
  }
  return edges[edges.length - 1][0];
}

/**
 * Generate one IPA word with soft length targeting.
 * @param {WeightTable} table
 * @param {number} seed
 * @param {{ targetLen?: number, minLen?: number, maxLen?: number, maxSteps?: number }} [opts]
 * @returns {string}
 */
export function generateWord(table, seed, opts = {}) {
  const {
    targetLen = 5,
    minLen = 2,
    maxLen = 18,
    maxSteps = 48,
  } = opts;

  const L = Math.max(minLen, Math.min(maxLen, Math.round(targetLen)));
  const start = table.start || "^";
  const end = table.end || "$";
  const t = table.t;

  let best = "";
  // A few attempts with advanced seeds for better length fit
  for (let attempt = 0; attempt < 6; attempt++) {
    const rand = mulberry32((seed + attempt * 0x9e3779b9) >>> 0);
    let word = "";
    let state = start;

    for (let step = 0; step < maxSteps; step++) {
      let edges = t[state];
      if (!edges || edges.length === 0) {
        // Fallback: try start row or force end
        edges = t[start];
        if (!edges || edges.length === 0) break;
      }

      // Soft-bias toward end once we hit target length
      let next;
      if (word.length >= L) {
        const endEdge = edges.find(([s]) => s === end);
        if (endEdge && rand() < Math.min(0.85, 0.35 + (word.length - L) * 0.15)) {
          next = end;
        } else {
          next = pick(edges, rand);
        }
      } else if (word.length < Math.max(minLen, L - 1)) {
        // Discourage early termination
        const nonEnd = edges.filter(([s]) => s !== end);
        next = pick(nonEnd.length ? nonEnd : edges, rand);
      } else {
        next = pick(edges, rand);
      }

      if (next == null || next === end) break;
      word += next;
      state = next;

      if (word.length >= maxLen) break;
    }

    if (word.length >= minLen) {
      const dist = Math.abs(word.length - L);
      const bestDist = best ? Math.abs(best.length - L) : Infinity;
      if (!best || dist < bestDist) best = word;
      if (dist <= 2) return word;
    } else if (!best && word.length > 0) {
      best = word;
    }
  }

  return best || "ə";
}
