import {
  CHANNEL,
  DEFAULT_BRIDGE_URL,
  MAX_BATCH,
  PROTOCOL_VERSION,
  TRANSLATE_TIMEOUT_MS,
  originFromBridgeUrl,
} from "./shared.js";

const iframe = /** @type {HTMLIFrameElement} */ (document.getElementById("bridge"));

/** @type {string} */
let bridgeUrl = DEFAULT_BRIDGE_URL;
/** @type {string} */
let targetOrigin = originFromBridgeUrl(bridgeUrl);
/** @type {"idle"|"loading"|"ready"|"error"} */
let bridgeState = "idle";
/** @type {string|null} */
let bridgeError = null;

/** @type {Map<string, { resolve: (v: unknown) => void, reject: (e: Error) => void, timer: number }>} */
const pending = new Map();

function uuid() {
  return crypto.randomUUID();
}

/**
 * @param {Record<string, unknown>} msg
 * @param {number} [timeoutMs]
 * @returns {Promise<unknown>}
 */
function sendToBridge(msg, timeoutMs = TRANSLATE_TIMEOUT_MS) {
  return new Promise((resolve, reject) => {
    if (!iframe.contentWindow) {
      reject(new Error("bridge iframe not ready"));
      return;
    }
    const id = /** @type {string} */ (msg.id);
    const timer = /** @type {unknown} */ (
      setTimeout(() => {
        pending.delete(id);
        reject(new Error("bridge timeout"));
      }, timeoutMs)
    );
    pending.set(id, {
      resolve,
      reject,
      timer: /** @type {number} */ (timer),
    });
    iframe.contentWindow.postMessage(msg, targetOrigin);
  });
}

/**
 * @param {MessageEvent} event
 */
function onBridgeMessage(event) {
  if (event.origin !== targetOrigin) return;
  const data = event.data;
  if (!data || data.channel !== CHANNEL || data.version !== PROTOCOL_VERSION) {
    return;
  }
  const entry = pending.get(data.id);
  if (!entry) return;
  clearTimeout(entry.timer);
  pending.delete(data.id);
  entry.resolve(data);
}

window.addEventListener("message", onBridgeMessage);

/**
 * @returns {Promise<void>}
 */
async function loadBridgeUrl() {
  const stored = await chrome.storage.local.get(["bridgeUrl"]);
  if (typeof stored.bridgeUrl === "string" && stored.bridgeUrl.trim()) {
    bridgeUrl = stored.bridgeUrl.trim();
  } else {
    bridgeUrl = DEFAULT_BRIDGE_URL;
  }
  targetOrigin = originFromBridgeUrl(bridgeUrl);
}

/**
 * @returns {Promise<void>}
 */
function waitForIframeLoad() {
  return new Promise((resolve, reject) => {
    const onLoad = () => {
      iframe.removeEventListener("load", onLoad);
      iframe.removeEventListener("error", onError);
      resolve();
    };
    const onError = () => {
      iframe.removeEventListener("load", onLoad);
      iframe.removeEventListener("error", onError);
      reject(new Error("failed to load bridge iframe"));
    };
    iframe.addEventListener("load", onLoad);
    iframe.addEventListener("error", onError);
  });
}

/**
 * @returns {Promise<void>}
 */
async function ensureBridgeReady() {
  if (bridgeState === "ready") return;
  if (bridgeState === "loading") {
    // Wait until ready or error
    await new Promise((resolve, reject) => {
      const start = Date.now();
      const tick = () => {
        if (bridgeState === "ready") return resolve(undefined);
        if (bridgeState === "error") {
          return reject(new Error(bridgeError || "bridge error"));
        }
        if (Date.now() - start > TRANSLATE_TIMEOUT_MS * 2) {
          return reject(new Error("bridge load timeout"));
        }
        setTimeout(tick, 50);
      };
      tick();
    });
    return;
  }

  bridgeState = "loading";
  bridgeError = null;
  await loadBridgeUrl();
  iframe.src = bridgeUrl;
  await waitForIframeLoad();

  // Give the bridge module a moment to start loading models, then ping until ready
  const deadline = Date.now() + TRANSLATE_TIMEOUT_MS * 2;
  while (Date.now() < deadline) {
    try {
      const id = uuid();
      const res = /** @type {{ type: string, ready?: boolean }} */ (
        await sendToBridge(
          {
            channel: CHANNEL,
            version: PROTOCOL_VERSION,
            type: "ping",
            id,
          },
          2000
        )
      );
      if (res.type === "pong" && res.ready) {
        bridgeState = "ready";
        bridgeError = null;
        return;
      }
    } catch {
      // keep polling
    }
    await new Promise((r) => setTimeout(r, 150));
  }
  bridgeState = "error";
  bridgeError = "bridge models not ready";
  throw new Error(bridgeError);
}

/**
 * @param {string[]} texts
 * @returns {Promise<{ results: string[]|null, error: string|null }>}
 */
async function translateBatch(texts) {
  await ensureBridgeReady();
  if (texts.length > MAX_BATCH) {
    throw new Error(`batch too large (max ${MAX_BATCH})`);
  }
  const id = uuid();
  const res = /** @type {{ type: string, results?: string[]|null, error?: string|null }} */ (
    await sendToBridge({
      channel: CHANNEL,
      version: PROTOCOL_VERSION,
      type: "translate",
      id,
      texts,
    })
  );
  if (res.type !== "translate-result") {
    throw new Error("unexpected bridge response");
  }
  return { results: res.results ?? null, error: res.error ?? null };
}

/**
 * Force reload the iframe (e.g. after bridge URL change).
 */
async function reloadBridge() {
  for (const [, entry] of pending) {
    clearTimeout(entry.timer);
    entry.reject(new Error("bridge reloading"));
  }
  pending.clear();
  bridgeState = "idle";
  bridgeError = null;
  iframe.removeAttribute("src");
  await ensureBridgeReady();
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message !== "object") return false;

  if (message.type === "OFFSCREEN_PING") {
    ensureBridgeReady()
      .then(() => sendResponse({ ok: true, bridgeState, bridgeUrl }))
      .catch((err) =>
        sendResponse({
          ok: false,
          bridgeState,
          bridgeUrl,
          error: err instanceof Error ? err.message : String(err),
        })
      );
    return true;
  }

  if (message.type === "OFFSCREEN_STATUS") {
    sendResponse({
      ok: bridgeState === "ready",
      bridgeState,
      bridgeUrl,
      bridgeError,
    });
    return false;
  }

  if (message.type === "OFFSCREEN_RELOAD") {
    reloadBridge()
      .then(() => sendResponse({ ok: true, bridgeState, bridgeUrl }))
      .catch((err) =>
        sendResponse({
          ok: false,
          error: err instanceof Error ? err.message : String(err),
        })
      );
    return true;
  }

  if (message.type === "OFFSCREEN_TRANSLATE") {
    const texts = Array.isArray(message.texts) ? message.texts : [];
    translateBatch(texts)
      .then((out) => sendResponse({ ok: !out.error, ...out }))
      .catch((err) =>
        sendResponse({
          ok: false,
          results: null,
          error: err instanceof Error ? err.message : String(err),
        })
      );
    return true;
  }

  return false;
});

// Eagerly warm the bridge
ensureBridgeReady().catch(() => {
  /* surfaced via status / translate errors */
});
