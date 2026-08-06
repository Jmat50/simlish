# Simlish

Static [GitHub Pages](https://pages.github.com/) English→Simlish converter. Everything runs in the browser — no server, no accounts, no telemetry.

**Live:** [https://jmat50.github.io/simlish/](https://jmat50.github.io/simlish/)

The converter is a **line-first**, audio-grounded planner induced from official soundtrack EN|SIMLISH lyric pairs. It does not gloss English word-by-word. It tries to sound like sung Simlish — preserving rhythm, end-rhyme class, and phone-ish onset — the way Maxis lyricists appear to write.

---

## Chrome extension

MV3 extension in [`chrome-extension/`](chrome-extension/). It rewrites visible page text by talking to the Pages **bridge** (`docs/bridge.html`) over `postMessage` — no models or convert logic ship inside the extension.

Full notes: [`chrome-extension/README.md`](chrome-extension/README.md).

### Install (load unpacked)

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** → select the repo’s `chrome-extension/` folder
4. Pin the Simlish action, open any `http(s)` page, toggle **Simlish this page**

Default bridge: `https://jmat50.github.io/simlish/bridge.html`. For local convert, serve `docs/` on port 4173 and set **Bridge URL** → **Use local :4173** in the popup.

### Files required to load

Everything Chrome needs is under `chrome-extension/` (no build step):

| Path | Role |
|------|------|
| `manifest.json` | MV3 manifest |
| `background.js` | Service worker (queue + offscreen) |
| `shared.js` | Bridge URL defaults / batch size |
| `content.js` + `content.css` | Page text rewrite |
| `offscreen.html` + `offscreen.js` | Hidden iframe → Pages bridge |
| `popup.html` + `popup.js` + `popup.css` | Toggle + bridge URL |
| `icons/icon{16,32,48,128}.png` | Action / store icons |

Site-side bridge (already in this repo for Pages deploy): `docs/bridge.html`, `docs/js/bridge.js`, plus `docs/js/convert.js` and `docs/models/`.

---

## How it thinks

Simlish soundtrack lyrics are not a bilingual dictionary. Parallel lines often have fewer tokens than English (~0.8×), nearly the same syllable count (~1.0×), and strong end-rhyme discipline. Content words tend to keep onset and/or rhyme-ish endings (`shake`→`sheeky`, `girl`→`gurn`, `think`/`zonk`-style pairs). Function words are unstable fillers for meter, not glosses.

The planner works **per line**, not per word:

```text
input text
  → split on newlines / sentence boundaries
  → for each line:
       1. phrase memory?  → return official Simlish line (if close enough)
       2. else:
            meter  → target syllable budget for the line
            allocate budgets across tokens
            last content word → rhyme-class ending
            other words       → sound-alike transform (under budget)
       3. reassemble into original punctuation / spacing / casing skeleton
```

That is the whole runtime loop. There is no neural decoder at inference time on the site — only induced JSON models plus a small deterministic planner (`docs/js/convert.js`, ported from `engine/convert/`).

### Design principles (from the corpus)

| Observation | Converter consequence |
|-------------|----------------------|
| Line/phrase mapping dominates; token counts diverge | Prefer whole-line retrieval before word rewrite |
| Syllable ratio ≈ 1.0 | Fit a linear meter model; allocate per-token syllable budgets |
| End rhyme is first-class | Last content word sampled from ARPABET rhyme-class → Simlish endings |
| Sound-alike content words | Lexicon + phone unigram/bigram maps; keep onset if similarity collapses |
| Function words are noisy | Separate empirical maps (`you`, `the`, `to`, …); fill rhythm, don’t translate |

---

## Runtime pipeline (detailed)

### 1. Text splitting

`convertText` splits on newlines (kept), then on `(?<=[.!?])\s+` so each clause is planned independently. Empty / whitespace-only chunks pass through unchanged.

### 2. Phrase memory (nearest-neighbor line recall)

Before inventing anything, the engine asks: *have we seen a nearly identical English line in the official corpus?*

- Corpus: every EN|SIMLISH line pair from official wiki tables (~282 lines in `phrase_memory.json`).
- Features: character n-grams with word boundaries (`char_wb`, n = 3…5).
- Accept if cosine similarity ≥ **0.82**.
- On hit: return the stored Simlish line (with a light UPPERCASE casing match).

### 3. Meter (syllable budget)

If memory misses, measure English line syllables and predict a Simlish target:

\[
\text{target} = \mathrm{round}(a \cdot S_{\mathrm{en}} + b)
\]

Induced fit (current models): **a ≈ 0.988**, **b ≈ 0.053**.

### 4. Rhyme (line-end treatment)

Identify the **last content word**. That token is sampled from a rhyme class via ARPABET rhyme keys (`rhyme_keys.json` in the browser).

### 5. Sound-alike (non-rhyme words)

Lexicon → function-word map → phone map → pad/trim to syllable budget.

### 6. Reassembly

Original punctuation / spacing / casing skeleton is preserved. Lexicon, function, phone-map, and rhyme bags sample randomly — same input can vary across runs.

---

## Where the models come from

Models are **induced**, not hand-authored. Research lives under [`engine/`](engine/); the site only consumes exported JSON under `docs/models/`.

### Evidence constraints

- **Orthography source:** official Sims soundtrack wiki EN|SIMLISH tables only (`wiki_official`). No fan sheets, YouTube description lyrics, or ASR spellings as Simlish text.
- **YouTube audio:** allowed for research timing / prosody of official performances. Whisper is lyrics-constrained alignment (timing), never a spelling source.
- **Shareable artifacts:** aggregated maps and model JSON — not raw audio dumps or full lyric sheet redistribution.

### Induction sketch

```text
01 catalog  →  02 official parallel lyrics
            →  05 text analysis (soft align + rhyme + syllable ratios)
            →  08 induce soundalike / rhyme / meter / phrase memory / function words
03–07 audio resolve/download/align/prosody
09 phrase LM train (optional; site uses NN memory, not torch weights)
10 converter build / smoke
11 eval
```

Canonical models: `engine/models/`. Sync to the site with `npm run build` and `python scripts/build-rhyme-keys.py`.

---

## Site models & code map

| Artifact | Role at runtime |
|----------|-----------------|
| `docs/models/phrase_memory.json` | NN line recall |
| `docs/models/soundalike_rules.json` | Lexicon + phone maps |
| `docs/models/function_words.json` | Function-word fillers |
| `docs/models/rhyme_classes.json` | End-rhyme bags |
| `docs/models/rhyme_keys.json` | Word → ARPABET rhyme key |
| `docs/models/syllable_templates.json` | Meter `a`, `b` |
| `docs/js/convert.js` | Browser planner |
| `engine/convert/*.py` | Source-of-truth methodology / CLI |

URL param: `t` (shareable text).

---

## Local preview

```bash
npm install
npm run build
npx --yes serve docs -p 4173
```

Open `http://localhost:4173`. Pages deploy from `main` / `/docs` with relative asset paths (`./js/…`, `./models/…`).

Extension bridge: `http://127.0.0.1:4173/bridge.html` (live: `https://jmat50.github.io/simlish/bridge.html`).

### Research CLI (optional)

```bash
python -m pip install -r engine/requirements.txt   # from repo root; ffmpeg on PATH
python -m engine.cli "You're yes then you're no"
```

See [`engine/README.md`](engine/README.md) for phase1/phase2 induction orchestration.

---

## License

MIT for this repository’s code and UI. Training-data provenance: [CITATIONS.md](CITATIONS.md). Not affiliated with or endorsed by Electronic Arts / Maxis.
