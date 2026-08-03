# Simlish v2 — Audio-Grounded Conversion

Independent English→Simlish research stack. **Does not use** the v1 Markov /
Orthodox translator under `docs/`.

## Method (summary)

1. Official soundtrack catalog + EN|SIMLISH wiki lyric tables only.
2. Rip Simlish performances from YouTube (research reference).
3. Induce sound-alike, rhyme, and meter models from parallel lines + audio.
4. Convert with a **line-first** planner (rhyme + syllable budget + sound-alike),
   not a 1:1 English dictionary gloss.

## Quick start

```bash
cd v2
python -m pip install -r requirements.txt
# ffmpeg on PATH; for YouTube bot-checks: Chrome logged into YouTube
python scripts/run_phase1.py
python -m v2.cli "You're yes then you're no"
python scripts/run_phase2.py   # full catalog audio after phase1
```

Run scripts from the **repo root** (`C:\VIsual Studio\simlish`) so imports resolve:

```bash
python -m v2.scripts.run_phase1
# or:
python v2/scripts/run_phase1.py
```

## Layout

See plan: catalog, lyrics, audio, analysis, models, convert, scripts.

Audio binaries are gitignored; JSON metadata and induced rule models are kept.
