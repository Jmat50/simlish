"""
Local Speak using the winning research stack:
  Kokoro IPA Simlish → OpenVoice v2 tone-color (Sims ref WAV).

Public GitHub Pages stays on stock browser Kokoro (`docs/js/speak.js`).
This script is for local demos only — never commit outputs or EA refs.

Usage (repo root):
  .\\v3\\tts\\.venv\\Scripts\\python.exe v3/tts/scripts/08_local_speak.py "Hilla, sho!"
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from v3.tts.config import DATA_DIR, ensure_dirs  # noqa: E402


def _load_smoke():
    path = Path(__file__).resolve().parent / "06_smoke_voice_clone.py"
    spec = importlib.util.spec_from_file_location("smoke_voice_clone", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    smoke = _load_smoke()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("text", nargs="?", default="Hilla, sho!")
    ap.add_argument("--ref", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=DATA_DIR / "smoke" / "local_speak_out.wav")
    args = ap.parse_args()
    ensure_dirs()

    refs = sorted((DATA_DIR / "refs").glob("ref_*.wav"))
    ref = args.ref or (refs[0] if refs else None)
    if not ref or not ref.exists():
        print("No Sims ref WAV — run 05_curate_refs.py", file=sys.stderr)
        return 1

    base = args.out.with_name(args.out.stem + "_kokoro_base.wav")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    kk = smoke.generate_kokoro(base, args.text)
    if not kk.get("ok"):
        print("kokoro failed:", kk, file=sys.stderr)
        return 2
    ov = smoke.try_openvoice(base, ref, args.out)
    if not ov.get("ok"):
        print("openvoice failed:", ov, file=sys.stderr)
        print("base only at", base)
        return 3
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
