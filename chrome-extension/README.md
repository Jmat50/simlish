# Simlish Chrome Extension

Manifest V3 extension that rewrites visible page text into Simlish using the **GitHub Pages convert bridge**. The extension does not ship models or convert logic — translation always runs in a Pages document framed by an offscreen iframe.

## Load unpacked

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select this folder:

   `C:\VIsual Studio\simlish\chrome-extension`

5. Pin the Simlish action, open any http(s) page, toggle **Simlish this page**

## How it works

```text
content script (DOM text nodes)
  → service worker (queue / batch)
    → offscreen document (hidden iframe)
      → https://jmat50.github.io/simlish/bridge.html
        → docs/js/bridge.js → loadModels + convertText
```

Protocol: `postMessage` channel `simlish-bridge` (`ping` / `translate` / `status`).

## Bridge URL

Default: `https://jmat50.github.io/simlish/bridge.html`

For local development:

```bash
# from repo root
npx --yes serve docs -p 4173
```

In the extension popup → **Bridge URL** → **Use local :4173** → **Save & reload**.

## Packaging

Zip **only** the contents of `chrome-extension/` (not the whole repo). Do not include `docs/models` or `convert.js` in the zip — Pages remains the translation runtime.

## Limitations

- Requires network access to the bridge origin
- Host pages under `chrome://`, the Web Store, etc. are skipped
- Inputs / `contenteditable` / `code` / `pre` are left alone
- Toggle is per-tab and stored in `chrome.storage.session` (cleared when the browser session ends)
