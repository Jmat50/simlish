from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from v2.config import ANALYSIS_REPORTS, AUDIO_META, AUDIO_PHASE2, CATALOG_DIR, ensure_dirs


def main() -> None:
    ensure_dirs()
    # Ensure catalog
    if not (CATALOG_DIR / "songs.json").exists():
        runpy.run_path(str(ROOT / "v2/scripts/01_fetch_official_catalog.py"), run_name="__main__")

    print("\n=== Phase2 resolve YouTube ===")
    sys.argv = [str(ROOT / "v2/scripts/03_resolve_youtube_official.py"), "phase2"]
    runpy.run_path(str(ROOT / "v2/scripts/03_resolve_youtube_official.py"), run_name="__main__")

    print("\n=== Phase2 download audio ===")
    sys.argv = [str(ROOT / "v2/scripts/04_download_audio.py"), "phase2"]
    runpy.run_path(str(ROOT / "v2/scripts/04_download_audio.py"), run_name="__main__")

    songs = json.loads((CATALOG_DIR / "songs.json").read_text(encoding="utf-8"))
    ok = fail = no_yt = 0
    rows = []
    for s in songs:
        sid = s["song_id"]
        meta_p = AUDIO_META / f"{sid}.youtube.json"
        status = "no_meta"
        if meta_p.exists():
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            if not meta.get("ok"):
                status = meta.get("skip_reason") or "no_simlish_youtube"
                no_yt += 1
            else:
                audio = list(AUDIO_PHASE2.glob(f"{sid}.*"))
                audio = [a for a in audio if a.suffix.lower() in {".wav", ".mp3", ".m4a", ".webm"}]
                if audio:
                    status = "downloaded"
                    ok += 1
                else:
                    status = "download_failed"
                    fail += 1
        rows.append({"song_id": sid, "status": status})

    report = {
        "catalog": len(songs),
        "downloaded": ok,
        "download_failed": fail,
        "no_simlish_youtube": no_yt,
        "rows": rows,
    }
    (ANALYSIS_REPORTS / "phase2_coverage.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = [
        "# Phase 2 coverage",
        "",
        f"- Catalog songs: **{len(songs)}**",
        f"- Downloaded: **{ok}**",
        f"- Download failed: **{fail}**",
        f"- No Simlish YouTube: **{no_yt}**",
        "",
        "Audio-only tracks refine meter priors later; orthography still comes from official parallel tables only.",
        "",
    ]
    (ANALYSIS_REPORTS / "phase2_coverage.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
