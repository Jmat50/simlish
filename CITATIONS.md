# Citations

This project’s convert models are **induced** from official Sims soundtrack EN|SIMLISH lyric tables and research audio alignments. Raw multi-megabyte lexicons and audio dumps are not redistributed in this repository by default.

## Primary lyric / catalog source

- [Songs in Simlish](https://sims.fandom.com/wiki/Songs_in_Simlish) — official soundtrack EN|SIMLISH wiki tables (Maxis / EA soundtrack listings as published on the Sims Wiki). Used as the orthography source for induction targets only; full lyric sheets are not redistributed here.

## Related tooling

- Naming and the general idea of language-sounding nonsense generation were inspired by exploration of [TEParsons/simlish](https://github.com/TEParsons/simlish). This site does **not** depend on that Python package at runtime.
- [Kokoro](https://github.com/hexgrad/kokoro) — stock in-browser TTS for Speak (not an official Sims voice).
- CMU-style pronunciation helpers via [`pronouncing`](https://github.com/aparrish/pronouncingpy) when building `docs/models/rhyme_keys.json` offline.
