import { rewriteText } from "./rewrite.js";
import {
  getDictionaryEntryCount,
  lookupSimlishForms,
  openDictionaryDb,
} from "./dictionary-db.js";

/** @type {Map<string, import("./markov.js").WeightTable>} */
const cache = new Map();

const MAX_SHARE_CHARS = 1800;

const els = {
  input: /** @type {HTMLTextAreaElement} */ (document.getElementById("input")),
  output: /** @type {HTMLElement} */ (document.getElementById("output")),
  lang: /** @type {HTMLSelectElement} */ (document.getElementById("lang-select")),
  mode: /** @type {HTMLSelectElement} */ (document.getElementById("mode-select")),
  showIpa: /** @type {HTMLInputElement} */ (document.getElementById("show-ipa")),
  translate: /** @type {HTMLButtonElement} */ (document.getElementById("translate-btn")),
  clear: /** @type {HTMLButtonElement} */ (document.getElementById("clear-btn")),
  copy: /** @type {HTMLButtonElement} */ (document.getElementById("copy-btn")),
  status: /** @type {HTMLElement} */ (document.getElementById("status")),
};

/** @type {{ display: string, ipa: string } | null} */
let lastResult = null;

/**
 * @param {string} profile
 */
async function loadProfile(profile) {
  if (cache.has(profile)) return cache.get(profile);
  els.status.textContent = `Loading ${profile}…`;
  const res = await fetch(`./weights/${profile}.json`, { cache: "force-cache" });
  if (!res.ok) throw new Error(`Failed to load weights for ${profile} (${res.status})`);
  const data = await res.json();
  cache.set(profile, data);
  els.status.textContent = "";
  return data;
}

function renderOutput() {
  if (!lastResult) {
    els.output.textContent = "";
    els.output.classList.remove("has-content", "flash");
    return;
  }
  const text = els.showIpa.checked ? lastResult.ipa : lastResult.display;
  els.output.textContent = text;
  els.output.classList.add("has-content");
  els.output.classList.remove("flash");
  void els.output.offsetWidth;
  els.output.classList.add("flash");
}

function updateShareUrl(text, lang, mode) {
  const url = new URL(window.location.href);
  if (text && text.length <= MAX_SHARE_CHARS) {
    url.searchParams.set("t", text);
  } else {
    url.searchParams.delete("t");
  }
  url.searchParams.set("lang", lang);
  url.searchParams.set("mode", mode);
  if (els.showIpa.checked) url.searchParams.set("ipa", "1");
  else url.searchParams.delete("ipa");
  history.replaceState(null, "", url);
}

async function translate() {
  const text = els.input.value;
  const lang = els.lang.value;
  const mode = els.mode.value === "orthodox" ? "orthodox" : "generative";
  try {
    els.translate.disabled = true;
    const table = await loadProfile(lang);
    /** @type {(key: string) => string[]} */
    let lookupForms = () => [];
    if (mode === "orthodox") {
      els.status.textContent = "Loading dictionary.sqlite…";
      await openDictionaryDb();
      lookupForms = lookupSimlishForms;
    }
    lastResult = rewriteText(text, table, lang, {
      mode,
      lookupForms,
    });
    renderOutput();
    updateShareUrl(text, lang, mode);
    els.output.focus({ preventScroll: true });
    if (!text) {
      els.status.textContent = "";
    } else if (mode === "orthodox") {
      els.status.textContent = `Orthodox · ${getDictionaryEntryCount()} sqlite entries · Markov fallback`;
    } else {
      els.status.textContent = `Generative · ${table.meta?.edgeCount ?? "?"} phoneme edges`;
    }
  } catch (err) {
    console.error(err);
    els.status.textContent = err instanceof Error ? err.message : String(err);
  } finally {
    els.translate.disabled = false;
  }
}

async function copyOutput() {
  const text = els.output.textContent || "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    els.status.textContent = "Copied.";
  } catch {
    els.status.textContent = "Could not copy — select the output manually.";
  }
}

function clearAll() {
  els.input.value = "";
  lastResult = null;
  renderOutput();
  els.status.textContent = "";
  updateShareUrl("", els.lang.value, els.mode.value);
  els.input.focus();
}

function readQuery() {
  const params = new URLSearchParams(window.location.search);
  const lang = params.get("lang");
  if (lang === "en_US" || lang === "en_UK") els.lang.value = lang;
  const mode = params.get("mode");
  if (mode === "orthodox" || mode === "generative") els.mode.value = mode;
  const t = params.get("t");
  if (t != null) els.input.value = t;
  els.showIpa.checked = params.get("ipa") === "1";
}

els.translate.addEventListener("click", () => translate());
els.clear.addEventListener("click", () => clearAll());
els.copy.addEventListener("click", () => copyOutput());
els.showIpa.addEventListener("change", () => {
  renderOutput();
  updateShareUrl(els.input.value, els.lang.value, els.mode.value);
});
els.lang.addEventListener("change", () => {
  if (els.input.value) translate();
});
els.mode.addEventListener("change", () => {
  if (els.input.value) translate();
});

els.input.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    translate();
  }
});

readQuery();
if (els.input.value.trim()) {
  translate();
} else {
  els.status.textContent = "Tip: Ctrl/Cmd+Enter to translate.";
}
