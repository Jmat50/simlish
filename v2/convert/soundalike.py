from __future__ import annotations

import json
import random
from pathlib import Path

from v2.config import MODELS_DIR
from v2.lib.textfeat import approx_phones, phone_similarity, simlish_syllable_count


class SoundAlike:
    def __init__(self, path: Path | None = None):
        path = path or (MODELS_DIR / "soundalike_rules.json")
        raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.lexicon = {
            k: [x["simlish"] for x in v] for k, v in (raw.get("lexicon") or {}).items()
        }
        self.phone_map = {
            k: [x["to"] for x in v] for k, v in (raw.get("phone_map") or {}).items()
        }
        fw = MODELS_DIR / "function_words.json"
        self.function = {}
        if fw.exists():
            self.function = {
                k: [x["simlish"] for x in v]
                for k, v in json.loads(fw.read_text(encoding="utf-8")).items()
            }

    def transform(self, word: str, target_syll: int | None = None) -> str:
        w = word.lower()
        if w in self.function and self.function[w]:
            return random.choice(self.function[w])
        if w in self.lexicon and self.lexicon[w]:
            choice = random.choice(self.lexicon[w][:3])
            if target_syll is None or abs(simlish_syllable_count(choice) - target_syll) <= 1:
                return choice
        # generate from phones
        phones = approx_phones(w)
        out = []
        i = 0
        while i < len(phones):
            if i + 1 < len(phones):
                big = phones[i] + "+" + phones[i + 1]
                if big in self.phone_map and self.phone_map[big]:
                    part = random.choice(self.phone_map[big]).split("+")
                    out.extend(part)
                    i += 2
                    continue
            if phones[i] in self.phone_map and self.phone_map[phones[i]]:
                out.append(random.choice(self.phone_map[phones[i]]))
            else:
                # slight mutation: keep consonant, nudge vowel
                p = phones[i]
                if p in "AEIOU":
                    out.append(random.choice(list("AEIOU")))
                else:
                    out.append(p)
            i += 1
        spelling = phones_to_spelling(out)
        # enforce rough syllable budget (bounded loops — appending vowels alone
        # may not increase syllable count when extending an existing nucleus)
        if target_syll:
            guard = 0
            while simlish_syllable_count(spelling) < target_syll and guard < 12:
                spelling += random.choice(["ba", "di", "ko", "su", "la"])
                guard += 1
            guard = 0
            while (
                simlish_syllable_count(spelling) > target_syll + 1
                and len(spelling) > 2
                and guard < 24
            ):
                spelling = spelling[:-1]
                guard += 1
        # prefer similarity to original
        if phone_similarity(phones, approx_phones(spelling)) < 0.25 and w[:1]:
            spelling = w[0] + spelling[1:] if spelling else w
        return spelling or w


def phones_to_spelling(phones: list[str]) -> str:
    special = {
        "CH": "ch",
        "SH": "sh",
        "TH": "th",
        "NG": "ng",
        "KW": "qu",
        "AY": "ai",
        "OY": "oi",
        "AW": "aw",
        "A": "a",
        "E": "e",
        "I": "i",
        "O": "o",
        "U": "u",
    }
    out = []
    for p in phones:
        out.append(special.get(p, p.lower() if len(p) == 1 else p.lower()))
    return "".join(out)
