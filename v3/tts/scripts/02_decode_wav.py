"""Decode extracted .snr files to 24 kHz mono WAV."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from v3.tts.config import MANIFEST_DIR, SNR_DIR, WAV_DIR, ensure_dirs  # noqa: E402
from v3.tts.lib.decode_audio import DecodeError, codec_of, decode_snr_to_wav  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="Max files (0 = all)")
    ap.add_argument("--skip-existing", action="store_true", default=True)
    args = ap.parse_args()
    ensure_dirs()

    files = sorted(SNR_DIR.glob("*.snr"))
    if args.limit:
        files = files[: args.limit]

    ok = fail = skip = 0
    errors: list[dict] = []
    for i, snr in enumerate(files):
        wav = WAV_DIR / (snr.stem + ".wav")
        if args.skip_existing and wav.exists() and wav.stat().st_size > 44:
            skip += 1
            continue
        try:
            payload = snr.read_bytes()
            decode_snr_to_wav(payload, wav)
            ok += 1
        except DecodeError as exc:
            fail += 1
            errors.append({"file": snr.name, "error": str(exc), "codec": codec_of(snr.read_bytes()) if snr.stat().st_size else None})
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(files)} ok={ok} fail={fail} skip={skip}")

    report = {"ok": ok, "fail": fail, "skip": skip, "errors": errors[:50], "error_count": len(errors)}
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    path = MANIFEST_DIR / "decode_wav.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"done ok={ok} fail={fail} skip={skip} -> {WAV_DIR}")
    print(f"report {path}")
    return 0 if fail < max(1, ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
