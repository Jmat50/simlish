import {
  CHANNEL,
  DEFAULT_BRIDGE_URL,
  MAX_BATCH,
  PROTOCOL_VERSION,
  TRANSLATE_TIMEOUT_MS,
  originFromBridgeUrl,
} from "./shared.js";

const iframe = /** @type {HTMLIFrameElement} */ (document.getElementById("bridge"));
const IFRAME_LOAD_TIMEOUT_MS = 15000;

/** @type {string} */
let bridgeUrl = DEFAULT_BRIDGE_URL;
/** @type {string} */
let targetOrigin = originFromBridgeUrl(bridgeUrl);
/** @type {"idle"|"loading"|"ready"|"error"} */
let bridgeState = "idle";
/** @type {string|null} */
let bridgeError = null;
/** @type {Promise<void>|null} */
let readyPromise = null;

/** @type {Map<string, { resolve: (v: unknown) => void, reject: (e: Error) => void, timer: number }>} */
const pending = new Map();

function uuid() {
  return crypto.randomUUID();
}

/**
 * @param {string} url
 * @returns {boolean} true if the URL changed
 */
function setBridgeUrl(url) {
  const next = (url && url.trim()) || DEFAULT_BRIDGE_URL;
  if (next === bridgeUrl) return false;
  bridgeUrl = next;
  targetOrigin = originFromBridgeUrl(bridgeUrl);
  return true;
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
function waitForIframeLoad() {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      iframe.removeEventListener("load", onLoad);
      iframe.removeEventListener("error", onError);
      reject(new Error("bridge iframe load timeout"));
    }, IFRAME_LOAD_TIMEOUT_MS);

    const onLoad = () => {
      clearTimeout(timer);
      iframe.removeEventListener("load", onLoad);
      iframe.removeEventListener("error", onError);
      resolve();
    };
    const onError = () => {
      clearTimeout(timer);
      iframe.removeEventListener("load", onLoad);
      iframe.removeEventListener("error", onError);
      reject(new Error("failed to load bridge iframe"));
    };
    iframe.addEventListener("load", onLoad);
    iframe.addEventListener("error", onError);
  });
}

/**
 * Navigate the iframe and poll until Pages reports models ready.
 * @returns {Promise<void>}
 */
function startBridgeLoad() {
  bridgeState = "loading";
  bridgeError = null;
  readyPromise = (async () => {
    try {
      const loadWait = waitForIframeLoad();
      iframe.src = bridgeUrl;
      await loadWait;

      const deadline = Date.now() + TRANSLATE_TIMEOUT_MS * 2;
      let lastDetail = "no pong";
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
          lastDetail =
            res.type === "pong" ? "models not ready" : "unexpected ping reply";
        } catch (err) {
          lastDetail = err instanceof Error ? err.message : String(err);
        }
        await new Promise((r) => setTimeout(r, 150));
      }
      throw new Error(`bridge models not ready (${lastDetail})`);
    } catch (err) {
      bridgeState = "error";
      bridgeError = err instanceof Error ? err.message : String(err);
      throw err;
    } finally {
      if (bridgeState !== "ready") {
        readyPromise = null;
      }
    }
  })();
  return readyPromise;
}

/**
 * Load (or reuse) the Pages bridge iframe and wait until models are ready.
 * Bridge URL must be supplied by the service worker — offscreen has no chrome.storage.
 * @param {string} [url]
 * @returns {Promise<void>}
 */
function ensureBridgeReady(url) {
  if (typeof url === "string" && url.trim() && setBridgeUrl(url)) {
    return reloadBridge();
  }
  if (bridgeState === "ready") return Promise.resolve();
  if (readyPromise) return readyPromise;
  return startBridgeLoad();
}

/**
 * @param {string[]} texts
 * @param {string} [url]
 * @returns {Promise<{ results: string[]|null, error: string|null }>}
 */
async function translateBatch(texts, url) {
  await ensureBridgeReady(url);
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
 * @param {string} [url]
 */
async function reloadBridge(url) {
  for (const [, entry] of pending) {
    clearTimeout(entry.timer);
    entry.reject(new Error("bridge reloading"));
  }
  pending.clear();
  readyPromise = null;
  bridgeState = "idle";
  bridgeError = null;
  if (typeof url === "string" && url.trim()) {
    setBridgeUrl(url);
  }
  iframe.removeAttribute("src");
  await new Promise((r) => setTimeout(r, 0));
  return startBridgeLoad();
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message !== "object") return false;

  if (message.type === "OFFSCREEN_PING") {
    ensureBridgeReady(
      typeof message.bridgeUrl === "string" ? message.bridgeUrl : undefined
    )
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
    reloadBridge(
      typeof message.bridgeUrl === "string" ? message.bridgeUrl : undefined
    )
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

  if (message.type === "OFFSCREEN_TRANSLATE") {
    const texts = Array.isArray(message.texts) ? message.texts : [];
    translateBatch(
      texts,
      typeof message.bridgeUrl === "string" ? message.bridgeUrl : undefined
    )
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

// Warm with default Pages bridge (SW will re-ping with stored URL when needed).
ensureBridgeReady(DEFAULT_BRIDGE_URL).catch(() => {
  /* surfaced via status / translate errors */
});
