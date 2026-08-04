/** Shared defaults for the Simlish extension. */
export const DEFAULT_BRIDGE_URL =
  "https://jmat50.github.io/simlish/bridge.html";

export const LOCAL_BRIDGE_URL = "http://127.0.0.1:4173/bridge.html";

export const CHANNEL = "simlish-bridge";
export const PROTOCOL_VERSION = 1;
export const TRANSLATE_TIMEOUT_MS = 8000;
export const MAX_BATCH = 50;

/**
 * @param {string} bridgeUrl
 * @returns {string} postMessage targetOrigin
 */
export function originFromBridgeUrl(bridgeUrl) {
  try {
    return new URL(bridgeUrl).origin;
  } catch {
    return "https://jmat50.github.io";
  }
}
