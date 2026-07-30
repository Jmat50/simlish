from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

STAGES = [
    "pipeline/01_fetch_wiki.py",
    "pipeline/02_parse_catalog.py",
    "pipeline/03_parse_official_lyrics.py",
    "pipeline/08_align_lyrics.py",
    "pipeline/09_build_dictionary.py",
    "pipeline/11_strip_english_from_simlish.py",
    "pipeline/12_consensus_prune.py",
    "pipeline/10_validate_report.py",
]


def main() -> None:
    ap = argparse.ArgumentParser(description="Run Simlish dictionary pipeline")
    ap.add_argument("--from", dest="from_stage", type=int, default=1, help="1-based stage index")
    ap.add_argument("--to", dest="to_stage", type=int, default=None)
    args = ap.parse_args()
    start = max(1, args.from_stage) - 1
    end = len(STAGES) if args.to_stage is None else min(len(STAGES), args.to_stage)
    for i in range(start, end):
        script = ROOT / STAGES[i]
        print(f"\n=== Stage {i+1}: {script.name} ===")
        runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
