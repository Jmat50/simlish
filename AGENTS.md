# AGENTS.md

Guidance for AI agents working in this repository.

## What this project is

Three coupled pieces:

1. **Static translator** (`docs/`) — GitHub Pages site at `/simlish/`. Client-side only (no backend, no telemetry). Ships **two engines** selectable in the UI:
   - **v2** (default) — sound-alike / rhyme / meter / phrase-memory converter from induced JSON models.
   - **v1** — Generative Markov + Orthodox sqlite lookup (unchanged methodology).
2. **Lyric dictionary pipeline** (`DICTIONARY/`) — builds `dictionary.sqlite` from **official** Sims soundtrack EN|SIMLISH wiki tables. Powers **v1 Orthodox** only.
3. **v2 research stack** (`v2/`) — audio-grounded induction (official lyrics + YouTube audio rips → models). Independent of the v1 Markov/Orthodox code path. Site consumes **exported model JSON** only (browser port in `docs/js/v2-convert.js`).

Live site: https://jmat50.github.io/simlish/

## Non‑negotiable product rules

- **Official soundtrack lyrics only for Simlish orthography.** Training / dictionary targets come from wiki `wiki_official` EN|SIMLISH tables. Do **not** use fan sheets, YouTube description lyrics, or ASR transcripts as Simlish spellings for the dictionary or v2 lyric targets.
- **Whisper/ASR is not an orthography source.** It may appear in `v2/` only as lyrics-constrained **audio alignment** (timing), never as a replacement for official wiki Simlish text. Do not reintroduce Whisper stages into `DICTIONARY/`.
- **YouTube audio** is allowed under `v2/` for research rips of official performances. Do not wire YouTube downloads into the `DICTIONARY/` pipeline or treat video titles/descriptions as lyric evidence.
- Generative (v1) is **not** canon Sims dialogue and not a bilingual MT system — it samples phonotactic Markov weights.
- Orthodox (v1) must stay backed by **`docs/dictionary.sqlite`** via sql.js (read-only). Do not revive a separate `dictionary.json` export as the source of truth.
- **v2 site runtime** must stay model-driven JSON under `docs/v2-models/` + `docs/js/v2-convert.js`. Do not call Python/`v2.convert` from the Pages site.
- Keep asset paths **relative** (`./js/…`, `./weights/…`, `./dictionary.sqlite`, `./v2-models/…`) so Pages works under `/simlish/`.
- Do not redistribute full copyrighted lyric sheets; shareable artifacts are aggregated word maps, sqlite, and induced rule/model JSON (not raw audio dumps).

## Repository map

| Path | Role |
|------|------|
| `docs/` | Deployed site (HTML/CSS/JS, weights, sqlite, v2 models, vendored sql.js) |
| `docs/js/` | Translator UI + engines: `app.js`, `v2-convert.js`, `rewrite.js`, `markov.js`, `dictionary-db.js`, … |
| `docs/v2-models/` | Browser copies of induced v2 JSON (+ `rhyme_keys.json` for CMU-style rhyme lookup) |
| `docs/vendor/sql.js/` | Vendored sql.js wasm (refresh via `npm run build:dictionary`) |
| `DICTIONARY/` | Python pipeline + canonical `dictionary.sqlite` (v1 Orthodox) |
| `DICTIONARY/pipeline/` | Numbered stages `01`…`12` (gaps are intentional — removed paths) |
| `v2/` | Independent research: catalog, lyrics, audio, analysis, models, convert, CLI |
| `v2/convert/` | Python converter (line-first); source of truth for methodology |
| `v2/models/` | Canonical induced models before sync into `docs/v2-models/` |
| `scripts/` | `build-weights.mjs`, `sync-dictionary.mjs`, `build-rhyme-keys.py`, `smoke-markov.mjs`, … |
| `data/profiles/` | Raw IPA lists (gitignored); needed only to rebuild v1 weights |

## Site engines (`docs/`)

Toolbar **Engine** thumb switch: **v2** (on, default) ↔ **v1** (off). URL param: `engine=v2|v1` (omit or any non-`v1` → v2).

| Engine | Behavior |
|--------|----------|
| **v2** (default) | Line-first: phrase memory (char n-gram NN) → else sound-alike + end-rhyme class + syllable budget. Mode / Profile / Show IPA are UI-disabled (IPA N/A). |
| **v1** | Restores Mode + Profile + IPA. |

### v1 modes (only when Engine = v1)

| Mode | Behavior |
|------|----------|
| **Generative** | Deterministic Markov rewrite per token + profile (`en_US` / `en_UK`). |
| **Orthodox** | Per-word `SELECT` on `dictionary` table; multi-form → random pick; miss → Generative fallback. |

Key modules:

- `docs/js/app.js` — UI, engine toggle, URL params `t`, `lang`, `mode`, `engine`, `ipa`.
- `docs/js/v2-convert.js` — browser port of v2 convert (loads `./v2-models/*.json`).
- `docs/js/rewrite.js` — v1 tokenization, casing, Generative vs Orthodox.
- `docs/js/dictionary-db.js` — load sql.js + `dictionary.sqlite`, `PRAGMA query_only`, prepared lookup.

After changing the dictionary DB **or** v2 models: sync into `docs/` (see Sync rule) before assuming the site is updated.

## Dictionary pipeline (`DICTIONARY/`)

```text
01_fetch_wiki → 02_parse_catalog → 03_parse_official_lyrics
  → 08_align_lyrics → 09_build_dictionary
  → 11_strip_english_from_simlish → 12_consensus_prune
  → 10_validate_report
```

`run_all.py` then **copies** `DICTIONARY/dictionary.sqlite` → `docs/dictionary.sqlite`.

