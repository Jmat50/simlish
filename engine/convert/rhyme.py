from __future__ import annotations

import json
import random
from pathlib import Path

from engine.config import MODELS_DIR
from engine.lib.textfeat import english_rhyme_key
from engine.convert.soundalike import SoundAlike


class RhymeModel:
    def __init__(self, path: Path | None = None):
        path = path or (MODELS_DIR / "rhyme_classes.json")
        self.map = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.sa = SoundAlike()

    def ending_for(self, en_word: str) -> str:
        key = english_rhyme_key(en_word)
        opts = self.map.get(key) or []
        if opts:
            # weighted by n
            bag = []
            for o in opts:
                bag.extend([o["simlish"]] * max(1, int(o.get("n") or 1)))
            return random.choice(bag)
        # fallback: soundalike of the end word
        return self.sa.transform(en_word)
