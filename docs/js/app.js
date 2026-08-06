import { convertText, loadModels } from "./convert.js?v=20260804a";
import { ensureTts, speakSimlish, stopSpeaking } from "./speak.js?v=20260806b";

const MAX_SHARE_CHARS = 1800;
const THEME_KEY = "simlish-theme";
const THEMES = new Set(["vanilla", "suburbia", "latenight"]);
const DEFAULT_THEME = "vanilla";

const els = {
  input: /** @type {HTMLTextAreaElement} */ (document.getElementById("input")),
  output: /** @type {HTMLElement} */ (document.getElementById("output")),
  translate: /** @type {HTMLButtonElement} */ (document.getElementById("translate-btn")),
  clear: /** @type {HTMLButtonElement} */ (document.getElementById("clear-btn")),
  copy: /** @type {HTMLButtonElement} */ (document.getElementById("copy-btn")),
  speak: /** @type {HTMLButtonElement} */ (document.getElementById("speak-btn")),
  stopSpeak: /** @type {HTMLButtonElement} */ (document.getElementById("stop-speak-btn")),
  status: /** @type {HTMLElement} */ (document.getElementById("status")),
  themeSelect: /** @type {HTMLSelectElement | null} */ (document.getElementById("theme-select")),
  musicToggle: /** @type {HTMLInputElement | null} */ (document.getElementById("music-toggle")),
  bgMusic: /** @type {HTMLAudioElement | null} */ (document.getElementById("bg-music")),
};

/** @param {string} theme */
function applyTheme(theme) {
  const next = THEMES.has(theme) ? theme : DEFAULT_THEME;
  document.documentElement.setAttribute("data-theme", next);
  if (els.themeSelect && els.themeSelect.value !== next) {
    els.themeSelect.value = next;
  }
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch {
    /* private mode / blocked storage */
  }
}

function initTheme() {
  let stored = "";
  try {
    stored = localStorage.getItem(THEME_KEY) || "";
  } catch {
    stored = "";
  }
  const current = document.documentElement.getAttribute("data-theme") || DEFAULT_THEME;
  const theme = THEMES.has(stored) ? stored : current;
  applyTheme(theme);
  if (els.themeSelect) {
    els.themeSelect.addEventListener("change", () => {
      applyTheme(els.themeSelect.value);
    });
  }
}

function syncMusicUi(on) {
  if (!els.musicToggle) return;
  els.musicToggle.checked = on;
  els.musicToggle.setAttribute("aria-checked", on ? "true" : "false");
}

async function setMusicEnabled(on) {
  syncMusicUi(on);
  if (!els.bgMusic) return;
  if (on) {
    try {
      els.bgMusic.volume = 0.45;
      await els.bgMusic.play();
    } catch (err) {
      console.error(err);
      syncMusicUi(false);
      if (els.status) {
        els.status.textContent = "Could not play music — click Music again after interacting.";
      }
    }
  } else {
    els.bgMusic.pause();
  }
}

function initMusic() {
  if (!els.musicToggle || !els.bgMusic) return;
  // Default off — do not persist across visits (explicit product default).
  syncMusicUi(false);
  els.bgMusic.pause();
  els.musicToggle.addEventListener("change", () => {
    setMusicEnabled(els.musicToggle.checked);
  });
}

/** @type {{ display: string } | null} */
let lastResult = null;
/** @type {boolean} */
let ttsPreloadStarted = false;

function syncSpeakUi(speaking) {
  els.stopSpeak.hidden = !speaking;
  els.speak.disabled = speaking || !(lastResult?.display);
}

/**
 * Warm Kokoro after convert models load (idle), so first Speak is often cached.
 * Skipped until Translate succeeds once — avoids surprising mobile data use on land.
 */
function scheduleTtsPreload() {
  if (ttsPreloadStarted) return;
  ttsPreloadStarted = true;
  const run = () => {
    ensureTts((msg) => {
      // Keep Quiet unless user is idle on tip / empty status.
      if (!els.status.textContent || /tip:|kokoro|loading/i.test(els.status.textContent)) {
        els.status.textContent = msg;
      }
    }).catch((err) => {
      console.warn("Kokoro preload failed:", err);
      ttsPreloadStarted = false;
    });
  };
  if (typeof requestIdleCallback === "function") {
    requestIdleCallback(run, { timeout: 4000 });
  } else {
    setTimeout(run, 0);
  }
}

function renderOutput() {
  if (!lastResult) {
    els.output.textContent = "";
    els.output.classList.remove("has-content", "flash", "is-error");
    syncSpeakUi(false);
    return;
  }
  els.output.textContent = lastResult.display;
  els.output.classList.remove("is-error");
  els.output.classList.add("has-content");
  els.output.classList.remove("flash");
  void els.output.offsetWidth;
  els.output.classList.add("flash");
  syncSpeakUi(false);
}

function updateShareUrl(text) {
  const url = new URL(window.location.href);
  if (text && text.length <= MAX_SHARE_CHARS) {
    url.searchParams.set("t", text);
  } else {
    url.searchParams.delete("t");
  }
  // Drop legacy query params if present
  for (const key of ["lang", "mode", "engine", "ipa"]) {
    url.searchParams.delete(key);
  }
  history.replaceState(null, "", url);
}

async function translate() {
  const text = els.input.value;
  try {
    els.translate.disabled = true;
    els.status.textContent = "Loading models…";
    await loadModels();
    const display = convertText(text);
    lastResult = { display };
    renderOutput();
    updateShareUrl(text);
    try {
      els.output.focus({ preventScroll: true });
    } catch {
      /* ignore focus failures on <output> */
    }
    els.status.textContent = text
      ? "sound-alike + rhyme + meter + phrase memory"
      : "";
    scheduleTtsPreload();
  } catch (err) {
    console.error(err);
    const msg = err instanceof Error ? err.message : String(err);
    els.status.textContent = msg;
    lastResult = null;
    els.output.textContent = msg;
    els.output.classList.add("has-content");
    els.output.classList.add("is-error");
    syncSpeakUi(false);
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
      onEnded: () => {
        syncSpeakUi(false);
      },
    });
    // If Stop aborted mid-flight, speakSimlish returns without onEnded.
    syncSpeakUi(false);
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
  updateShareUrl("");
  els.input.focus();
}

function readQuery() {
  const params = new URLSearchParams(window.location.search);
  const t = params.get("t");
  if (t != null) els.input.value = t;
}

els.translate.addEventListener("click", () => translate());
els.clear.addEventListener("click", () => clearAll());
els.copy.addEventListener("click", () => copyOutput());
els.speak.addEventListener("click", () => onSpeak());
els.stopSpeak.addEventListener("click", () => onStopSpeak());

els.input.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    translate();
  }
});

initTheme();
initMusic();
readQuery();
syncSpeakUi(false);
if (els.input.value.trim()) {
  translate();
} else {
  els.status.textContent = "Tip: Ctrl/Cmd+Enter to translate.";
}
