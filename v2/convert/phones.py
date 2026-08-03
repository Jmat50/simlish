from __future__ import annotations

from v2.lib.align_words import g2p_english
from v2.lib.textfeat import approx_phones


def english_phones(word: str) -> list[str]:
    return g2p_english(word)


def simlish_phones_from_spelling(word: str) -> list[str]:
    return approx_phones(word)
