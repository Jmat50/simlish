# Simlish engine — audio-grounded conversion

English→Simlish research + convert stack. The GitHub Pages site consumes
exported JSON under `engine/models/` (synced to `docs/models/`).

## Method (summary)

1. Official soundtrack catalog + EN|SIMLISH wiki lyric tables only.
2. Rip Simlish performances from YouTube (research reference).
3. Induce sound-alike, rhyme, and meter models from parallel lines + audio.
4. Convert with a **line-first** planner (rhyme + syllable budget + sound-alike),
   not a 1:1 English dictionary gloss.

## Quick start

```bash
# from repo root
python -m pip install -r engine/requirements.txt
# ffmpeg on PATH; for YouTube bot-checks: Chrome logged into YouTube
python engine/scripts/run_phase1.py
python -m engine.cli "You're yes then you're no"
python engine/scripts/run_phase2.py
```

## Layout

catalog, lyrics, audio, analysis, models, convert, scripts.

Audio binaries are gitignored; JSON metadata and induced rule models are kept.
