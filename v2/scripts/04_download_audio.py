from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from v2.config import AUDIO_META, AUDIO_PHASE1, AUDIO_PHASE2, PHASE1_SONG_IDS, CATALOG_DIR, ensure_dirs
from v2.lib.youtube import download_audio


def targets(phase: str) -> list[str]:
    if phase == "phase1":
        return list(PHASE1_SONG_IDS)
    songs = json.loads((CATALOG_DIR / "songs.json").read_text(encoding="utf-8"))
    return [s["song_id"] for s in songs]


def main(phase: str = "phase1") -> None:
    ensure_dirs()
    out_dir = AUDIO_PHASE1 if phase == "phase1" else AUDIO_PHASE2
    ids = targets(phase)
    got = 0
    for sid in ids:
        meta_path = AUDIO_META / f"{sid}.youtube.json"
        if not meta_path.exists():
            print(f"no meta {sid}")
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not meta.get("ok"):
            print(f"skip {sid}: {meta.get('skip_reason')}")
            continue
        url = meta["chosen"]["url"]
        path = download_audio(url, out_dir, sid)
        if path:
            meta["audio_path"] = str(path)
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            got += 1
            print(f"downloaded {sid} -> {path.name}")
        else:
            meta["download_ok"] = False
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"FAIL download {sid}")
    print(f"Audio ready {got}/{len(ids)}")


if __name__ == "__main__":
    ph = sys.argv[1] if len(sys.argv) > 1 else "phase1"
    main(ph)
