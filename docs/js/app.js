import { convertText, loadModels } from "./convert.js?v=20260804a";
import { speakSimlish, stopSpeaking } from "./speak.js?v=20260804a";

const MAX_SHARE_CHARS = 1800;

const els = {
  input: /** @type {HTMLTextAreaElement} */ (document.getElementById("input")),
  output: /** @type {HTMLElement} */ (document.getElementById("output")),
  translate: /** @type {HTMLButtonElement} */ (document.getElementById("translate-btn")),
  clear: /** @type {HTMLButtonElement} */ (document.getElementById("clear-btn")),
  copy: /** @type {HTMLButtonElement} */ (document.getElementById("copy-btn")),
  speak: /** @type {HTMLButtonElement} */ (document.getElementById("speak-btn")),
  stopSpeak: /** @type {HTMLButtonElement} */ (document.getElementById("stop-speak-btn")),
  status: /** @type {HTMLElement} */ (document.getElementById("status")),
};

/** @type {{ display: string } | null} */
let lastResult = null;

function syncSpeakUi(speaking) {
  els.stopSpeak.hidden = !speaking;
  els.speak.disabled = speaking || !(lastResult?.display);
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

readQuery();
syncSpeakUi(false);
if (els.input.value.trim()) {
  translate();
} else {
  els.status.textContent = "Tip: Ctrl/Cmd+Enter to translate.";
}
