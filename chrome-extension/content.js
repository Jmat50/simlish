/**
 * Content script: walk text nodes, batch-translate via background → Pages bridge,
 * replace / restore, observe mutations while enabled.
 */

// Avoid duplicate listeners if scripting.executeScript re-injects.
if (globalThis.__simlishContentLoaded) {
  // Re-entry: handlers already registered.
} else {
globalThis.__simlishContentLoaded = true;

const SKIP_TAGS = new Set([
  "SCRIPT",
  "STYLE",
  "NOSCRIPT",
  "TEXTAREA",
  "INPUT",
  "OPTION",
  "CODE",
  "PRE",
  "KBD",
  "SAMP",
  "SVG",
  "MATH",
  "TITLE",
]);

const FIRST_CHUNK = 200;
const IDLE_CHUNK = 80;
const OBSERVER_DEBOUNCE_MS = 150;
const MAX_TEXT_LEN = 2000;

/** @type {WeakMap<Text, string>} */
const originals = new WeakMap();
/** @type {WeakSet<Text>} */
const translated = new WeakSet();
/** @type {Set<Text>} */
const tracked = new Set();

/** @type {MutationObserver|null} */
let observer = null;
/** @type {number|null} */
let debounceTimer = null;
/** @type {boolean} */
let enabled = false;
/** @type {boolean} */
let translating = false;

/**
 * @param {Node|null} node
 * @returns {boolean}
 */
function isSkippedContext(node) {
  let el =
    node && node.nodeType === Node.TEXT_NODE
      ? node.parentElement
      : /** @type {Element|null} */ (node);
  while (el) {
    if (el.nodeType === Node.ELEMENT_NODE) {
      const tag = el.tagName;
      if (SKIP_TAGS.has(tag)) return true;
      if (el instanceof HTMLElement) {
        if (el.isContentEditable) return true;
        if (el.dataset.simlishUi === "1") return true;
        if (el.id === "simlish-ext-indicator") return true;
      }
    }
    el = el.parentElement;
  }
  return false;
}

/**
 * @param {string} text
 * @returns {boolean}
 */
function shouldTranslate(text) {
  if (!text || !text.trim()) return false;
  if (text.length > MAX_TEXT_LEN) return false;
  if (text.length === 1) return false;
  // Pure punctuation / numbers / whitespace
  if (!/[A-Za-z\u00C0-\u024F]/.test(text)) return false;
  // URL-ish
  if (/^https?:\/\/\S+$/i.test(text.trim())) return false;
  if (/^[\w.+-]+@[\w.-]+\.\w+$/.test(text.trim())) return false;
  return true;
}

/**
 * @param {Node} root
 * @returns {Text[]}
 */
function collectTextNodes(root) {
  /** @type {Text[]} */
  const out = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!(node instanceof Text)) return NodeFilter.FILTER_REJECT;
      if (isSkippedContext(node)) return NodeFilter.FILTER_REJECT;
      if (translated.has(node)) return NodeFilter.FILTER_REJECT;
      if (!shouldTranslate(node.data)) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  let current = walker.nextNode();
  while (current) {
    out.push(/** @type {Text} */ (current));
    current = walker.nextNode();
  }
  return out;
}

/**
 * @param {string[]} texts
 * @returns {Promise<{ ok: boolean, results: string[]|null, error: string|null }>}
 */
function requestTranslate(texts) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(
      { type: "TRANSLATE_BATCH", texts },
      (res) => {
        if (chrome.runtime.lastError) {
          resolve({
            ok: false,
            results: null,
            error: chrome.runtime.lastError.message || "messaging error",
          });
          return;
        }
        resolve(
          res || { ok: false, results: null, error: "no response" }
        );
      }
    );
  });
}

/**
 * Apply translations for a list of text nodes (deduped by string).
 * @param {Text[]} nodes
 */
