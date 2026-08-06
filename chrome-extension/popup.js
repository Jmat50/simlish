import { DEFAULT_BRIDGE_URL, LOCAL_BRIDGE_URL } from "./shared.js";

const enabledEl = /** @type {HTMLInputElement} */ (document.getElementById("enabled"));
const statusEl = /** @type {HTMLElement} */ (document.getElementById("status"));
const bridgeUrlEl = /** @type {HTMLInputElement} */ (document.getElementById("bridge-url"));
const saveUrlBtn = /** @type {HTMLButtonElement} */ (document.getElementById("save-url"));
const useLocalBtn = /** @type {HTMLButtonElement} */ (document.getElementById("use-local"));

/**
 * @param {string} text
 * @param {"ok"|"error"|""} [kind]
 */
function setStatus(text, kind = "") {
  statusEl.textContent = text;
  statusEl.classList.remove("ok", "error");
  if (kind) statusEl.classList.add(kind);
}

/**
 * @returns {Promise<chrome.tabs.Tab|undefined>}
 */
async function activeTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0];
}

async function refreshBridgeStatus() {
  setStatus("Checking bridge…");
  try {
    const statusPromise = chrome.runtime.sendMessage({ type: "BRIDGE_STATUS" });
    const timed = await Promise.race([
      statusPromise.then((res) => ({ res })),
      new Promise((resolve) =>
        setTimeout(() => resolve({ timeout: true }), 25000)
      ),
    ]);
    if ("timeout" in timed && timed.timeout) {
      setStatus("Bridge check timed out", "error");
      return;
    }
    const res = /** @type {{ res?: { ok?: boolean, error?: string } }} */ (timed)
      .res;
    if (res && res.ok) {
      setStatus("Bridge ready", "ok");
    } else {
      setStatus(
        `Bridge unavailable${res?.error ? `: ${res.error}` : ""}`,
        "error"
      );
    }
  } catch (err) {
    setStatus(
      err instanceof Error ? err.message : String(err),
      "error"
    );
  }
}

async function refreshToggle() {
  const tab = await activeTab();
  if (!tab?.id) {
    enabledEl.checked = false;
    enabledEl.disabled = true;
    return;
  }
  const url = tab.url || "";
  if (
    url.startsWith("chrome://") ||
    url.startsWith("chrome-extension://") ||
    url.startsWith("https://chrome.google.com/webstore") ||
    url.startsWith("https://chromewebstore.google.com")
  ) {
    enabledEl.checked = false;
    enabledEl.disabled = true;
    setStatus("Cannot run on this page", "error");
    return;
  }
  enabledEl.disabled = false;
  const res = await chrome.runtime.sendMessage({
    type: "GET_TAB_ENABLED",
    tabId: tab.id,
  });
  enabledEl.checked = !!(res && res.enabled);
}

enabledEl.addEventListener("change", async () => {
  const tab = await activeTab();
  if (!tab?.id) return;
  enabledEl.disabled = true;
  try {
    const res = await chrome.runtime.sendMessage({
      type: "SET_TAB_ENABLED",
      tabId: tab.id,
      enabled: enabledEl.checked,
    });
    if (!res?.ok) {
      enabledEl.checked = !enabledEl.checked;
      setStatus(res?.error || "Failed to toggle", "error");
    } else if (enabledEl.checked) {
      setStatus("Simlish enabled on this tab", "ok");
    } else {
      setStatus("Restored original text", "ok");
    }
  } catch (err) {
    enabledEl.checked = !enabledEl.checked;
    setStatus(err instanceof Error ? err.message : String(err), "error");
  } finally {
    enabledEl.disabled = false;
  }
});

saveUrlBtn.addEventListener("click", async () => {
  const url = bridgeUrlEl.value.trim() || DEFAULT_BRIDGE_URL;
  setStatus("Reloading bridge…");
  const res = await chrome.runtime.sendMessage({
    type: "SET_BRIDGE_URL",
    bridgeUrl: url,
  });
  if (res?.ok) {
    bridgeUrlEl.value = url;
    setStatus("Bridge reloaded", "ok");
    await refreshBridgeStatus();
  } else {
    setStatus(res?.error || "Reload failed", "error");
  }
});

useLocalBtn.addEventListener("click", () => {
  bridgeUrlEl.value = LOCAL_BRIDGE_URL;
});

chrome.runtime
  .sendMessage({ type: "GET_BRIDGE_URL" })
  .then((res) => {
    bridgeUrlEl.value = res?.bridgeUrl || DEFAULT_BRIDGE_URL;
  })
  .catch(() => {
    bridgeUrlEl.value = DEFAULT_BRIDGE_URL;
  });

refreshToggle().then(refreshBridgeStatus);
