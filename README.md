# Simlish

Static [GitHub Pages](https://pages.github.com/) English→Simlish converter. Everything runs in the browser — no server, no accounts, no telemetry.

**Live:** [https://jmat50.github.io/simlish/](https://jmat50.github.io/simlish/)

The site’s **default engine is v2**: a line-first, audio-grounded planner induced from official soundtrack EN|SIMLISH lyric pairs. It does not gloss English word-by-word. It tries to sound like sung Simlish — preserving rhythm, end-rhyme class, and phone-ish onset — the way Maxis lyricists appear to write.

An older **v1** engine (Markov phonotactics + Orthodox sqlite lookup) remains available via the Engine toggle (`?engine=v1`).

A **Chrome extension** lives in [`chrome-extension/`](chrome-extension/) and rewrites page text by talking to the Pages **bridge** (`docs/bridge.html`) over `postMessage` — load unpacked from that folder (see [`chrome-extension/README.md`](chrome-extension/README.md)).

---

## How v2 thinks

Simlish soundtrack lyrics are not a bilingual dictionary. Parallel lines often have fewer tokens than English (~0.8×), nearly the same syllable count (~1.0×), and strong end-rhyme discipline. Content words tend to keep onset and/or rhyme-ish endings (`shake`→`sheeky`, `girl`→`gurn`, `think`/`zonk`-style pairs). Function words are unstable fillers for meter, not glosses.

v2 therefore plans **per line**, not per word:

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

That is the whole runtime loop. There is no neural decoder at inference time on the site — only induced JSON models plus a small deterministic planner (`docs/js/v2-convert.js`, ported from `v2/convert/`).

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
- Features: character n-grams with word boundaries (`char_wb`, n = 3…5). Python uses scikit-learn TF–IDF + cosine; the browser port uses sparse count vectors + cosine over the same n-gram set.
- Accept if cosine similarity ≥ **0.82** (`NN_RETRIEVAL_THRESHOLD`).
- On hit: return the stored Simlish line (with a light UPPERCASE casing match). Skip meter / rhyme / sound-alike entirely.

This is why familiar lyric hooks often come out “canon-ish”: the planner is allowed to quote induced memory when the input is close enough.

### 3. Meter (syllable budget)

If memory misses, measure English line syllables and predict a Simlish target:

\[
\text{target} = \mathrm{round}(a \cdot S_{\mathrm{en}} + b)
\]

Induced fit (current models): **a ≈ 0.988**, **b ≈ 0.053** over 282 parallel lines — essentially “keep the same number of syllables.”

Budgets are then allocated across tokens proportional to each English word’s syllable weight (minimum 1), then nudged so the budgets sum exactly to `target`. Each non-rhyme word’s sound-alike pass is asked to land near its budget (±1 for lexicon hits; pad/trim for generative spelling).

### 4. Rhyme (line-end treatment)

Identify the **last content word** (skipping a small function-word set: `the`, `a`, `and`, `to`, …). That token is *not* sound-alike-transformed; it is sampled from a rhyme class:

1. Map the English word → ARPABET rhyme key = phones from the last stressed vowel onward (CMU-style via `pronouncing` in Python; precomputed `rhyme_keys.json` in the browser).
2. Look up `rhyme_classes.json`: key → weighted bag of Simlish endings observed as line-final forms for English words in that class.
3. Sample with multiplicity (`n` repetitions in the bag). Miss → fall back to sound-alike on that word.

Example classes from induction: `OW1` → `cou` / `oh` / …; `AY1 L` → `asmil` / …; `ER1 L` → `gurn` / …. So “no” and other `OW1` endings preferentially become Simlish forms that actually ended English lines with that rhyme shape in the soundtrack corpus.

### 5. Sound-alike (content + function words)

For every other token, `SoundAlike.transform(word, target_syll)` runs a cascade:

1. **Function-word map** — if the word is in `function_words.json`, pick a ranked Simlish alternate at random (rhythm filler).
2. **Lexicon** — if the word appears in induced soft-alignments (`soundalike_rules.json` lexicon, top forms), pick among the top 3, preferring syllable distance ≤ 1 from budget.
3. **Phone rewrite** — approximate Latin spelling → coarse phone classes (`ch`→`CH`, `sh`→`SH`, vowels → `A|E|I|O|U`, …). Walk the phone sequence:
   - Prefer **bigram** phone maps (`T+IH` style keys) when present.
   - Else **unigram** phone map.
   - Else mutate vowels randomly among `AEIOU`, keep consonants.
4. **Render** phones back to ASCII spelling (`CH`→`ch`, `AY`→`ai`, …).
5. **Enforce budget** — if too short, append CV pads (`ba`, `di`, `ko`, `su`, `la`); if too long, trim characters (bounded loops).
6. **Onset rescue** — if phone similarity to the original drops below 0.25, force the first letter of the English word onto the result so the form still “starts like” the source.

Approximate phones and similarity use Levenshtein edit distance over those symbols — not full CMU G2P at rewrite time (G2P is used for English rhyme keys / syllable counts in the Python research path).

### 6. Reassembly

Original non-word pieces (punctuation, spaces) are preserved via a split-keep of `[A-Za-z']+ | punctuation | whitespace`. Each word slot gets the converted form with casing matched (`UPPER`, `Title`, else lower). Leftover Simlish tokens (rare) are appended.

**Stochastic note:** lexicon, function, phone-map, and rhyme bags all sample randomly. Same input can vary across runs; there is no seed in the browser port.

---

## Where the models come from

v2 is **induced**, not hand-authored rules. Research lives under `v2/`; the site only consumes exported JSON under `docs/v2-models/`.

### Evidence constraints

- **Orthography source:** official Sims soundtrack wiki EN|SIMLISH tables only (`wiki_official`). No fan sheets, YouTube description lyrics, or ASR spellings as Simlish text.
- **YouTube audio:** allowed for research timing / prosody of official performances. Whisper is lyrics-constrained alignment (timing), never a spelling source.
- **Shareable artifacts:** aggregated maps and model JSON — not raw audio dumps or full lyric sheet redistribution.

### Induction sketch

```text
01 catalog  →  02 official parallel lyrics
            →  05 text analysis (soft align + rhyme + syllable ratios)
            →  08 induce soundalike / rhyme / meter / phrase memory / function words
03–07 audio resolve/download/align/prosody  (grounds timing claims; rhyme stays text-primary)
09 phrase LM train (optional; site uses NN memory, not torch weights)
10 converter build / smoke
11 eval
```

**Soft alignment (stage 05):** Needleman–Wunsch over approximate phones of EN vs Simlish tokens, gap −0.35, diagonal score from phone similarity (+ onset/coda bonuses). Pairs with similarity ≥ **0.45** become sound-alike observations (~600 kept). Those feed:

- word lexicon (`en` → counted Simlish forms)
- phone unigram/bigram maps (top transforms)

**Rhyme map:** for each parallel line, take English last token’s rhyme key and Simlish last token; accumulate counts → `rhyme_classes.json` (~91 keys).

**Meter:** ordinary least-squares of Simlish line syllables on English line syllables → `syllable_templates.json`.

**Phrase memory:** raw list of `{original, simlish, song_id}` line pairs.

Current induced footprint (approx.): **183** lexicon words, **237** phone-map keys, **91** rhyme classes, **21** function words, **282** memory lines.

Canonical models: `v2/models/`. Sync to the site with `npm run build:dictionary` (copies JSON) and `python scripts/build-rhyme-keys.py` (browser rhyme-key index).

---

## Site models & code map

| Artifact | Role at runtime |
|----------|-----------------|
| `docs/v2-models/phrase_memory.json` | NN line recall |
| `docs/v2-models/soundalike_rules.json` | Lexicon + phone maps |
| `docs/v2-models/function_words.json` | Function-word fillers |
| `docs/v2-models/rhyme_classes.json` | End-rhyme bags |
| `docs/v2-models/rhyme_keys.json` | Word → ARPABET rhyme key (no `pronouncing` in browser) |
| `docs/v2-models/syllable_templates.json` | Meter `a`, `b` |
| `docs/js/v2-convert.js` | Browser planner (default engine) |
| `v2/convert/*.py` | Source-of-truth methodology / CLI |

URL params: `t` (text), `engine=v2|v1` (default v2), plus v1-only `lang`, `mode`, `ipa`.

---

## v2 vs v1 (why they coexist)

| | **v2 (default)** | **v1** |
|--|------------------|--------|
| Goal | Sound like soundtrack Simlish lines | Language-sounding nonsense / lyric-dict glosses |
| Unit | Line-first planner | Per-token rewrite |
| Knowledge | Induced sound-alike, rhyme, meter, phrase memory | Markov IPA weights + `dictionary.sqlite` |
| Modes | Single convert path | Generative vs Orthodox |
| IPA UI | N/A | Optional Show IPA |

v1 Generative samples phonotactic Markov chains trained on real IPA dictionaries. v1 Orthodox does per-word `SELECT` on official lyric-derived pairs, with Generative fallback. Neither path shares convert logic with v2.

---

## Local preview

```bash
npm install
npm run build          # weights (if profiles present) + sync sqlite + v2 models
npm run smoke
npx --yes serve docs -p 4173
```

Open `http://localhost:4173`. Pages deploy from `main` / `/docs` with relative asset paths (`./js/…`, `./v2-models/…`).

Extension bridge (for the Chrome extension offscreen iframe): `http://127.0.0.1:4173/bridge.html` (live: `https://jmat50.github.io/simlish/bridge.html`).

### Research CLI (optional)

```bash
python -m pip install -r v2/requirements.txt   # from repo root; ffmpeg on PATH
python -m v2.cli "You're yes then you're no"
```

See `v2/README.md` for phase1/phase2 induction orchestration.

---

## License

MIT for this repository’s code and UI. Training-data provenance: [CITATIONS.md](CITATIONS.md). Not affiliated with or endorsed by Electronic Arts / Maxis.
