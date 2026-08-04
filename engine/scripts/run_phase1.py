from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

STAGES = [
    "engine/scripts/01_fetch_official_catalog.py",
    "engine/scripts/02_fetch_official_parallel_lyrics.py",
    "engine/scripts/03_resolve_youtube_official.py",
    "engine/scripts/04_download_audio.py",
    "engine/scripts/05_analyze_text_parallel.py",
    "engine/scripts/06_align_audio_to_lyrics.py",
    "engine/scripts/07_analyze_audio_prosody.py",
    "engine/scripts/08_induce_rules_and_stats.py",
    "engine/scripts/09_train_phrase_model.py",
    "engine/scripts/10_build_converter.py",
    "engine/scripts/11_eval_and_report.py",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_stage", type=int, default=1)
    ap.add_argument("--to", dest="to_stage", type=int, default=None)
    ap.add_argument("--skip-youtube", action="store_true", help="Skip stages 03-04")
    args = ap.parse_args()
    stages = list(STAGES)
    if args.skip_youtube:
        stages = [s for s in stages if "03_" not in s and "04_" not in s]
    start = max(1, args.from_stage) - 1
    end = len(stages) if args.to_stage is None else min(len(stages), args.to_stage)
    for i in range(start, end):
        script = ROOT / stages[i]
        print(f"\n=== Phase1 {i+1}/{len(stages)}: {script.name} ===")
        # For 03/04 pass phase1 via rewriting argv
        if "03_" in script.name or "04_" in script.name:
            sys.argv = [str(script), "phase1"]
        else:
            sys.argv = [str(script)]
        runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
