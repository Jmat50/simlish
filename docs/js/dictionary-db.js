/**
 * Read-only Orthodoxy dictionary backed by dictionary.sqlite via sql.js.
 * The sqlite file under docs/ is the single source of truth (no JSON export).
 */

/** @type {import("sql.js").SqlJsStatic | null} */
let SQL = null;
/** @type {import("sql.js").Database | null} */
let db = null;
/** @type {import("sql.js").Statement | null} */
let lookupStmt = null;
/** @type {Promise<{ entryCount: number }> | null} */
let openPromise = null;
let entryCount = 0;

const WASM_DIR = new URL("../vendor/sql.js/", import.meta.url).href;
const DB_URL = new URL("../dictionary.sqlite", import.meta.url).href;

/**
 * Load sql.js init function in the browser (UMD script, not ESM).
 * @returns {Promise<(config?: object) => Promise<import("sql.js").SqlJsStatic>>}
 */
function loadInitSqlJs() {
  // @ts-ignore — classic script sets a browser global
  if (typeof globalThis.initSqlJs === "function") {
    // @ts-ignore
    return Promise.resolve(globalThis.initSqlJs);
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = new URL("sql-wasm.js", WASM_DIR).href;
    script.async = true;
    script.onload = () => {
      // @ts-ignore
      if (typeof globalThis.initSqlJs !== "function") {
        reject(new Error("sql.js failed to expose initSqlJs"));
        return;
      }
      // @ts-ignore
      resolve(globalThis.initSqlJs);
    };
    script.onerror = () => reject(new Error("Failed to load sql-wasm.js"));
    document.head.appendChild(script);
  });
}

/**
 * Open (or reuse) the read-only lyric dictionary.
 * @returns {Promise<{ entryCount: number }>}
 */
export async function openDictionaryDb() {
  if (db) return { entryCount };
  if (openPromise) return openPromise;

  openPromise = (async () => {
    const initSqlJs = await loadInitSqlJs();
    const [sqlModule, buf] = await Promise.all([
      initSqlJs({
        locateFile: (file) => new URL(file, WASM_DIR).href,
      }),
      fetch(DB_URL, { cache: "force-cache" }).then(async (res) => {
        if (!res.ok) throw new Error(`Failed to load dictionary.sqlite (${res.status})`);
        return res.arrayBuffer();
      }),
    ]);
    SQL = sqlModule;
    db = new SQL.Database(new Uint8Array(buf));
    try {
      db.run("PRAGMA query_only = ON");
    } catch {
      // Older sql.js / SQLite builds may lack query_only; ignore.
    }
    const countRow = db.exec("SELECT COUNT(*) AS c FROM dictionary");
    entryCount = countRow[0]?.values?.[0]?.[0] ?? 0;
    lookupStmt = db.prepare(`
      SELECT simlish_1, simlish_2, simlish_3, simlish_4, simlish_5,
             simlish_6, simlish_7, simlish_8, simlish_9, simlish_10,
             simlish_extra
      FROM dictionary
      WHERE original_word = ?
    `);
    return { entryCount };
  })();

  try {
    return await openPromise;
  } catch (err) {
    openPromise = null;
    throw err;
  }
}

/**
 * @param {string} key normalized lowercase English word
 * @returns {string[]}
 */
export function lookupSimlishForms(key) {
  if (!db || !lookupStmt || !key) return [];
  lookupStmt.bind([key]);
  /** @type {string[]} */
  const forms = [];
  if (lookupStmt.step()) {
    const row = lookupStmt.getAsObject();
    for (let i = 1; i <= 10; i++) {
      const v = row[`simlish_${i}`];
      if (typeof v === "string" && v) forms.push(v);
    }
    const extra = row.simlish_extra;
    if (typeof extra === "string" && extra) {
      try {
        const parsed = JSON.parse(extra);
        if (Array.isArray(parsed)) {
          for (const x of parsed) {
            if (typeof x === "string" && x) forms.push(x);
          }
        }
      } catch {
        // ignore bad extra JSON
      }
    }
  }
  lookupStmt.reset();
  // dedupe preserve order
  const seen = new Set();
  /** @type {string[]} */
  const uniq = [];
  for (const f of forms) {
    const k = f.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    uniq.push(f.toLowerCase());
  }
  return uniq;
}

export function getDictionaryEntryCount() {
  return entryCount;
}
