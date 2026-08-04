from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.config import ANALYSIS_TEXT, LYRICS_DIR, MODELS_DIR, ensure_dirs
from engine.lib.textfeat import approx_phones, line_syllables, tokenize


def main() -> None:
    ensure_dirs()
    pairs = json.loads((ANALYSIS_TEXT / "soundalike_pairs.json").read_text(encoding="utf-8"))
    rhyme_map = json.loads((ANALYSIS_TEXT / "rhyme_map.json").read_text(encoding="utf-8"))
    phrase = json.loads((ANALYSIS_TEXT / "phrase_templates.json").read_text(encoding="utf-8"))

    # Sound-alike: en word -> Counter(sim), and phone bigram transforms
    lex: dict[str, Counter] = defaultdict(Counter)
    phone_ng: dict[str, Counter] = defaultdict(Counter)
    for p in pairs:
        en, sim = p["en"], p["sim"]
        lex[en][sim] += 1
        ep, sp = p.get("en_phones") or approx_phones(en), p.get("sim_phones") or approx_phones(sim)
        # unigram + bigram mappings padded
        for a, b in zip(ep, sp):
            phone_ng[a][b] += 1
        for i in range(len(ep) - 1):
            key = ep[i] + "+" + ep[i + 1]
            tgt = (sp[i] if i < len(sp) else "X") + "+" + (sp[i + 1] if i + 1 < len(sp) else "X")
            phone_ng[key][tgt] += 1

    soundalike_rules = {
        "lexicon": {
            w: [{"simlish": s, "n": c} for s, c in ctr.most_common(8)]
            for w, ctr in sorted(lex.items(), key=lambda x: -sum(x[1].values()))
        },
        "phone_map": {
            k: [{"to": t, "n": c} for t, c in ctr.most_common(6)]
            for k, ctr in sorted(phone_ng.items(), key=lambda x: -sum(x[1].values()))[:400]
        },
    }
    (MODELS_DIR / "soundalike_rules.json").write_text(
        json.dumps(soundalike_rules, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (MODELS_DIR / "rhyme_classes.json").write_text(
        json.dumps(rhyme_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Syllable budget linear fit sim = a*en + b
    xs, ys = [], []
    for fp in LYRICS_DIR.glob("*.json"):
        doc = json.loads(fp.read_text(encoding="utf-8"))
        for pair in doc.get("pairs") or []:
            xs.append(line_syllables(pair["original"], False))
            ys.append(line_syllables(pair["simlish"], True))
    n = len(xs) or 1
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs) or 1.0
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    a = cov / var_x
    b = mean_y - a * mean_x
    (MODELS_DIR / "syllable_templates.json").write_text(
        json.dumps(
            {
                "a": a,
                "b": b,
                "mean_ratio": phrase.get("mean_syllable_ratio"),
                "mean_token_ratio": phrase.get("mean_token_ratio"),
                "n_lines": n,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Function-word / contextual maps
    func = {
        "you",
        "i",
        "me",
        "we",
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
        "it",
        "is",
        "are",
        "be",
        "my",
        "your",
        "that",
        "this",
        "with",
        "no",
        "yes",
        "oh",
        "la",
        "na",
    }
    ctx: dict[str, Counter] = defaultdict(Counter)
    for p in pairs:
        if p["en"] in func:
            ctx[p["en"]][p["sim"]] += 1
    # Phrase memory: all line pairs
    memory = []
    for fp in LYRICS_DIR.glob("*.json"):
        doc = json.loads(fp.read_text(encoding="utf-8"))
        for pair in doc.get("pairs") or []:
            memory.append(
                {
                    "song_id": doc["song_id"],
                    "original": pair["original"],
                    "simlish": pair["simlish"],
                }
            )
    (MODELS_DIR / "function_words.json").write_text(
        json.dumps(
            {w: [{"simlish": s, "n": c} for s, c in ctr.most_common(6)] for w, ctr in ctx.items()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (MODELS_DIR / "phrase_memory.json").write_text(
        json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Induced models in {MODELS_DIR}; lexicon_entries={len(lex)} memory={len(memory)}")


if __name__ == "__main__":
    main()
