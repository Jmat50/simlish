"""Extract SNR resources from Sims 3 FullBuild packages to data/snr/."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# allow `python v3/tts/scripts/01_extract_snr.py` from repo root
REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from v3.tts.config import (  # noqa: E402
    DEFAULT_EXTRACT_LIMIT,
    DEFAULT_SIMS3_ROOT,
    MANIFEST_DIR,
    SNR_DIR,
    TYPE_SNR,
    ensure_dirs,
)
from v3.tts.lib.dbpf import Package  # noqa: E402


def discover_fullbuild_packages(root: Path) -> list[Path]:
    return sorted(root.rglob("FullBuild*.package"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--sims3-root",
        type=Path,
        default=Path(os.environ.get("SIMS3_ROOT", DEFAULT_SIMS3_ROOT)),
    )
    ap.add_argument(
        "--package",
        type=Path,
        help="Single package path (default: base game FullBuild1)",
    )
    ap.add_argument("--limit", type=int, default=DEFAULT_EXTRACT_LIMIT)
    ap.add_argument("--offset", type=int, default=0, help="Skip first N SNR entries")
    ap.add_argument("--all-packs", action="store_true", help="Scan every FullBuild*.package")
    args = ap.parse_args()

    ensure_dirs()
    packages: list[Path]
    if args.package:
        packages = [args.package]
    elif args.all_packs:
        packages = discover_fullbuild_packages(args.sims3_root)
    else:
        packages = [
            args.sims3_root
            / "The Sims 3"
            / "GameData"
            / "Shared"
            / "Packages"
            / "FullBuild1.package"
        ]

    written = 0
    skipped = 0
    codec_hist: dict[str, int] = {}
    rows: list[dict] = []

    for pkg_path in packages:
        if not pkg_path.exists():
            print(f"missing {pkg_path}", file=sys.stderr)
            continue
        print(f"open {pkg_path}")
        pkg = Package(pkg_path)
        pack_tag = pkg_path.stem
        for i, ref in enumerate(pkg.iter_type(TYPE_SNR)):
            if i < args.offset:
                continue
            if written >= args.limit:
                break
            payload = pkg.read_bytes(ref)
            if not payload:
                skipped += 1
                continue
            codec = payload[0]
            codec_hist[str(codec)] = codec_hist.get(str(codec), 0) + 1
            name = f"{pack_tag}__{ref.key}.snr"
            out = SNR_DIR / name
            if not out.exists():
                out.write_bytes(payload)
            rows.append(
                {
                    "file": name,
                    "package": str(pkg_path),
                    "type": f"0x{ref.type_id:08X}",
                    "group": f"0x{ref.group:08X}",
                    "instance": f"0x{ref.instance:016X}",
                    "codec": codec,
                    "bytes": len(payload),
                }
            )
            written += 1
            if written % 500 == 0:
                print(f"  extracted {written}...")
        if written >= args.limit:
            break

    manifest = {
        "written": written,
        "skipped": skipped,
        "codec_hist": codec_hist,
        "limit": args.limit,
        "offset": args.offset,
        "packages": [str(p) for p in packages],
        "rows": rows,
    }
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    out_json = MANIFEST_DIR / "extract_snr.json"
    out_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {written} SNR -> {SNR_DIR}")
    print(f"codec_hist={codec_hist}")
    print(f"manifest {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
