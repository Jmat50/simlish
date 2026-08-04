# AGENTS.md

Guidance for AI agents working in this repository.

## What this project is

Three coupled pieces:

1. **Static translator** (`docs/`) — GitHub Pages site at `/simlish/`. Client-side only (no backend, no telemetry).
   - Single convert engine: sound-alike / rhyme / meter / phrase-memory from induced JSON models (`docs/js/convert.js` + `docs/models/`).
   - **Speak** — stock [Kokoro](https://github.com/hexgrad/kokoro) TTS in-browser (`docs/js/speak.js` + Simlish→IPA in `docs/js/simlish-ipa.js`). Not an official Sims voice.
   - **Extension bridge** — `docs/bridge.html` + `docs/js/bridge.js` expose convert over `postMessage` (`simlish-bridge` protocol) for the Chrome extension. No HTTP translate API (Pages is static).
2. **Research / induction stack** (`engine/`) — audio-grounded induction (official lyrics + YouTube audio rips → models). Site consumes **exported model JSON** only (browser port in `docs/js/convert.js`).
3. **Chrome extension** (`chrome-extension/`) — MV3; offscreen iframe loads the Pages bridge; content script rewrites page text. Does **not** vendor models or convert logic.

Live site: https://jmat50.github.io/simlish/

## Non‑negotiable product rules

- **Official soundtrack lyrics only for Simlish orthography.** Training targets come from wiki `wiki_official` EN|SIMLISH tables. Do **not** use fan sheets, YouTube description lyrics, or ASR transcripts as Simlish spellings.
- **Whisper/ASR is not an orthography source.** It may appear in `engine/` only as lyrics-constrained **audio alignment** (timing), never as a replacement for official wiki Simlish text.
- **YouTube audio** is allowed under `engine/` for research rips of official performances. Do not treat video titles/descriptions as lyric evidence.
- **Site runtime** must stay model-driven JSON under `docs/models/` + `docs/js/convert.js`. Do not call Python/`engine.convert` from the Pages site.
- Keep asset paths **relative** (`./js/…`, `./models/…`) so Pages works under `/simlish/`.
- Do not redistribute full copyrighted lyric sheets; shareable artifacts are aggregated word maps and induced rule/model JSON (not raw audio dumps).
- **Never commit** Sims package rips, decoded EA WAVs, or EA-derived TTS fine-tune weights to the public repo or Pages. Public Speak uses stock Kokoro only.

## Repository map

| Path | Role |
|------|------|
| `docs/` | Deployed site (HTML/CSS/JS, models) |
| `docs/bridge.html` | Extension RPC page (UI-less); framed by `chrome-extension/` offscreen doc |
| `docs/js/` | Translator UI + convert: `app.js`, `convert.js`, `bridge.js`, `speak.js`, … |
| `docs/models/` | Browser copies of induced JSON (+ `rhyme_keys.json` for CMU-style rhyme lookup) |
| `chrome-extension/` | MV3 extension (load unpacked from this folder); translations via Pages bridge only |
| `engine/` | Research: catalog, lyrics, audio, analysis, models, convert, CLI |
| `engine/convert/` | Python converter (line-first); source of truth for methodology |
| `engine/models/` | Canonical induced models before sync into `docs/models/` |
| `scripts/` | `sync-models.mjs`, `build-rhyme-keys.py`, … |

## Site convert (`docs/`)

Line-first planner: phrase memory (char n-gram NN) → else sound-alike + end-rhyme class + syllable budget.

Key modules:

- `docs/js/app.js` — UI, Speak/Stop, URL param `t`.
- `docs/js/convert.js` — browser port of convert (loads `./models/*.json`).
- `docs/js/bridge.js` — `postMessage` RPC wrapping `loadModels` / `convertText` for the extension.
- `docs/js/speak.js` / `docs/js/simlish-ipa.js` — stock Kokoro Speak + Simlish IPA mapping.
- `chrome-extension/` — content script + offscreen iframe client; see `chrome-extension/README.md`.

After induction changes that mutate models: sync into `docs/` (see Sync rule) before assuming the site is updated.

## Research stack (`engine/`)

```text
01_fetch_official_catalog → 02_fetch_official_parallel_lyrics
  → 03_resolve_youtube_official → 04_download_audio
  → 05_analyze_text_parallel → 06_align_audio_to_lyrics → 07_analyze_audio_prosody
  → 08_induce_rules_and_stats → 09_train_phrase_model → 10_build_converter
  → 11_eval_and_report
```

Orchestrators: `engine/scripts/run_phase1.py` (7 parallel songs), `engine/scripts/run_phase2.py` (full catalog audio).

CLI (repo root): `python -m engine.cli "…"`.

Induced models (canonical under `engine/models/`):

- `soundalike_rules.json`, `rhyme_classes.json`, `syllable_templates.json`
- `phrase_memory.json`, `function_words.json`
- `phrase_lm/` — torch checkpoint (gitignored); site uses `phrase_memory` NN, not the LM weights

Site also needs `docs/models/rhyme_keys.json` via `python scripts/build-rhyme-keys.py` after model refreshes.

Audio binaries are gitignored (`engine/.gitignore`); keep JSON metadata / induced rule JSON as appropriate.

## Common commands

```bash
# Site
npm install
npm run build              # sync engine/models → docs/models
python scripts/build-rhyme-keys.py
npx --yes serve docs -p 4173

# Research (from repo root)
python -m pip install -r engine/requirements.txt   # ffmpeg on PATH
python engine/scripts/run_phase1.py
python -m engine.cli "You're yes then you're no"
python engine/scripts/run_phase2.py
```

## Coding conventions

- **Site:** vanilla ES modules, no bundler required for Pages. Prefer small focused files matching existing style.
- **Engine:** Python package under `engine/`; run from repo root so `python -m engine…` resolves. Prefer editing existing numbered scripts over parallel one-offs unless the user asks.
- Do not commit bulky raw lyrics/audio; respect `.gitignore`.
- When changing convert semantics in Python, update `docs/js/convert.js` to match (or call out the drift).

## Sync rule (avoid drift)

| Canonical | Site copy |
|-----------|-----------|
| `engine/models/*.json` (rules / memory) | `docs/models/` (same basenames) |
| (built) rhyme key index | `docs/models/rhyme_keys.json` via `scripts/build-rhyme-keys.py` |

Always sync after induction changes:

- `npm run build` (or `npm run build:models`), and
- `python scripts/build-rhyme-keys.py` after rhyme/lexicon/memory changes

Site reads **docs/models** only.

## Out of scope / do not re-add

- Fan lyric scrapers or YouTube **description/title lyrics** as Simlish orthography.
- Whisper/ASR as a Simlish **spelling** source.
- Publishing EA-derived TTS weights or ripped Sims VO on Pages / public Hub.
- Server-side APIs, auth, analytics. (The extension bridge is static `postMessage` only.)
- Claiming EA/Maxis endorsement or shipping full song lyric dumps / audio binaries in git.
- Reintroducing a second convert engine (Markov / Orthodox / versioned “v1/v2/v3” stacks).
- Vendoring `docs/models` / `convert.js` inside `chrome-extension/` (Pages bridge is the translation runtime).

## References

- Root `README.md`, `CITATIONS.md`
- `engine/README.md`
- `chrome-extension/README.md`
- Engine eval / smoke notes: `engine/analysis/reports/`
