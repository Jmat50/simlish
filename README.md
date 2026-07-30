# Simlish

Static [GitHub Pages](https://pages.github.com/) app that rewrites your text into language-sounding nonsense using client-side Markov phonotactics. Everything runs in the browser — no server, no accounts, no telemetry.

**Live:** after Pages is enabled → [https://jmat50.github.io/simlish/](https://jmat50.github.io/simlish/)

## What it does

- Deterministic **word-aligned rewrite**: the same input token always maps to the same nonsense word for a given profile.
- Preserves punctuation, whitespace, numbers, and casing.
- Default display is **ASCII romanization** of IPA; toggle **Show IPA** for the raw phones.
- Profiles: `en_US`, `en_UK` (sparse ~10–16 KB JSON each).

This is **not** a bilingual translator and not canon The Sims dialogue — it samples phoneme transitions trained on real IPA dictionaries.

## Local preview

```bash
npm run build:weights   # needs data/profiles/*/words.csv
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

## GitHub Pages

Repo Settings → Pages → **Deploy from a branch** → `main` / `/docs`.

Asset paths are relative (`./js/…`, `./weights/…`) so the project site works at `/simlish/`.

Shareable links use `?t=` (text), `?lang=en_US|en_UK`, and optional `?ipa=1`. Long text is omitted from the URL (privacy / length).

## License

MIT for this repository’s code and UI. See [CITATIONS.md](CITATIONS.md) for training-data provenance.
