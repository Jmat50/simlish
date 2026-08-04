/**
 * Extension RPC surface for the Simlish converter.
 * Protocol: postMessage channel "simlish-bridge" v1.
 * Loaded only by chrome-extension offscreen iframe (docs/bridge.html).
 */
import { convertText, loadModels } from "./convert.js";

const CHANNEL = "simlish-bridge";
const VERSION = 1;
const MAX_BATCH = 50;
const MAX_CHARS = 2000;
const BRIDGE_VERSION = "1.0.0";

/** @type {"loading"|"ready"|"error"} */
let loadState = "loading";
/** @type {string|null} */
let loadError = null;

function isAllowedOrigin(origin) {
  if (!origin || typeof origin !== "string") return false;
  if (origin.startsWith("chrome-extension://")) return true;
  if (origin === "http://127.0.0.1:4173" || origin === "http://localhost:4173") {
    return true;
  }
  return false;
}

/**
 * @param {unknown} data
 * @returns {data is { channel: string, version: number, type: string, id: string }}
 */
function isBridgeMessage(data) {
  return (
    !!data &&
    typeof data === "object" &&
    /** @type {{ channel?: unknown }} */ (data).channel === CHANNEL &&
    /** @type {{ version?: unknown }} */ (data).version === VERSION &&
    typeof /** @type {{ type?: unknown }} */ (data).type === "string" &&
    typeof /** @type {{ id?: unknown }} */ (data).id === "string"
  );
}

/**
 * @param {MessageEvent} event
 * @param {Record<string, unknown>} payload
 */
function reply(event, payload) {
  const source = event.source;
  if (!source || typeof source.postMessage !== "function") return;
  source.postMessage(
    { channel: CHANNEL, version: VERSION, ...payload },
    event.origin
  );
}

/**
 * @param {unknown[]} texts
 * @returns {string[]}
 */
function translateBatch(texts) {
  if (!Array.isArray(texts)) {
    throw new Error("texts must be an array");
  }
  if (texts.length > MAX_BATCH) {
    throw new Error(`batch too large (max ${MAX_BATCH})`);
  }
  return texts.map((raw) => {
    if (typeof raw !== "string") return "";
    if (!raw.trim()) return raw;
    if (raw.length > MAX_CHARS) {
      throw new Error(`string exceeds ${MAX_CHARS} characters`);
    }
    return convertText(raw);
  });
}

/**
 * @param {MessageEvent} event
 */
function onMessage(event) {
  if (!isAllowedOrigin(event.origin)) return;
  if (!isBridgeMessage(event.data)) return;

  const { type, id } = event.data;

  if (type === "ping") {
    reply(event, { type: "pong", id, ready: loadState === "ready" });
    return;
  }

  if (type === "status") {
    reply(event, {
      type: "status-result",
      id,
      ready: loadState === "ready",
      loadState,
      loadError,
      bridgeVersion: BRIDGE_VERSION,
    });
    return;
  }

  if (type === "translate") {
    if (loadState !== "ready") {
      reply(event, {
        type: "translate-result",
        id,
        results: null,
        error: loadError || "models not ready",
      });
      return;
    }
    try {
      const texts = /** @type {{ texts?: unknown }} */ (event.data).texts;
      const results = translateBatch(/** @type {unknown[]} */ (texts));
      reply(event, {
        type: "translate-result",
        id,
        results,
        error: null,
      });
    } catch (err) {
      reply(event, {
        type: "translate-result",
        id,
        results: null,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }
}

window.addEventListener("message", onMessage);

loadModels()
  .then(() => {
    loadState = "ready";
    loadError = null;
  })
  .catch((err) => {
    loadState = "error";
    loadError = err instanceof Error ? err.message : String(err);
  });
