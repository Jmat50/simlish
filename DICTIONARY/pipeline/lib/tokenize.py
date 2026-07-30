from __future__ import annotations

import regex as re

TOKEN_RE = re.compile(r"(\p{L}+(?:['’]\p{L}+)?|\p{N}+)", re.UNICODE)


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return TOKEN_RE.findall(text)


def normalize_word(word: str) -> str:
    return word.casefold().replace("’", "'").strip()


def split_lyric_lines(cell: str) -> list[str]:
    """Split wiki cell / lyric blob into non-empty lines."""
    if not cell:
        return []
    text = cell.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</?[^>]+>", "", text)  # strip residual HTML
    lines = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        # drop section markers like [Verse 1]
        if re.fullmatch(r"\[.*?\]", line):
            continue
        lines.append(line)
    return lines
