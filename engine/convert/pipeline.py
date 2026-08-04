from __future__ import annotations

import re

from engine.convert.meter import MeterModel
from engine.convert.phrase import PhraseMemory, split_keep
from engine.convert.rhyme import RhymeModel
from engine.convert.soundalike import SoundAlike
from engine.lib.textfeat import tokenize


_FUNC = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "is",
    "are",
    "be",
    "was",
    "were",
    "it",
    "at",
}


class SimlishConverter:
    def __init__(self):
        self.sa = SoundAlike()
        self.rhyme = RhymeModel()
        self.meter = MeterModel()
        self.memory = PhraseMemory()

    def convert_line(self, line: str) -> str:
        hit = self.memory.lookup(line)
        if hit:
            return _match_casing_line(line, hit)

        tokens = tokenize(line)
        if not tokens:
            return line

        target = self.meter.target_line_syllables(line)
        budgets = self.meter.allocate(tokens, target)
        # last content word gets rhyme treatment
        content_idx = [i for i, t in enumerate(tokens) if t not in _FUNC]
        rhyme_i = content_idx[-1] if content_idx else len(tokens) - 1

        out_words = []
        for i, tok in enumerate(tokens):
            if i == rhyme_i:
                out_words.append(self.rhyme.ending_for(tok))
            else:
                out_words.append(self.sa.transform(tok, budgets[i] if i < len(budgets) else None))

        # reassemble with original punctuation/spacing skeleton
        return _reassemble(line, tokens, out_words)

    def convert_text(self, text: str) -> str:
        if not text:
            return ""
        parts = re.split(r"(\n+)", text)
        out = []
        for part in parts:
            if not part or part.isspace() or set(part) <= {"\n"}:
                out.append(part)
                continue
            # sentence-ish split on .!? while keeping delimiters
            chunks = re.split(r"(?<=[.!?])\s+", part)
            converted = []
            for ch in chunks:
                converted.append(self.convert_line(ch.strip()) if ch.strip() else ch)
            out.append(" ".join(converted))
        return "".join(out)


def _reassemble(original: str, en_tokens: list[str], sim_tokens: list[str]) -> str:
    pieces = split_keep(original)
    ti = 0
    out = []
    for p in pieces:
        if re.fullmatch(r"[A-Za-z']+", p):
            if ti < len(sim_tokens):
                out.append(_match_case(p, sim_tokens[ti]))
                ti += 1
            else:
                out.append(p)
        else:
            out.append(p)
    while ti < len(sim_tokens):
        out.append(" " + sim_tokens[ti])
        ti += 1
    return "".join(out)


def _match_case(src: str, dst: str) -> str:
    if src.isupper():
        return dst.upper()
    if src.istitle():
        return dst[:1].upper() + dst[1:].lower() if dst else dst
    return dst.lower()


def _match_casing_line(src_line: str, dst_line: str) -> str:
    # if source mostly title/upper, light touch
    if src_line.isupper():
        return dst_line.upper()
    return dst_line


def convert_text(text: str) -> str:
    return SimlishConverter().convert_text(text)
