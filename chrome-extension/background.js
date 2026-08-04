import { DEFAULT_BRIDGE_URL, MAX_BATCH } from "./shared.js";

const OFFSCREEN_URL = "offscreen.html";
const OFFSCREEN_REASONS = ["IFRAME_SCRIPTING"];
const OFFSCREEN_JUSTIFICATION =
  "Embed the Simlish GitHub Pages bridge iframe to run v2 translation.";

/** @type {Promise<unknown>|null} */
let queueTail = null;

/**
 * @returns {Promise<boolean>}
 */
async function hasOffscreenDocument() {
  if (chrome.runtime.getContexts) {
    const contexts = await chrome.runtime.getContexts({
      contextTypes: ["OFFSCREEN_DOCUMENT"],
      documentUrls: [chrome.runtime.getURL(OFFSCREEN_URL)],
    });
    return contexts.length > 0;
  }
  // Fallback for older Chrome
  return false;
}

/**
 * @returns {Promise<void>}
 */
async function ensureOffscreen() {
  if (await hasOffscreenDocument()) return;
  try {
    await chrome.offscreen.createDocument({
      url: OFFSCREEN_URL,
      reasons: /** @type {chrome.offscreen.Reason[]} */ (OFFSCREEN_REASONS),
      justification: OFFSCREEN_JUSTIFICATION,
    });
  } catch (err) {
    // Concurrent create can throw; re-check
    if (await hasOffscreenDocument()) return;
    throw err;
  }
}

/**
 * @param {Record<string, unknown>} message
 * @returns {Promise<any>}
 */
async function sendToOffscreen(message) {
  await ensureOffscreen();
  let lastErr = null;
  for (let attempt = 0; attempt < 8; attempt++) {
    try {
      const res = await chrome.runtime.sendMessage(message);
      if (res !== undefined) return res;
    } catch (err) {
      lastErr = err;
    }
    await new Promise((r) => setTimeout(r, 50 * (attempt + 1)));
    await ensureOffscreen();
  }
  throw lastErr || new Error("offscreen did not respond");
}

/**
 * Serialize bridge traffic: one in-flight translate at a time.
 * @template T
 * @param {() => Promise<T>} fn
 * @returns {Promise<T>}
 */
function enqueue(fn) {
  const run = (queueTail || Promise.resolve()).then(fn, fn);
  queueTail = run.then(
    () => undefined,
    () => undefined
  );
  return run;
}

/**
 * @param {string[]} texts
 * @returns {Promise<{ ok: boolean, results: string[]|null, error: string|null }>}
 */
async function translateBatch(texts) {
  return enqueue(async () => {
    /** @type {string[]} */
    const allResults = [];
    for (let i = 0; i < texts.length; i += MAX_BATCH) {
      const chunk = texts.slice(i, i + MAX_BATCH);
      const res = await sendToOffscreen({
        type: "OFFSCREEN_TRANSLATE",
        texts: chunk,
      });
      if (!res || res.error || !Array.isArray(res.results)) {
        return {
          ok: false,
          results: null,
          error: (res && res.error) || "translate failed",
        };
      }
      allResults.push(...res.results);
    }
    return { ok: true, results: allResults, error: null };
  });
}

/**
 * @param {number} tabId
 * @param {boolean} enabled
 */
async function setTabEnabled(tabId, enabled) {
  const key = `tabEnabled:${tabId}`;
  if (enabled) {
    await chrome.storage.session.set({ [key]: true });
  } else {
    await chrome.storage.session.remove(key);
  }
}

/**
 * @param {number} tabId
 * @returns {Promise<boolean>}
 */
async function getTabEnabled(tabId) {
  const key = `tabEnabled:${tabId}`;
  const stored = await chrome.storage.session.get(key);
  return !!stored[key];
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message !== "object") return false;

  // Offscreen handles its own OFFSCREEN_* messages; ignore here if we are SW
  if (
    typeof message.type === "string" &&
    message.type.startsWith("OFFSCREEN_")
  ) {
    return false;
  }

  if (message.type === "TRANSLATE_BATCH") {
    const texts = Array.isArray(message.texts) ? message.texts : [];
    translateBatch(texts)
      .then((out) => sendResponse(out))
      .catch((err) =>
        sendResponse({
          ok: false,
          results: null,
          error: err instanceof Error ? err.message : String(err),
        })
      );
    return true;
  }

  if (message.type === "GET_TAB_ENABLED") {
    const tabId = sender.tab?.id ?? message.tabId;
    if (typeof tabId !== "number") {
      sendResponse({ enabled: false });
      return false;
    }
    getTabEnabled(tabId).then((enabled) => sendResponse({ enabled }));
    return true;
  }

  if (message.type === "SET_TAB_ENABLED") {
    const tabId = message.tabId;
    const enabled = !!message.enabled;
    if (typeof tabId !== "number") {
      sendResponse({ ok: false, error: "missing tabId" });
      return false;
    }
    setTabEnabled(tabId, enabled)
      .then(async () => {
        try {
          await chrome.tabs.sendMessage(tabId, {
            type: enabled ? "ENABLE" : "DISABLE",
          });
        } catch {
          // Content script may not be injected yet; try scripting
          if (enabled) {
            try {
              await chrome.scripting.executeScript({
                target: { tabId },
                files: ["content.js"],
              });
              await chrome.scripting.insertCSS({
                target: { tabId },
                files: ["content.css"],
              });
              await chrome.tabs.sendMessage(tabId, { type: "ENABLE" });
            } catch (err) {
              sendResponse({
                ok: false,
                error: err instanceof Error ? err.message : String(err),
              });
              return;
            }
          }
        }
        sendResponse({ ok: true, enabled });
      })
      .catch((err) =>
        sendResponse({
          ok: false,
          error: err instanceof Error ? err.message : String(err),
        })
      );
    return true;
  }

  if (message.type === "BRIDGE_STATUS") {
    sendToOffscreen({ type: "OFFSCREEN_PING" })
      .then((res) => sendResponse(res || { ok: false, error: "no response" }))
      .catch((err) =>
        sendResponse({
          ok: false,
          error: err instanceof Error ? err.message : String(err),
        })
      );
    return true;
  }

  if (message.type === "GET_BRIDGE_URL") {
    chrome.storage.local.get(["bridgeUrl"]).then((stored) => {
      sendResponse({
        bridgeUrl:
          typeof stored.bridgeUrl === "string" && stored.bridgeUrl.trim()
            ? stored.bridgeUrl.trim()
            : DEFAULT_BRIDGE_URL,
      });
    });
    return true;
  }

  if (message.type === "SET_BRIDGE_URL") {
    const url =
      typeof message.bridgeUrl === "string" && message.bridgeUrl.trim()
        ? message.bridgeUrl.trim()
        : DEFAULT_BRIDGE_URL;
    chrome.storage.local
      .set({ bridgeUrl: url })
      .then(() => sendToOffscreen({ type: "OFFSCREEN_RELOAD" }))
      .then((res) => sendResponse(res || { ok: true }))
      .catch((err) =>
        sendResponse({
          ok: false,
          error: err instanceof Error ? err.message : String(err),
        })
      );
    return true;
  }

  return false;
});

chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.session.remove(`tabEnabled:${tabId}`);
});

// Warm offscreen + bridge early
ensureOffscreen().catch(() => {});
