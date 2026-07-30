# Simlish Lyric Dictionary

Research pipeline that builds `dictionary.sqlite` from official parallel lyric
tables on [Songs in Simlish](https://sims.fandom.com/wiki/Songs_in_Simlish).

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
python run_all.py
```

## Notes

- **Official soundtrack only.** Simlish comes exclusively from wiki EN|SIMLISH
  tables for songs that appear on The Sims game soundtracks.
- Fan covers, fan lyric sheets, YouTube, and Whisper ASR are not used.
- Running `python run_all.py` rebuilds `dictionary.sqlite` and copies it to
  `../docs/dictionary.sqlite` for the GitHub Pages Orthodox translator
  (read via sql.js in the browser).
- Raw lyric dumps are gitignored; the sqlite word map is the shareable artifact.
- Simlish is not a 1:1 cipher — this dictionary is an empirical many-to-many map from parallel lines.

See `CITATIONS.md` and `data/reports/coverage.md` after a run.
