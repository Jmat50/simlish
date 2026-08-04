"""
Orchestrate base-game Phase-1 extract → decode → filter.

Usage (repo root):
  python v3/tts/scripts/run_phase1_base.py --limit 500
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = Path(__file__).resolve().parent


def run(script: str, extra: list[str]) -> None:
    cmd = [sys.executable, str(SCRIPTS / script), *extra]
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=str(REPO))
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--skip-extract", action="store_true")
    ap.add_argument("--skip-decode", action="store_true")
    ap.add_argument("--skip-filter", action="store_true")
    args = ap.parse_args()

    if not args.skip_extract:
        run("01_extract_snr.py", ["--limit", str(args.limit), "--offset", str(args.offset)])
    if not args.skip_decode:
        run("02_decode_wav.py", ["--limit", str(args.limit)])
    if not args.skip_filter:
        run("03_filter_speech.py", [])
    print("phase1 base extract/decode/filter complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