async function translateNodes(nodes) {
  if (!enabled || !nodes.length) return;

  /** @type {Map<string, Text[]>} */
  const groups = new Map();
  for (const node of nodes) {
    if (!node.isConnected) continue;
    if (translated.has(node)) continue;
    if (!shouldTranslate(node.data)) continue;
    const key = node.data;
    let list = groups.get(key);
    if (!list) {
      list = [];
      groups.set(key, list);
    }
    list.push(node);
  }

  const unique = [...groups.keys()];
  if (!unique.length) return;

  translating = true;
  try {
    for (let i = 0; i < unique.length; i += FIRST_CHUNK) {
      if (!enabled) break;
      const slice = unique.slice(i, i + (i === 0 ? FIRST_CHUNK : IDLE_CHUNK));
      const res = await requestTranslate(slice);
      if (!enabled) break;
      if (!res.ok || !res.results || res.results.length !== slice.length) {
        console.warn("[Simlish] translate failed:", res.error);
        break;
      }
      for (let j = 0; j < slice.length; j++) {
        const original = slice[j];
        const simlish = res.results[j];
        const targets = groups.get(original) || [];
        for (const node of targets) {
          if (!node.isConnected) continue;
          if (translated.has(node)) continue;
          if (node.data !== original) continue;
          if (!originals.has(node)) originals.set(node, original);
          node.data = simlish;
          translated.add(node);
          tracked.add(node);
        }
      }
      // Yield so the page stays responsive
      await new Promise((r) => {
        if (typeof requestIdleCallback === "function") {
          requestIdleCallback(() => r(undefined), { timeout: 200 });
        } else {
          setTimeout(r, 0);
        }
      });
    }
  } finally {
    translating = false;
  }
}

function showIndicator() {
  let el = document.getElementById("simlish-ext-indicator");
  if (!el) {
    el = document.createElement("div");
    el.id = "simlish-ext-indicator";
    el.dataset.simlishUi = "1";
    el.textContent = "Simlish on";
    document.documentElement.appendChild(el);
  }
}

function hideIndicator() {
  document.getElementById("simlish-ext-indicator")?.remove();
}

function restoreAll() {
  for (const node of [...tracked]) {
    const original = originals.get(node);
    if (original != null && node.isConnected) {
      node.data = original;
    }
    translated.delete(node);
    originals.delete(node);
  }
  tracked.clear();
}

function disconnectObserver() {
  if (debounceTimer != null) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
  if (observer) {
    observer.disconnect();
    observer = null;
  }
}

function scheduleMutationPass() {
  if (debounceTimer != null) clearTimeout(debounceTimer);
  debounceTimer = /** @type {unknown} */ (
    setTimeout(() => {
      debounceTimer = null;
      if (!enabled || translating) return;
      const nodes = collectTextNodes(document.body || document.documentElement);
      translateNodes(nodes);
    }, OBSERVER_DEBOUNCE_MS)
  );
}

function connectObserver() {
  disconnectObserver();
  observer = new MutationObserver((mutations) => {
    if (!enabled) return;
    for (const m of mutations) {
      if (m.type === "characterData") {
        const node = m.target;
        if (node instanceof Text && translated.has(node)) {
          // Our own write — ignore
          continue;
        }
        scheduleMutationPass();
        return;
      }
      if (m.type === "childList" && (m.addedNodes.length || m.removedNodes.length)) {
        scheduleMutationPass();
        return;
      }
    }
  });
  observer.observe(document.documentElement, {
    childList: true,
    characterData: true,
    subtree: true,
  });
}

async function enable() {
  if (enabled) return;
  enabled = true;
  showIndicator();
  connectObserver();
  const root = document.body || document.documentElement;
  await translateNodes(collectTextNodes(root));
}

function disable() {
  enabled = false;
  disconnectObserver();
  restoreAll();
  hideIndicator();
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message !== "object") return false;
  if (message.type === "ENABLE") {
    enable()
      .then(() => sendResponse({ ok: true }))
      .catch((err) =>
        sendResponse({
          ok: false,
          error: err instanceof Error ? err.message : String(err),
        })
      );
    return true;
  }
  if (message.type === "DISABLE") {
    disable();
    sendResponse({ ok: true });
    return false;
  }
  if (message.type === "GET_STATE") {
    sendResponse({ enabled });
    return false;
  }
  return false;
});

// Re-enable if this tab was marked enabled (e.g. after navigation with session flag)
chrome.runtime.sendMessage({ type: "GET_TAB_ENABLED" }, (res) => {
  if (chrome.runtime.lastError) return;
  if (res && res.enabled) enable();
});

} // end __simlishContentLoaded guard
