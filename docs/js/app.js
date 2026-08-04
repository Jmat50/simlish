import { rewriteText } from "./rewrite.js";
import {
  getDictionaryEntryCount,
  lookupSimlishForms,
  openDictionaryDb,
} from "./dictionary-db.js";
import { convertTextV2, loadV2Models } from "./v2-convert.js";
import { speakSimlish, stopSpeaking } from "./speak.js";

/** @type {Map<string, import("./markov.js").WeightTable>} */
const cache = new Map();

const MAX_SHARE_CHARS = 1800;

const els = {
  input: /** @type {HTMLTextAreaElement} */ (document.getElementById("input")),
  output: /** @type {HTMLElement} */ (document.getElementById("output")),
  lang: /** @type {HTMLSelectElement} */ (document.getElementById("lang-select")),
  mode: /** @type {HTMLSelectElement} */ (document.getElementById("mode-select")),
  engine: /** @type {HTMLInputElement} */ (document.getElementById("engine-toggle")),
  toolbar: /** @type {HTMLElement} */ (document.querySelector(".toolbar")),
  showIpa: /** @type {HTMLInputElement} */ (document.getElementById("show-ipa")),
  translate: /** @type {HTMLButtonElement} */ (document.getElementById("translate-btn")),
  clear: /** @type {HTMLButtonElement} */ (document.getElementById("clear-btn")),
  copy: /** @type {HTMLButtonElement} */ (document.getElementById("copy-btn")),
  speak: /** @type {HTMLButtonElement} */ (document.getElementById("speak-btn")),
  stopSpeak: /** @type {HTMLButtonElement} */ (document.getElementById("stop-speak-btn")),
  status: /** @type {HTMLElement} */ (document.getElementById("status")),
};

/** @type {{ display: string, ipa: string } | null} */
let lastResult = null;

function isV2() {
  return els.engine.checked;
}

function syncEngineUi() {
  const v2 = isV2();
  els.engine.setAttribute("aria-checked", v2 ? "true" : "false");
  els.toolbar.classList.toggle("is-engine-v2", v2);
  if (v2) {
    els.showIpa.checked = false;
  }
}

function syncSpeakUi(speaking) {
  els.stopSpeak.hidden = !speaking;
  els.speak.disabled = speaking || !(lastResult?.display);
}

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
    syncSpeakUi(false);
    return;
  }
  const text =
    !isV2() && els.showIpa.checked ? lastResult.ipa : lastResult.display;
  els.output.textContent = text;
  els.output.classList.add("has-content");
  els.output.classList.remove("flash");
  void els.output.offsetWidth;
  els.output.classList.add("flash");
  syncSpeakUi(false);
}

function updateShareUrl(text, lang, mode, engine) {
  const url = new URL(window.location.href);
  if (text && text.length <= MAX_SHARE_CHARS) {
    url.searchParams.set("t", text);
  } else {
    url.searchParams.delete("t");
  }
  url.searchParams.set("lang", lang);
  url.searchParams.set("mode", mode);
  url.searchParams.set("engine", engine);
  if (!isV2() && els.showIpa.checked) url.searchParams.set("ipa", "1");
  else url.searchParams.delete("ipa");
  history.replaceState(null, "", url);
}

async function translate() {
  const text = els.input.value;
  const lang = els.lang.value;
  const mode = els.mode.value === "orthodox" ? "orthodox" : "generative";
  const engine = isV2() ? "v2" : "v1";
  try {
    els.translate.disabled = true;
    if (engine === "v2") {
      els.status.textContent = "Loading v2 models…";
      await loadV2Models();
      const display = convertTextV2(text);
      lastResult = { display, ipa: display };
      renderOutput();
      updateShareUrl(text, lang, mode, engine);
      els.output.focus({ preventScroll: true });
      els.status.textContent = text
        ? "v2 · sound-alike + rhyme + meter + phrase memory"
        : "";
      return;
    }

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
    updateShareUrl(text, lang, mode, engine);
    els.output.focus({ preventScroll: true });
    if (!text) {
      els.status.textContent = "";
    } else if (mode === "orthodox") {
      els.status.textContent = `v1 Orthodox · ${getDictionaryEntryCount()} sqlite entries · Markov fallback`;
    } else {
      els.status.textContent = `v1 Generative · ${table.meta?.edgeCount ?? "?"} phoneme edges`;
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

async function onSpeak() {
  const text = lastResult?.display || els.output.textContent || "";
  if (!text.trim()) return;
  try {
    syncSpeakUi(true);
    await speakSimlish(text, {
      onStatus: (msg) => {
        els.status.textContent = msg;
      },
    });
  } catch (err) {
    console.error(err);
    els.status.textContent = err instanceof Error ? err.message : String(err);
    syncSpeakUi(false);
  }
}

function onStopSpeak() {
  stopSpeaking();
  syncSpeakUi(false);
  els.status.textContent = "Stopped.";
}

function clearAll() {
  stopSpeaking();
  els.input.value = "";
  lastResult = null;
  renderOutput();
  els.status.textContent = "";
  updateShareUrl("", els.lang.value, els.mode.value, isV2() ? "v2" : "v1");
  els.input.focus();
}

function readQuery() {
  const params = new URLSearchParams(window.location.search);
  const lang = params.get("lang");
  if (lang === "en_US" || lang === "en_UK") els.lang.value = lang;
  const mode = params.get("mode");
  if (mode === "orthodox" || mode === "generative") els.mode.value = mode;
  const engine = params.get("engine");
  els.engine.checked = engine !== "v1";
  const t = params.get("t");
  if (t != null) els.input.value = t;
  els.showIpa.checked = params.get("ipa") === "1" && !isV2();
  syncEngineUi();
}

els.translate.addEventListener("click", () => translate());
els.clear.addEventListener("click", () => clearAll());
els.copy.addEventListener("click", () => copyOutput());
els.speak.addEventListener("click", () => onSpeak());
els.stopSpeak.addEventListener("click", () => onStopSpeak());
els.showIpa.addEventListener("change", () => {
  renderOutput();
  updateShareUrl(els.input.value, els.lang.value, els.mode.value, isV2() ? "v2" : "v1");
});
els.lang.addEventListener("change", () => {
  if (els.input.value) translate();
});
els.mode.addEventListener("change", () => {
  if (els.input.value) translate();
});
els.engine.addEventListener("change", () => {
  syncEngineUi();
  if (els.input.value) translate();
  else {
    updateShareUrl("", els.lang.value, els.mode.value, isV2() ? "v2" : "v1");
    els.status.textContent = isV2()
      ? "Tip: Ctrl/Cmd+Enter to translate (v2)."
      : "Tip: Ctrl/Cmd+Enter to translate (v1).";
  }
});

els.input.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    translate();
  }
});

readQuery();
syncSpeakUi(false);
if (els.input.value.trim()) {
  translate();
} else {
  els.status.textContent = isV2()
    ? "Tip: Ctrl/Cmd+Enter to translate (v2)."
    : "Tip: Ctrl/Cmd+Enter to translate (v1).";
}