Important filters (keep them):

- Strip English/vocables/non-Latin tokens from Simlish columns (`english_filter.py`, stage `11`).
- Align/build use `source_kind='wiki_official'` only.
- Consensus prune keeps multi-song-confirmed forms when applicable (stage `12`).

Schema: `DICTIONARY/schema.sql`. Wide table `dictionary` (`original_word`, `simlish_1`…`10`, `simlish_extra`, `occurrence_count`).

## v2 research stack (`v2/`)

Hard separation from v1: do not import `docs/js` Markov code into `v2/`, and do not teach v1 Orthodox to depend on `v2/` Python at runtime.

```text
01_fetch_official_catalog → 02_fetch_official_parallel_lyrics
  → 03_resolve_youtube_official → 04_download_audio
  → 05_analyze_text_parallel → 06_align_audio_to_lyrics → 07_analyze_audio_prosody
  → 08_induce_rules_and_stats → 09_train_phrase_model → 10_build_converter
  → 11_eval_and_report
```

Orchestrators: `v2/scripts/run_phase1.py` (7 parallel songs), `v2/scripts/run_phase2.py` (full catalog audio).

CLI (repo root): `python -m v2.cli "…"`.

Induced models (canonical under `v2/models/`):

- `soundalike_rules.json`, `rhyme_classes.json`, `syllable_templates.json`
- `phrase_memory.json`, `function_words.json`
- `phrase_lm/` — torch checkpoint (gitignored); site uses `phrase_memory` NN, not the LM weights

Site also needs `docs/v2-models/rhyme_keys.json` (word → ARPABET rhyme key) via `python scripts/build-rhyme-keys.py` after model refreshes (browser has no `pronouncing` package).

Audio binaries are gitignored (`v2/.gitignore`); keep JSON metadata / induced rule JSON as appropriate.

## Common commands

```bash
# Site
npm install
npm run build              # weights (if profiles present) + sync sqlite/vendor (+ copy v2 models when present)
npm run build:dictionary   # copy DICTIONARY/dictionary.sqlite → docs/ + refresh sql.js vendor + copy v2/models → docs/v2-models
python scripts/build-rhyme-keys.py   # refresh docs/v2-models/rhyme_keys.json
npm run smoke
npx --yes serve docs -p 4173

# Dictionary (v1 Orthodox)
cd DICTIONARY
python -m pip install -r requirements.txt
python run_all.py          # full pipeline + sync to docs/

# v2 research (from repo root)
cd v2 && python -m pip install -r requirements.txt   # ffmpeg on PATH; optional Chrome for yt-dlp
python v2/scripts/run_phase1.py
python -m v2.cli "You're yes then you're no"
python v2/scripts/run_phase2.py
```

Weights rebuild needs `data/profiles/*/words.csv` (via `node scripts/download-profiles.mjs`).

## Coding conventions

- **Site:** vanilla ES modules, no bundler required for Pages. Prefer small focused files matching existing style.
- **v1 vs v2:** keep convert paths separate. UI may share chrome; conversion logic must not blend Markov weights with v2 sound-alike rules.
- **Pipeline (`DICTIONARY/`):** Python 3, stages as runnable scripts; shared code under `DICTIONARY/pipeline/lib/`.
- **v2:** Python package under `v2/`; run from repo root so `python -m v2…` resolves. Prefer editing existing numbered scripts over parallel one-offs unless the user asks.
- Prefer editing existing stages over adding parallel one-off scripts unless the user asks.
- Do not commit bulky raw lyrics/audio; respect `.gitignore` (`DICTIONARY/data/lyrics/…`, `v2` wavs, cache, etc.).
- `docs/vendor/sql.js/` is vendored for static hosting — update via `npm run build:dictionary`, not hand-edits.
- When touching Orthodox lookup or sqlite schema, update smoke coverage in `scripts/smoke-markov.mjs` if behavior changes.
- When changing v2 convert semantics in Python, update `docs/js/v2-convert.js` to match (or call out the drift).

## Sync rule (avoid drift)

| Canonical | Site copy |
|-----------|-----------|
| `DICTIONARY/dictionary.sqlite` | `docs/dictionary.sqlite` |
| `v2/models/*.json` (rules / memory) | `docs/v2-models/` (same basenames) |
| (built) rhyme key index | `docs/v2-models/rhyme_keys.json` via `scripts/build-rhyme-keys.py` |

Always sync after pipeline / induction changes that mutate those artifacts:

- `python DICTIONARY/run_all.py`, and/or
- `npm run build:dictionary` (sqlite + vendor + v2 model JSON copy), and
- `python scripts/build-rhyme-keys.py` after rhyme/lexicon/memory changes

v1 Orthodox reads the **docs** sqlite only. v2 site reads **docs/v2-models** only.

## Out of scope / do not re-add

- Fan lyric scrapers or YouTube **description/title lyrics** as Simlish orthography (either pipeline).
- Whisper/ASR as a Simlish **spelling** source; Whisper stages inside `DICTIONARY/`.
- Server-side APIs, auth, analytics.
- OPFS / COOP-COEP persistence for sqlite (unnecessary; GH Pages cannot set those headers cleanly).
- Claiming EA/Maxis endorsement or shipping full song lyric dumps / audio binaries in git.
- Merging v1 Markov and v2 into a single hybrid converter without an explicit product decision.

## References

- Root `README.md`, `CITATIONS.md`
- `DICTIONARY/README.md`, `DICTIONARY/CITATIONS.md`
- `v2/README.md`
- Coverage after a dictionary run: `DICTIONARY/data/reports/coverage.md`
- v2 eval / smoke notes: `v2/analysis/reports/`
