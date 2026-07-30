from __future__ import annotations

from pathlib import Path

from pipeline.config import DATA

WORDLIST = DATA / "cache" / "english_words_50k.txt"

# Lyric vocables / fillers — stripped from Simlish columns (not kept)
VOCABLES = {
    "na",
    "oh",
    "ah",
    "ooh",
    "la",
    "da",
    "ba",
    "boo",
    "woo",
    "hey",
    "yo",
    "mm",
    "uh",
    "hmm",
    "hm",
    "aha",
    "ooh",
    "ooo",
    "oooh",
    "nah",
    "neh",
    "lalala",
    "nanana",
}

_ENGLISH: set[str] | None = None


def load_english() -> set[str]:
    global _ENGLISH
    if _ENGLISH is not None:
        return _ENGLISH
    words: set[str] = set()
    if WORDLIST.exists():
        for line in WORDLIST.read_text(encoding="utf-8").splitlines():
            w = line.strip().casefold()
            if w and w.isalpha():
                words.add(w)
    for ch in "abcdefghijklmnopqrstuvwxyz":
        words.add(ch)
    words.update(
        {
            "you're",
            "i'm",
            "it's",
            "don't",
            "can't",
            "won't",
            "didn't",
            "isn't",
            "aren't",
            "wasn't",
            "weren't",
            "haven't",
            "hasn't",
            "hadn't",
            "wouldn't",
            "couldn't",
            "shouldn't",
            "c'mon",
            "gonna",
            "wanna",
            "gotta",
            "yeah",
            "y'all",
        }
    )
    _ENGLISH = words
    return _ENGLISH


def is_english_token(token: str, english: set[str] | None = None) -> bool:
    """True if token should be removed from Simlish columns (English or vocable)."""
    english = english or load_english()
    if not token:
        return True
    t = token.casefold().replace("’", "'").strip()
    if t in VOCABLES:
        return True
    # repeated vocable patterns: na-na, la la, hey!
    compact = t.replace("-", "").replace(" ", "")
    if compact in VOCABLES:
        return True
    if len(set(compact)) <= 2 and compact and all(ch in "naohleyudbmw" for ch in compact) and len(compact) >= 2:
        # e.g. nana, lala, ooooh — soft vocable heuristic
        if compact.startswith(("na", "la", "oh", "ah", "hey", "ooo", "mmm")):
            return True
    if t in english:
        return True
    if "-" in t or "+" in t:
        parts = [p for p in t.replace("+", "-").split("-") if p]
        if parts and any(p in english or p in VOCABLES for p in parts) and all(
            p in english or p in VOCABLES for p in parts
        ):
            return True
    return False
