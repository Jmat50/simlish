from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.config import ANALYSIS_TEXT, LYRICS_DIR, MODELS_DIR, ensure_dirs
from engine.convert.closed_class import ENGLISH_LEAK, FUNCTION_INDUCTION
from engine.lib.textfeat import approx_phones, line_syllables, simlish_syllable_count, tokenize


def _is_leak(tok: str) -> bool:
    t = tok.lower().strip("'")
    return t in ENGLISH_LEAK


def _ok_filler(tok: str) -> bool:
    if _is_leak(tok):
        return False
    t = tok.lower()
    if len(t) < 2 and t not in {"oh"}:
        return False
    return True


def _scrub_fw_options(ctr: Counter, fillers: list[dict]) -> list[dict]:
    non_eng = [{"simlish": s, "n": c} for s, c in ctr.most_common(12) if not _is_leak(s)]
    if non_eng:
        return non_eng[:6]
    if fillers:
        return fillers[:6]
    return [{"simlish": s, "n": c} for s, c in ctr.most_common(6)]


def _phone_map_entry(key: str, ctr: Counter) -> list[dict]:
    """Drop X targets; demote identity bigrams when non-identity alternatives exist."""
    cleaned = Counter()
    for t, c in ctr.items():
        if not t or "X" in t.split("+"):
            continue
        cleaned[t] += c
    if not cleaned:
        return []
    if "+" in key:
        src = key.split("+")
        non_id = Counter({t: c for t, c in cleaned.items() if t.split("+") != src})
        if non_id:
            cleaned = non_id
    return [{"to": t, "n": c} for t, c in cleaned.most_common(6)]


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
        ep = p.get("en_phones") or approx_phones(en)
        sp = p.get("sim_phones") or approx_phones(sim)
        for a, b in zip(ep, sp):
            if not b or b == "X":
                continue
            phone_ng[a][b] += 1
        for i in range(min(len(ep), len(sp)) - 1):
            key = ep[i] + "+" + ep[i + 1]
            tgt = sp[i] + "+" + sp[i + 1]
            if "X" in tgt.split("+"):
                continue
            phone_ng[key][tgt] += 1

    phone_map = {}
    for k, ctr in sorted(phone_ng.items(), key=lambda x: -sum(x[1].values())):
        entry = _phone_map_entry(k, ctr)
        if entry:
            phone_map[k] = entry
        if len(phone_map) >= 400:
            break

    soundalike_rules = {
        "lexicon": {
            w: [{"simlish": s, "n": c} for s, c in ctr.most_common(8)]
            for w, ctr in sorted(lex.items(), key=lambda x: -sum(x[1].values()))
        },
        "phone_map": phone_map,
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

    # Short fillers: attested 1-syllable (+ high-freq 2-syllable) Simlish tokens
    filler_ctr: Counter = Counter()
    for fp in LYRICS_DIR.glob("*.json"):
        doc = json.loads(fp.read_text(encoding="utf-8"))
        for pair in doc.get("pairs") or []:
            for tok in tokenize(pair["simlish"]):
                if not _ok_filler(tok):
                    continue
                syl = simlish_syllable_count(tok)
                if syl <= 1 or syl == 2:
                    filler_ctr[tok] += 1
    short_fillers = [
        {"simlish": s, "n": c}
        for s, c in filler_ctr.most_common()
        if simlish_syllable_count(s) <= 1 and _ok_filler(s)
    ]
    short_fillers += [
        {"simlish": s, "n": c}
        for s, c in filler_ctr.most_common()
        if simlish_syllable_count(s) == 2 and c >= 3 and _ok_filler(s)
    ]
    short_fillers = short_fillers[:80]
    (MODELS_DIR / "short_fillers.json").write_text(
        json.dumps(short_fillers, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Function-word / contextual maps (unified induction set includes was/were/at)
    ctx: dict[str, Counter] = defaultdict(Counter)
    for p in pairs:
        if p["en"] in FUNCTION_INDUCTION:
            ctx[p["en"]][p["sim"]] += 1

    fw_out = {
        w: _scrub_fw_options(ctr, short_fillers)
        for w, ctr in sorted(ctx.items(), key=lambda x: x[0])
    }
    (MODELS_DIR / "function_words.json").write_text(
        json.dumps(fw_out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

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
    (MODELS_DIR / "phrase_memory.json").write_text(
        json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"Induced models in {MODELS_DIR}; lexicon_entries={len(lex)} "
        f"memory={len(memory)} fillers={len(short_fillers)} fw={len(fw_out)} "
        f"phone_map={len(phone_map)}"
    )


if __name__ == "__main__":
    main()
