from __future__ import annotations

import json
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from engine.config import MODELS_DIR, NN_RETRIEVAL_THRESHOLD


class PhraseMemory:
    def __init__(self, path: Path | None = None):
        path = path or (MODELS_DIR / "phrase_memory.json")
        self.rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        self.vectorizer = None
        self.matrix = None
        if self.rows:
            texts = [r["original"].lower() for r in self.rows]
            self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
            self.matrix = self.vectorizer.fit_transform(texts)

    def lookup(self, en_line: str, threshold: float = NN_RETRIEVAL_THRESHOLD) -> str | None:
        if not self.rows or self.vectorizer is None or self.matrix is None:
            return None
        q = self.vectorizer.transform([en_line.lower()])
        sims = cosine_similarity(q, self.matrix)[0]
        idx = int(sims.argmax())
        if float(sims[idx]) >= threshold:
            return self.rows[idx]["simlish"]
        return None


_WORD = re.compile(r"[A-Za-z']+|[^\w\s]+|\s+")


def split_keep(text: str) -> list[str]:
    return _WORD.findall(text)
