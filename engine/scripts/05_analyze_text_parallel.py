from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.config import (
    ANALYSIS_REPORTS,
    ANALYSIS_TEXT,
    LYRICS_DIR,
    SOUNDALIKE_ALIGN_THRESHOLD,
    ensure_dirs,
)
from engine.lib.align_words import soft_align_words
from engine.lib.textfeat import (
    english_rhyme_key,
    english_syllable_count,
    line_syllables,
    tokenize,
)


def main() -> None:
    ensure_dirs()
    line_path = ANALYSIS_TEXT / "line_features.jsonl"
    soundalike: list[dict] = []
    rhyme_map: dict[str, Counter] = defaultdict(Counter)
    phrase_templates = []
    ratios = []

    with line_path.open("w", encoding="utf-8") as out:
        for fp in sorted(LYRICS_DIR.glob("*.json")):
            doc = json.loads(fp.read_text(encoding="utf-8"))
            sid = doc["song_id"]
            for pair in doc.get("pairs") or []:
                en = pair["original"]
                sim = pair["simlish"]
                en_toks = tokenize(en)
                sim_toks = tokenize(sim)
                en_syl = line_syllables(en, simlish=False)
                sim_syl = line_syllables(sim, simlish=True)
                en_end = en_toks[-1] if en_toks else ""
                sim_end = sim_toks[-1] if sim_toks else ""
                rkey = english_rhyme_key(en_end) if en_end else ""
                if rkey and sim_end:
                    rhyme_map[rkey][sim_end] += 1
                ratio = (sim_syl / en_syl) if en_syl else 1.0
                ratios.append(ratio)
                feat = {
                    "song_id": sid,
                    "line_index": pair.get("line_index"),
                    "original": en,
                    "simlish": sim,
                    "en_tokens": en_toks,
                    "sim_tokens": sim_toks,
                    "en_syllables": en_syl,
                    "sim_syllables": sim_syl,
                    "syllable_ratio": round(ratio, 3),
                    "en_end": en_end,
                    "sim_end": sim_end,
                    "rhyme_key": rkey,
                    "comma_en": en.count(","),
                    "comma_sim": sim.count(","),
                }
                out.write(json.dumps(feat, ensure_ascii=False) + "\n")
                aligns = soft_align_words(en, sim, SOUNDALIKE_ALIGN_THRESHOLD)
                for a in aligns:
                    a["song_id"] = sid
                    a["line_index"] = pair.get("line_index")
                    soundalike.append(a)
                phrase_templates.append(
                    {
                        "song_id": sid,
                        "en_n": len(en_toks),
                        "sim_n": len(sim_toks),
                        "token_ratio": round(len(sim_toks) / max(1, len(en_toks)), 3),
                        "vocable_retained": bool(
                            set(en_toks) & {"la", "oh", "na", "yeah", "ooh"}
                            and set(sim_toks) & {"la", "oh", "na", "yeah", "ooh", "vous"}
                        ),
                    }
                )

    (ANALYSIS_TEXT / "soundalike_pairs.json").write_text(
        json.dumps(soundalike, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    rhyme_out = {
        k: [{"simlish": w, "n": c} for w, c in ctr.most_common(12)]
        for k, ctr in sorted(rhyme_map.items(), key=lambda x: -sum(x[1].values()))
    }
    (ANALYSIS_TEXT / "rhyme_map.json").write_text(
        json.dumps(rhyme_out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ANALYSIS_TEXT / "phrase_templates.json").write_text(
        json.dumps(
            {
                "templates": phrase_templates,
                "mean_token_ratio": round(
                    sum(t["token_ratio"] for t in phrase_templates)
                    / max(1, len(phrase_templates)),
                    3,
                ),
                "mean_syllable_ratio": round(sum(ratios) / max(1, len(ratios)), 3),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Aggregate top soundalikes
    pair_ctr: Counter = Counter()
    for a in soundalike:
        pair_ctr[(a["en"], a["sim"])] += 1
    top_pairs = [{"en": a, "sim": b, "n": n} for (a, b), n in pair_ctr.most_common(40)]

    md = [
        "# Text findings (parallel corpus)",
        "",
        f"- Lines analyzed from `{LYRICS_DIR}`",
        f"- Sound-alike soft alignments kept: **{len(soundalike)}**",
        f"- Mean Simlish/English syllable ratio: **{sum(ratios)/max(1,len(ratios)):.3f}**",
        f"- Mean token ratio: **{sum(t['token_ratio'] for t in phrase_templates)/max(1,len(phrase_templates)):.3f}**",
        f"- Rhyme keys with observations: **{len(rhyme_map)}**",
        "",
        "## How Simlish appears to work (from text)",
        "",
        "1. **Line/phrase mapping** dominates: token counts often diverge; commas and breaks are frequently mirrored.",
        "2. **Sound-alike** content words preserve onset and/or rhyme-ish endings (`think`/`zonk`, `coaster`/`nowster`).",
        "3. **Rhyme** at line ends is a first-class target — English end rhyme class maps to a small set of Simlish endings.",
        "4. **Vocables** (`la`, `oh`, …) are often retained when present in English.",
        "5. Function words are unstable (`you`↔`vous`/`laka`) and should be filled for rhythm, not glossed.",
        "",
        "## Top sound-alike pairs",
        "",
    ]
    for p in top_pairs[:25]:
        md.append(f"- `{p['en']}` → `{p['sim']}` (n={p['n']})")
    md += ["", "## Sample rhyme classes", ""]
    for i, (k, vals) in enumerate(list(rhyme_out.items())[:15]):
        sims = ", ".join(f"{v['simlish']}×{v['n']}" for v in vals[:5])
        md.append(f"- `{k}` → {sims}")

    (ANALYSIS_REPORTS / "text_findings.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote text analysis; alignments={len(soundalike)}")


if __name__ == "__main__":
    main()
