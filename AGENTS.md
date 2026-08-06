# AGENTS.md

Guidance for AI agents in this repo.

## Project

Client-side English→Simlish converter. Live: https://jmat50.github.io/simlish/

| Piece | Path | Notes |
|-------|------|--------|
| Pages site | `docs/` | Convert + Speak + extension bridge. No backend/telemetry. |
| Induction | `engine/` | Official lyrics + YouTube rips → model JSON. Site never calls Python. |
| Extension | `chrome-extension/` | MV3; translates via Pages `postMessage` bridge only (no vendored models). Docs: `chrome-extension/README.md`. |

Convert is line-first: phrase memory → else sound-alike + end-rhyme + syllable budget (`docs/js/convert.js` ← `engine/convert/`). Closed-class misses (`is`/`are`/…) fill or elide from attested short fillers — never phone-invent glue.

Speak uses stock [Kokoro](https://github.com/hexgrad/kokoro) + `docs/js/simlish-ipa.js` (not an official Sims voice).

## Chrome extension

Load unpacked from `chrome-extension/` (Developer mode → Load unpacked). No build/bundle step.

Required load files (must stay in that folder):

- `manifest.json`, `background.js`, `shared.js`
- `content.js`, `content.css`
- `offscreen.html`, `offscreen.js`
- `popup.html`, `popup.js`, `popup.css`
- `icons/icon16.png`, `icon32.png`, `icon48.png`, `icon128.png`

Runtime depends on the live (or local) Pages bridge — not on files inside the extension:

- `docs/bridge.html` + `docs/js/bridge.js` (`simlish-bridge` RPC)
- `docs/js/convert.js` + `docs/models/`

Default bridge URL: `https://jmat50.github.io/simlish/bridge.html`. Local: serve `docs` on `:4173`, then popup → Use local :4173.

## Rules

- Simlish orthography from official wiki EN\|SIMLISH tables only — never fan sheets, YouTube descriptions, or ASR spellings.
- Whisper/ASR in `engine/` is timing alignment only, never orthography.
- YouTube audio allowed under `engine/` for research; titles/descriptions are not lyric evidence.
- Site loads only `docs/models/` + `docs/js/convert.js` (relative paths for `/simlish/`).
- Share induced JSON / aggregates — not full lyric sheets or audio dumps.
- Do not commit EA package rips, decoded VO, or EA-derived TTS weights. Public Speak stays stock Kokoro.
- Do not re-add a second convert engine, HTTP translate API, analytics, or model copies inside the extension.

## Layout

| Path | Role |
|------|------|
| `docs/js/app.js` | UI; URL param `t` |
| `docs/js/convert.js` | Browser convert (`loadModels` / `convertText`) |
| `docs/js/bridge.js` + `docs/bridge.html` | Extension RPC (`simlish-bridge`) |
| `docs/js/speak.js`, `simlish-ipa.js` | Stock Kokoro Speak |
| `docs/models/` | Site model JSON (+ `rhyme_keys.json`) |
| `chrome-extension/` | MV3 load-unpacked extension (see that folder’s README) |
| `engine/convert/` | Python convert (methodology source of truth) |
| `engine/models/` | Canonical induced models |
| `engine/scripts/` | Numbered induction stages + `run_phase1.py` / `run_phase2.py` |
| `scripts/sync-models.mjs` | `engine/models` → `docs/models` |
| `scripts/build-rhyme-keys.py` | Builds `docs/models/rhyme_keys.json` |

## Sync

After induction that changes models:

```bash
npm run build                      # sync-models.mjs
python scripts/build-rhyme-keys.py # after rhyme/lexicon/memory changes
```

Site reads **`docs/models` only**.

## Commands

```bash
npx --yes serve docs -p 4173

python -m pip install -r engine/requirements.txt   # ffmpeg on PATH
python engine/scripts/run_phase1.py
python -m engine.cli "You're yes then you're no"
```

Prefer editing existing `engine/scripts/0*.py` over one-offs. When Python convert semantics change, update `docs/js/convert.js` (or call out drift).

## Refs

`README.md`, `CITATIONS.md`, `engine/README.md`, `chrome-extension/README.md`, `engine/analysis/reports/`
