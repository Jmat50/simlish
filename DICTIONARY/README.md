# Simlish Lyric Dictionary

Research pipeline that builds `dictionary.sqlite` from [Songs in Simlish](https://sims.fandom.com/wiki/Songs_in_Simlish).

## Deliverable

`dictionary.sqlite` table `dictionary`:

| column | meaning |
|--------|---------|
| `original_word` | token from the original-language lyric |
| `simlish_1`…`simlish_10` | observed Simlish spellings (frequency order) |
| `simlish_extra` | JSON array if more than 10 forms |
| `occurrence_count` | alignment evidence count |

## Quick start

```bash
cd DICTIONARY
python -m pip install -r requirements.txt
python run_all.py --from 1 --to 3          # wiki + official lyrics (fast)
python run_all.py --from 4 --to 10         # originals, YouTube, ASR, aggregate
```

Requires `ffmpeg` on PATH for audio extraction. Optional: set `GENIUS_ACCESS_TOKEN` (not required; lrclib is default).

## Notes

- Official wiki EN/SIMLISH tables are the high-confidence seed.
- Other songs use lrclib originals + fan Simlish sheets (azlyrics.biz / similar) when available.
- YouTube audio → Whisper is implemented, but YouTube often requires browser cookies (`yt-dlp --cookies-from-browser`); stage `05b` covers the gap with fan lyric pages.
- Raw audio and full lyric dumps are gitignored; the sqlite word map is the shareable artifact.
- Simlish is not a 1:1 cipher — this dictionary is an empirical many-to-many map from parallel lines.

See `CITATIONS.md` and `data/reports/coverage.md` after a run.
