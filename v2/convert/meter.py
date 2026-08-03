from __future__ import annotations

import json
from pathlib import Path

from v2.config import MODELS_DIR
from v2.lib.textfeat import english_syllable_count, line_syllables, tokenize


class MeterModel:
    def __init__(self, path: Path | None = None):
        path = path or (MODELS_DIR / "syllable_templates.json")
        raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"a": 1.0, "b": 0.0}
        self.a = float(raw.get("a") or 1.0)
        self.b = float(raw.get("b") or 0.0)

    def target_line_syllables(self, en_line: str) -> int:
        en = line_syllables(en_line, False)
        return max(1, int(round(self.a * en + self.b)))

    def allocate(self, en_tokens: list[str], target: int) -> list[int]:
        if not en_tokens:
            return []
        weights = [max(1, english_syllable_count(t)) for t in en_tokens]
        s = sum(weights)
        raw = [max(1, int(round(target * w / s))) for w in weights]
        # fix sum
        while sum(raw) > target and any(x > 1 for x in raw):
            for i in range(len(raw)):
                if raw[i] > 1 and sum(raw) > target:
                    raw[i] -= 1
        while sum(raw) < target:
            raw[sum(raw) % len(raw)] += 1
        return raw
