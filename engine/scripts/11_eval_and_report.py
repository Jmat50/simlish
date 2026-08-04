from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.config import ANALYSIS_REPORTS, LYRICS_DIR, MODELS_DIR, ensure_dirs
from engine.convert.meter import MeterModel
from engine.convert.rhyme import RhymeModel
from engine.convert.soundalike import SoundAlike
from engine.lib.textfeat import (
    approx_phones,
    line_syllables,
    phone_edit_distance,
    tokenize,
)


class FastEvalConverter:
    """Converter without TF-IDF phrase memory (avoids slow sklearn path in batch eval)."""

    def __init__(self):
        self.sa = SoundAlike()
        self.rhyme = RhymeModel()
        self.meter = MeterModel()
        self._func = {
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

    def convert_line(self, line: str) -> str:
        tokens = tokenize(line)
        if not tokens:
            return line
        target = self.meter.target_line_syllables(line)
        budgets = self.meter.allocate(tokens, target)
        content_idx = [i for i, t in enumerate(tokens) if t not in self._func]
        rhyme_i = content_idx[-1] if content_idx else len(tokens) - 1
        out = []
        for i, tok in enumerate(tokens):
            if i == rhyme_i:
                out.append(self.rhyme.ending_for(tok))
            else:
                out.append(self.sa.transform(tok, budgets[i] if i < len(budgets) else None))
        return " ".join(out)


def eval_song(holdout: str, conv: FastEvalConverter) -> dict:
    fp = LYRICS_DIR / f"{holdout}.json"
    if not fp.exists():
        return {"song_id": holdout, "n": 0}
    doc = json.loads(fp.read_text(encoding="utf-8"))
    phone_dists = []
    rhyme_hits = 0
    rhyme_n = 0
    syl_err = []
    rows = []
    for pair in doc.get("pairs") or []:
        en, gold = pair["original"], pair["simlish"]
        pred = conv.convert_line(en)
        gp = approx_phones("".join(tokenize(gold)))
        pp = approx_phones("".join(tokenize(pred)))
        phone_dists.append(phone_edit_distance(gp, pp) / max(1, max(len(gp), len(pp))))
        gt, pt = tokenize(gold), tokenize(pred)
        if gt and pt:
            rhyme_n += 1
            if pt[-1][-2:] == gt[-1][-2:] or pt[-1] == gt[-1]:
                rhyme_hits += 1
        syl_err.append(abs(line_syllables(pred, True) - line_syllables(gold, True)))
        rows.append({"en": en, "gold": gold, "pred": pred})
    return {
        "song_id": holdout,
        "n": len(rows),
        "mean_norm_phone_edit": sum(phone_dists) / max(1, len(phone_dists)),
        "rhyme_hit_rate": rhyme_hits / max(1, rhyme_n),
        "syllable_mae": sum(syl_err) / max(1, len(syl_err)),
        "samples": rows[:8],
    }


def main() -> None:
    ensure_dirs()
    songs = sorted(p.stem for p in LYRICS_DIR.glob("*.json"))
    conv = FastEvalConverter()
    results = []
    for s in songs:
        print(f"eval {s} ...", flush=True)
        results.append(eval_song(s, conv))
    overall = {
        "songs": len(results),
        "mean_norm_phone_edit": sum(r["mean_norm_phone_edit"] for r in results) / max(1, len(results)),
        "mean_rhyme_hit_rate": sum(r["rhyme_hit_rate"] for r in results) / max(1, len(results)),
        "mean_syllable_mae": sum(r["syllable_mae"] for r in results) / max(1, len(results)),
        "per_song": results,
    }
    (ANALYSIS_REPORTS / "phase1_eval.json").write_text(
        json.dumps(overall, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = [
        "# Phase 1 evaluation (memory-off generative path)",
        "",
        f"- Songs: **{overall['songs']}**",
        f"- Mean normalized phone edit: **{overall['mean_norm_phone_edit']:.3f}**",
        f"- Mean rhyme hit rate: **{overall['mean_rhyme_hit_rate']:.3f}**",
        f"- Mean syllable MAE: **{overall['mean_syllable_mae']:.3f}**",
        "",
        "## Per song",
        "",
    ]
    for r in results:
        md.append(
            f"### {r['song_id']}\n\n"
            f"- n={r['n']} phone_edit={r['mean_norm_phone_edit']:.3f} "
            f"rhyme={r['rhyme_hit_rate']:.3f} syl_mae={r['syllable_mae']:.3f}\n"
        )
        for s in r.get("samples") or []:
            md.append(f"- EN: {s['en']}\n- GOLD: {s['gold']}\n- PRED: {s['pred']}\n")
    (ANALYSIS_REPORTS / "phase1_eval.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: overall[k] for k in overall if k != "per_song"}, indent=2))
    _ = MODELS_DIR  # silence lint


if __name__ == "__main__":
    main()
