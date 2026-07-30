from __future__ import annotations

from .tokenize import normalize_word, tokenize


def line_features(line: str) -> tuple[int, int]:
    toks = tokenize(line)
    return (len(toks), len(line))


def needleman_wunsch_lines(
    a: list[str], b: list[str]
) -> list[tuple[str | None, str | None]]:
    """Align two line lists; returns list of (a_line|None, b_line|None)."""
    n, m = len(a), len(b)
    # score: prefer similar token/char counts
    gap = -2.0

    def match(i: int, j: int) -> float:
        ta, ca = line_features(a[i])
        tb, cb = line_features(b[j])
        return -abs(ta - tb) - 0.05 * abs(ca - cb)

    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    ptr = [[0] * (m + 1) for _ in range(n + 1)]  # 0 diag, 1 up, 2 left
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + gap
        ptr[i][0] = 1
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + gap
        ptr[0][j] = 2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diag = dp[i - 1][j - 1] + match(i - 1, j - 1)
            up = dp[i - 1][j] + gap
            left = dp[i][j - 1] + gap
            best = max(diag, up, left)
            dp[i][j] = best
            if best == diag:
                ptr[i][j] = 0
            elif best == up:
                ptr[i][j] = 1
            else:
                ptr[i][j] = 2

    i, j = n, m
    out: list[tuple[str | None, str | None]] = []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ptr[i][j] == 0:
            out.append((a[i - 1], b[j - 1]))
            i -= 1
            j -= 1
        elif i > 0 and (j == 0 or ptr[i][j] == 1):
            out.append((a[i - 1], None))
            i -= 1
        else:
            out.append((None, b[j - 1]))
            j -= 1
    out.reverse()
    return out


def align_lines(original_lines: list[str], simlish_lines: list[str]) -> tuple[list[tuple[str, str]], str]:
    if len(original_lines) == len(simlish_lines):
        return list(zip(original_lines, simlish_lines)), "wiki_cell_parallel"
    if not original_lines or not simlish_lines:
        return [], "empty"
    paired = needleman_wunsch_lines(original_lines, simlish_lines)
    result = [(o, s) for o, s in paired if o is not None and s is not None]
    return result, "dtw"


def align_words(
    original_line: str, simlish_line: str
) -> list[tuple[str, list[str]]]:
    """
    Return list of (original_token, [simlish_tokens...]).
    1:1 when lengths match; else proportional mapping of Simlish onto English.
    """
    e = tokenize(original_line)
    s = tokenize(simlish_line)
    if not e or not s:
        return []
    if len(e) == len(s):
        return [(ew, [sw]) for ew, sw in zip(e, s)]

    # Map each simlish token to an english index
    buckets: list[list[str]] = [[] for _ in e]
    for i, sw in enumerate(s):
        j = min(len(e) - 1, int(i * len(e) / len(s)))
        buckets[j].append(sw)
    # Ensure every english token gets at least something if possible
    out: list[tuple[str, list[str]]] = []
    for ew, bucket in zip(e, buckets):
        if bucket:
            out.append((ew, bucket))
        else:
            # borrow from nearest non-empty
            out.append((ew, ["?"]))
    # Replace ? placeholders by duplicating neighbor when needed
    for idx, (ew, bucket) in enumerate(out):
        if bucket == ["?"]:
            for k in range(1, len(out)):
                for neighbor in (idx - k, idx + k):
                    if 0 <= neighbor < len(out) and out[neighbor][1] and out[neighbor][1] != ["?"]:
                        out[idx] = (ew, [out[neighbor][1][0]])
                        break
                if out[idx][1] != ["?"]:
                    break
    return [(ew, b) for ew, b in out if b and b != ["?"]]


def alignments_from_line_pair(
    original_line: str, simlish_line: str
) -> list[dict]:
    rows = []
    for ew, sws in align_words(original_line, simlish_line):
        for sw in sws:
            rows.append(
                {
                    "original_word": ew,
                    "original_norm": normalize_word(ew),
                    "simlish_word": sw,
                    "simlish_norm": normalize_word(sw),
                }
            )
    return rows
