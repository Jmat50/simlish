# Citations

This project’s convert models are **induced** from official Sims soundtrack EN|SIMLISH lyric tables and research audio alignments. Raw multi-megabyte lexicons and audio dumps are not redistributed in this repository by default.

## Primary lyric / catalog source

- [Songs in Simlish](https://sims.fandom.com/wiki/Songs_in_Simlish) — official soundtrack EN|SIMLISH wiki tables (Maxis / EA soundtrack listings as published on the Sims Wiki). Used as the orthography source for induction targets only; full lyric sheets are not redistributed here.

## Process notes (algorithm design, not orthography)

Maxis voice / audio leads describe Simlish song writing as theme-first seeding plus easy-to-sing fillers that preserve rhyme, alliteration, and meter — not 1:1 glosses. Closed-class fill/elide in this converter follows that design; spellings still come only from wiki lyric tables.

- [Reimagining Sims Sessions](https://www.ea.com/games/the-sims/the-sims-4/news/reimagining-sims-sessions) — Jackie Perez Gratz & Robi Kauker on Simlish lyric process and cheatsheets (unpublished; not used as spellings).
- [How The Sims Translates Pop Songs Into Simlish](https://kotaku.com/how-the-sims-translates-pop-songs-into-simlish-1832998368) — Kauker on abstract/emotional Simlish vs literal translation.

## Related tooling

- Naming and the general idea of language-sounding nonsense generation were inspired by exploration of [TEParsons/simlish](https://github.com/TEParsons/simlish). This site does **not** depend on that Python package at runtime.
- [Kokoro](https://github.com/hexgrad/kokoro) / [kokoro-js](https://www.npmjs.com/package/kokoro-js) — stock in-browser TTS for Speak (not an official Sims voice). Runtime weights: [onnx-community/Kokoro-82M-v1.0-ONNX](https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX) via Hugging Face Hub CDN (default); do not vendor into Pages.
- CMU-style pronunciation helpers via [`pronouncing`](https://github.com/aparrish/pronouncingpy) when building `docs/models/rhyme_keys.json` offline.
