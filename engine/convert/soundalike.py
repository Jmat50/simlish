from __future__ import annotations

import json
import random
from pathlib import Path

from engine.config import MODELS_DIR
from engine.convert.closed_class import CLOSED_CLASS
from engine.lib.textfeat import (
    approx_phones,
    compose_onset_ending,
    phone_similarity,
    simlish_syllable_count,
)


def _weighted_pick(options: list[str] | list[dict], *, key: str = "simlish") -> str:
    if not options:
        return ""
    if isinstance(options[0], str):
        return random.choice(options)  # type: ignore[arg-type]
    bag: list[str] = []
    for o in options:  # type: ignore[assignment]
        s = o.get(key) or o.get("to") or ""  # type: ignore[union-attr]
        if not s:
            continue
        bag.extend([s] * max(1, int(o.get("n") or 1)))  # type: ignore[union-attr]
    return random.choice(bag) if bag else ""


def _expand_weighted(entries: list[dict], field: str) -> list[str]:
    bag: list[str] = []
    for e in entries:
        s = e.get(field) or ""
        if not s or "X" in s.split("+"):
            continue
        bag.extend([s] * max(1, int(e.get("n") or 1)))
    return bag


class SoundAlike:
    def __init__(self, path: Path | None = None):
        path = path or (MODELS_DIR / "soundalike_rules.json")
        raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.lexicon = {
            k: [x["simlish"] for x in v] for k, v in (raw.get("lexicon") or {}).items()
        }
        self.phone_map = {
            k: _expand_weighted(v, "to")
            for k, v in (raw.get("phone_map") or {}).items()
        }
        fw = MODELS_DIR / "function_words.json"
        self.function: dict[str, list[str]] = {}
        if fw.exists():
            self.function = {
                k: _expand_weighted(v, "simlish")
                for k, v in json.loads(fw.read_text(encoding="utf-8")).items()
            }
        sf = MODELS_DIR / "short_fillers.json"
        self.short_fillers: list[dict] = []
        if sf.exists():
            self.short_fillers = json.loads(sf.read_text(encoding="utf-8")) or []
        # Ending bag for onset+rhyme composition (from lexicon values)
        ends: list[str] = []
        for opts in self.lexicon.values():
            ends.extend(opts[:2])
        self._ending_bag = ends or ["na", "la", "oh", "wa", "zor"]

    def transform(
        self,
        word: str,
        target_syll: int | None = None,
        *,
        prefer_elide: bool = False,
    ) -> str:
        w = word.lower()
        if w in self.function and self.function[w]:
            return random.choice(self.function[w])
        if w in self.lexicon and self.lexicon[w]:
            choice = random.choice(self.lexicon[w][:3])
            if target_syll is None or abs(simlish_syllable_count(choice) - target_syll) <= 1:
                return choice

        if w in CLOSED_CLASS:
            if prefer_elide:
                return ""
            fill = _weighted_pick(self.short_fillers)
            return fill or "na"

        return self._generate_content(w, target_syll)

    def _generate_content(self, w: str, target_syll: int | None) -> str:
        """Onset + rhyme/coda composition, with cleaned phone-map fallback."""
        phones = approx_phones(w)
        # Prefer composing English onset with an attested Simlish ending
        if self._ending_bag:
            ending = random.choice(self._ending_bag)
            spelling = compose_onset_ending(w, ending)
            if target_syll is not None:
                # Pick among a few endings to hit budget instead of chopping letters
                candidates = [
                    compose_onset_ending(w, e) for e in random.sample(
                        self._ending_bag, min(8, len(self._ending_bag))
                    )
                ]
                spelling = min(
                    candidates,
                    key=lambda s: abs(simlish_syllable_count(s) - target_syll),
                )
            if spelling and phone_similarity(phones, approx_phones(spelling)) >= 0.15:
                return spelling

        # Phone-map path (no X targets; weighted bags expanded at load)
        out: list[str] = []
        i = 0
        while i < len(phones):
            if i + 1 < len(phones):
                big = phones[i] + "+" + phones[i + 1]
                if big in self.phone_map and self.phone_map[big]:
                    part = random.choice(self.phone_map[big]).split("+")
                    part = [p for p in part if p and p != "X"]
                    out.extend(part)
                    i += 2
                    continue
            if phones[i] in self.phone_map and self.phone_map[phones[i]]:
                p = random.choice(self.phone_map[phones[i]])
                if p and p != "X":
                    out.append(p)
            else:
                p = phones[i]
                if p in "AEIOU":
                    out.append(random.choice(list("AEIOU")))
                elif p != "X":
                    out.append(p)
            i += 1
        spelling = phones_to_spelling(out)
        if target_syll:
            # Prefer alternate phone remaps / endings over letter-chop or ba-pad
            candidates = [spelling]
            for _ in range(6):
                if self._ending_bag:
                    candidates.append(compose_onset_ending(w, random.choice(self._ending_bag)))
            spelling = min(
                candidates,
                key=lambda s: abs(simlish_syllable_count(s or w) - target_syll),
            )
        if phone_similarity(phones, approx_phones(spelling)) < 0.25 and w[:1]:
            spelling = compose_onset_ending(w, spelling or random.choice(self._ending_bag))
        return spelling or compose_onset_ending(w, "na")


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
        if not p or p == "X":
            continue
        out.append(special.get(p, p.lower() if len(p) == 1 else p.lower()))
    return "".join(out)
