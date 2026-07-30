# Simlish

Static [GitHub Pages](https://pages.github.com/) app that rewrites your text into language-sounding nonsense using client-side Markov phonotactics. Everything runs in the browser — no server, no accounts, no telemetry.

**Live:** after Pages is enabled → [https://jmat50.github.io/simlish/](https://jmat50.github.io/simlish/)

## What it does

- **Mode: Generative** — deterministic Markov phonotactic rewrite (same input → same nonsense for a profile).
- **Mode: Orthodox** — per-word lookup against `docs/dictionary.sqlite` via [sql.js](https://sql.js.org/) in the browser; missing words fall back to Generative. Multi-form entries pick a Simlish spelling at random.
- Preserves punctuation, whitespace, numbers, and casing.
- Default display is **ASCII romanization** of IPA; toggle **Show IPA** for the raw phones.
- Profiles: `en_US`, `en_UK` (sparse ~10–16 KB JSON each).

Generative mode is **not** a bilingual translator and not canon The Sims dialogue — it samples phoneme transitions trained on real IPA dictionaries. Orthodox mode uses empirical EN↔Simlish pairs from official soundtrack lyric tables (see `DICTIONARY/`).

## Local preview

```bash
npm run build          # weights + sync dictionary.sqlite into docs/
npm run smoke
npx --yes serve docs -p 4173
```

Open `http://localhost:4173`.

## Building weight tables

Raw IPA lists live under `data/profiles/` (gitignored). Populate them once:

```bash
node scripts/download-profiles.mjs
npm run build:weights
```

Outputs committed site assets:

- `docs/weights/en_US.json`
- `docs/weights/en_UK.json`
- `docs/dictionary.sqlite` (`npm run build:dictionary` copies from `DICTIONARY/`)
- `docs/vendor/sql.js/` (sql.js wasm for Orthodox mode)

## GitHub Pages

Repo Settings → Pages → **Deploy from a branch** → `main` / `/docs`.

Asset paths are relative (`./js/…`, `./weights/…`) so the project site works at `/simlish/`.

Shareable links use `?t=` (text), `?lang=en_US|en_UK`, `?mode=generative|orthodox`, and optional `?ipa=1`. Long text is omitted from the URL (privacy / length).

## License

MIT for this repository’s code and UI. See [CITATIONS.md](CITATIONS.md) for training-data provenance.
