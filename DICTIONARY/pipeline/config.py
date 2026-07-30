from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # DICTIONARY/
REPO_ROOT = ROOT.parent
DATA = ROOT / "data"
DB_PATH = ROOT / "dictionary.sqlite"
SCHEMA_PATH = ROOT / "schema.sql"

WIKI_API = "https://sims.fandom.com/api.php"
WIKI_PAGE = "Songs_in_Simlish"
USER_AGENT = "SimlishDictionaryBot/1.0 (+https://github.com/Jmat50/simlish; research)"

CONFIDENCE_MIN = 0.55
SIMLISH_COLS = 10
REQUEST_SLEEP_S = 0.35


# Maxis / Simlish-original titles with no real-world lyric counterpart
MAXIS_ONLY_TITLES = {
    "glabe glarn",
    "thonsivee",
    "frettesche",
    "stambadoo",
    "chebadoo",
    "na na lae",
    "high nrg",
    "melinka",
    "downjazz",
    "glowstick juice",
    "dee bamow",
    "gofuork! gofuork!",
    "indogoth",
    "techno music",
    "pop one",
    "lathouse",
    "zu matan",
    "snatch",
    "tissy wawa",
    "glowstick",
    "wavetrap",
    "ze fron",
    "wiseguy",
    "fortuzala",
    "booglurbia",
    "wubbas doo",
    "topy apa ty",
}

# Artists that are soundtrack composers for Urbz originals (not BEP covers)
URBZ_ORIGINAL_ARTISTS = {
    "john cobbett",
    "rod abernathy",
    "jacen touchstone",
    "music orange",
    "matmos",
    "j greco",
    "chris seifert",
    "jeffery stott",
}


def ensure_dirs() -> None:
    for p in (
        DATA / "catalog",
        DATA / "lyrics" / "official",
        DATA / "lyrics" / "original" / "_overrides",
        DATA / "lyrics" / "simlish",
        DATA / "alignments",
        DATA / "reports",
        DATA / "cache",
    ):
        p.mkdir(parents=True, exist_ok=True)
