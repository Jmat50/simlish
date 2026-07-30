# Citations

This project’s phonotactic weight tables are **derived** (transition counts /
probabilities) from IPA pronunciation wordlists. Raw multi-megabyte lexicons
are not redistributed in this repository by default.

## Primary data source

- [open-dict-data/ipa-dict](https://github.com/open-dict-data/ipa-dict) — monolingual wordlists with IPA pronunciations. Released under the **MIT license** unless otherwise noted for specific language files (see that project’s Credits section for third-party dataset licenses).

English (US) IPA in ipa-dict is based on a modified [cmudict-ipa](https://github.com/lingz/cmudict-ipa) (MIT). English (UK) IPA is derived from [ipacards](https://github.com/leoboiko/ipacards) (GPL-3.0).

## Related tooling

- Naming and the general idea of language-sounding nonsense generation were inspired by exploration of [TEParsons/simlish](https://github.com/TEParsons/simlish). This site does **not** depend on that Python package at runtime.
- [sql.js](https://github.com/sql-js/sql.js) (MIT) — SQLite compiled to WebAssembly; used read-only in the browser to query `dictionary.sqlite` for Orthodox mode.
