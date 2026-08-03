from __future__ import annotations

from typing import Callable

import numpy as np

from v2.lib.textfeat import approx_phones, phone_similarity, tokenize


def soft_align_words(
    en_line: str,
    sim_line: str,
    threshold: float = 0.45,
) -> list[dict]:
    """Needleman–Wunsch on approximate phones; allow merges via gap penalties."""
    en = tokenize(en_line)
    sim = tokenize(sim_line)
    if not en or not sim:
        return []
    en_p = [approx_phones(w) for w in en]
    sim_p = [approx_phones(w) for w in sim]
    n, m = len(en), len(sim)
    gap = -0.35
    score = np.full((n + 1, m + 1), -1e9)
    back = np.zeros((n + 1, m + 1), dtype=np.int8)  # 1=diag, 2=up, 3=left
    score[0, 0] = 0
    for i in range(1, n + 1):
        score[i, 0] = score[i - 1, 0] + gap
        back[i, 0] = 2
    for j in range(1, m + 1):
        score[0, j] = score[0, j - 1] + gap
        back[0, j] = 3
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sim_sc = phone_similarity(en_p[i - 1], sim_p[j - 1])
            # bonus for shared onset/coda
            if en_p[i - 1][0] == sim_p[j - 1][0]:
                sim_sc += 0.08
            if en_p[i - 1][-1] == sim_p[j - 1][-1]:
                sim_sc += 0.08
            diag = score[i - 1, j - 1] + (sim_sc * 2 - 1)
            up = score[i - 1, j] + gap
            left = score[i, j - 1] + gap
            best = max(diag, up, left)
            score[i, j] = best
            if best == diag:
                back[i, j] = 1
            elif best == up:
                back[i, j] = 2
            else:
                back[i, j] = 3
    pairs = []
    i, j = n, m
    while i > 0 or j > 0:
        b = back[i, j]
        if b == 1 and i > 0 and j > 0:
            sc = phone_similarity(en_p[i - 1], sim_p[j - 1])
            if sc >= threshold:
                pairs.append(
                    {
                        "en": en[i - 1],
                        "sim": sim[j - 1],
                        "score": round(float(sc), 3),
                        "en_phones": en_p[i - 1],
                        "sim_phones": sim_p[j - 1],
                    }
                )
            i -= 1
            j -= 1
        elif b == 2 and i > 0:
            i -= 1
        elif j > 0:
            j -= 1
        else:
            break
    pairs.reverse()
    return pairs


def g2p_english(word: str) -> list[str]:
    """Best-effort English phones; falls back to approx if g2p_en unavailable."""
    try:
        from g2p_en import G2p

        if not hasattr(g2p_english, "_g2p"):
            g2p_english._g2p = G2p()  # type: ignore[attr-defined]
        phones = [p for p in g2p_english._g2p(word) if p != " "]  # type: ignore[attr-defined]
        return phones or approx_phones(word)
    except Exception:  # noqa: BLE001
        return approx_phones(word)
