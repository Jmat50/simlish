"""Curate Sims VO reference clips + optional FT subset from wav_filtered.

Writes (gitignored under data/):
  data/refs/           — top N short clean refs for zero-shot clone
  data/ft_subset/      — larger subset for optional Kokoro/GPT-SoVITS FT
  data/manifests/curate_refs.json
"""

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

from v3.tts.config import FILTERED_DIR, MANIFEST_DIR, ensure_dirs  # noqa: E402

REFS_DIR = FILTERED_DIR.parent / "refs"
FT_DIR = FILTERED_DIR.parent / "ft_subset"


def score_wav(path: Path) -> dict | None:
    try:
        with wave.open(str(path), "rb") as w:
            fr = w.getframerate()
            n = w.getnframes()
            dur = n / float(fr)
            # sample up to ~1s for RMS
            take = min(n, fr)
            raw = w.readframes(take)
        if len(raw) < 4:
            return None
        samples = struct.unpack("<" + ("h" * (len(raw) // 2)), raw[: len(raw) // 2 * 2])
        if not samples:
            return None
        mean = sum(abs(s) for s in samples) / len(samples)
        # instance-hi from filename for diversity
        parts = path.stem.split("_")
        inst_hi = parts[-2] if len(parts) >= 2 else path.stem
        return {
            "file": path.name,
            "path": str(path),
            "duration_s": round(dur, 3),
            "rms": round(mean, 1),
            "inst_hi": inst_hi,
        }
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-refs", type=int, default=10)
    ap.add_argument("--n-ft", type=int, default=200)
    ap.add_argument("--ref-min", type=float, default=1.5)
    ap.add_argument("--ref-max", type=float, default=5.0)
    ap.add_argument("--ft-min", type=float, default=2.0)
    ap.add_argument("--ft-max", type=float, default=8.0)
    args = ap.parse_args()
    ensure_dirs()
    REFS_DIR.mkdir(parents=True, exist_ok=True)
    FT_DIR.mkdir(parents=True, exist_ok=True)

    scored = []
    for p in sorted(FILTERED_DIR.glob("*.wav")):
        row = score_wav(p)
        if row:
            scored.append(row)
    print(f"scored {len(scored)} clips", flush=True)

    ref_pool = [r for r in scored if args.ref_min <= r["duration_s"] <= args.ref_max]
    ref_pool.sort(key=lambda r: -r["rms"])
    refs: list[dict] = []
    seen_hi: set[str] = set()
    for r in ref_pool:
        if r["inst_hi"] in seen_hi and len(refs) < args.n_refs:
            # allow duplicates only after diversity exhausted
            continue
        if len(refs) >= args.n_refs:
            break
        # prefer unique instance-hi groups first
        if r["inst_hi"] not in seen_hi or len(seen_hi) >= args.n_refs:
            refs.append(r)
            seen_hi.add(r["inst_hi"])
    # fill if diversity left gaps
    if len(refs) < args.n_refs:
        for r in ref_pool:
            if r in refs:
                continue
            refs.append(r)
            if len(refs) >= args.n_refs:
                break

    ft_pool = [r for r in scored if args.ft_min <= r["duration_s"] <= args.ft_max]
    ft_pool.sort(key=lambda r: -r["rms"])
    ft = ft_pool[: args.n_ft]

    for d in (REFS_DIR, FT_DIR):
        for old in d.glob("*.wav"):
            old.unlink()

    for i, r in enumerate(refs):
        dest = REFS_DIR / f"ref_{i:02d}_{r['file']}"
        shutil.copy2(r["path"], dest)
        r["ref_name"] = dest.name

    for i, r in enumerate(ft):
        dest = FT_DIR / f"ft_{i:04d}_{r['file']}"
        shutil.copy2(r["path"], dest)
        r["ft_name"] = dest.name

    report = {
        "n_scored": len(scored),
        "n_refs": len(refs),
        "n_ft": len(ft),
        "refs_dir": str(REFS_DIR),
        "ft_dir": str(FT_DIR),
        "refs": refs,
        "ft_total_duration_s": round(sum(x["duration_s"] for x in ft), 1),
    }
    out = MANIFEST_DIR / "curate_refs.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"refs={len(refs)} -> {REFS_DIR}")
    print(f"ft_subset={len(ft)} ({report['ft_total_duration_s']}s) -> {FT_DIR}")
    print(f"manifest {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
