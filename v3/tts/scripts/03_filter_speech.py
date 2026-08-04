"""Filter WAVs by duration for speech-like clips."""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import sys
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from v3.tts.config import (  # noqa: E402
    FILTERED_DIR,
    MANIFEST_DIR,
    MAX_DURATION_S,
    MIN_DURATION_S,
    WAV_DIR,
    ensure_dirs,
)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-s", type=float, default=MIN_DURATION_S)
    ap.add_argument("--max-s", type=float, default=MAX_DURATION_S)
    args = ap.parse_args()
    ensure_dirs()

    kept = dropped = 0
    rows = []
    for wav in sorted(WAV_DIR.glob("*.wav")):
        try:
            dur = wav_duration(wav)
        except (wave.Error, struct.error, EOFError) as exc:
            dropped += 1
            rows.append({"file": wav.name, "keep": False, "reason": str(exc)})
            continue
        keep = args.min_s <= dur <= args.max_s
        if keep:
            dest = FILTERED_DIR / wav.name
            if not dest.exists():
                shutil.copy2(wav, dest)
            kept += 1
        else:
            dropped += 1
        rows.append({"file": wav.name, "keep": keep, "duration_s": round(dur, 3)})

    report = {
        "kept": kept,
        "dropped": dropped,
        "min_s": args.min_s,
        "max_s": args.max_s,
        "rows": rows,
    }
    out = MANIFEST_DIR / "filter_speech.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"kept={kept} dropped={dropped} -> {FILTERED_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
