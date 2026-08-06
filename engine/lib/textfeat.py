from __future__ import annotations

import re
from functools import lru_cache

import pronouncing

VOWELS = set("aeiouy")


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z']+", text.lower())


def simlish_syllable_count(word: str) -> int:
    w = word.lower()
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    n = max(1, len(groups))
    if w.endswith("e") and n > 1 and not w.endswith(("le", "ye")):
        n -= 1
    return max(1, n)


@lru_cache(maxsize=50000)
def english_syllable_count(word: str) -> int:
    w = word.lower().strip("'")
    phones = pronouncing.phones_for_word(w)
    if phones:
        return pronouncing.syllable_count(phones[0])
    return simlish_syllable_count(w)


@lru_cache(maxsize=50000)
def english_rhyme_key(word: str) -> str:
    w = word.lower().strip("'")
    phones = pronouncing.phones_for_word(w)
    if phones:
        parts = phones[0].split()
        # from last stressed vowel
        for i in range(len(parts) - 1, -1, -1):
            if re.search(r"\d", parts[i]):
                return " ".join(parts[i:])
        return parts[-1] if parts else w[-2:]
    return w[-3:] if len(w) >= 3 else w


def line_syllables(text: str, simlish: bool = False) -> int:
    toks = tokenize(text)
    if simlish:
        return sum(simlish_syllable_count(t) for t in toks)
    return sum(english_syllable_count(t) for t in toks)


# Approximate Latin spelling → coarse phone classes for Simlish orthography
_SIMP = [
    (r"ch", "CH"),
    (r"sh", "SH"),
    (r"th", "TH"),
    (r"ph", "F"),
    (r"qu", "KW"),
    (r"ng", "NG"),
    (r"ck", "K"),
    (r"oo", "U"),
    (r"ee", "I"),
    (r"ou", "AW"),
    (r"ai", "AY"),
    (r"ay", "AY"),
    (r"oi", "OY"),
    (r"oy", "OY"),
]


def approx_phones(word: str) -> list[str]:
    w = word.lower()
    phones: list[str] = []
    i = 0
    while i < len(w):
        matched = False
        for pat, sym in _SIMP:
            if w.startswith(pat, i):
                phones.append(sym)
                i += len(pat)
                matched = True
                break
        if matched:
            continue
        ch = w[i]
        i += 1
        if ch in "'-":
            continue
        if ch in VOWELS:
            phones.append({"a": "A", "e": "E", "i": "I", "o": "O", "u": "U", "y": "I"}[ch])
        elif ch.isalpha():
            phones.append(ch.upper())
    return phones or ["X"]


def phone_edit_distance(a: list[str], b: list[str]) -> int:
    n, m = len(a), len(b)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev, dp = dp, [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[j] = min(prev[j] + 1, dp[j - 1] + 1, prev[j - 1] + cost)
    return dp[m]


def phone_similarity(a: list[str], b: list[str]) -> float:
    if not a and not b:
        return 1.0
    d = phone_edit_distance(a, b)
    return 1.0 - d / max(len(a), len(b), 1)


def onset_letters(word: str) -> str:
    """Leading consonant cluster (approx); single first letter if vowel-initial."""
    w = word.lower().strip("'")
    if not w:
        return ""
    i = 0
    while i < len(w) and w[i] not in VOWELS and w[i] != "'":
        i += 1
    return w[:i] if i else w[:1]


def compose_onset_ending(en_word: str, ending: str) -> str:
    """Keep English onset letters; graft Simlish rhyme/coda from an attested ending."""
    onset = onset_letters(en_word)
    e = (ending or "").lower().strip("'")
    if not e:
        return onset or en_word.lower()
    if onset and e.startswith(onset):
        return e
    j = 0
    while j < len(e) and e[j] not in VOWELS and e[j] != "'":
        j += 1
    coda = e[j:] if j < len(e) else e
    if not coda:
        return (onset + e) if onset else e
    return (onset + coda) if onset else coda
