from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.config import AUDIO_META, CATALOG_DIR, LYRICS_DIR, PHASE1_SONG_IDS, ensure_dirs
from engine.lib.youtube import pick_best


def song_list(phase: str) -> list[dict]:
    if phase == "phase1":
        out = []
        for sid in PHASE1_SONG_IDS:
            fp = LYRICS_DIR / f"{sid}.json"
            if fp.exists():
                d = json.loads(fp.read_text(encoding="utf-8"))
                out.append(d)
            else:
                out.append({"song_id": sid, "artist": sid.split("__")[0], "title": sid})
        return out
    songs = json.loads((CATALOG_DIR / "songs.json").read_text(encoding="utf-8"))
    return songs


def main(phase: str = "phase1") -> None:
    ensure_dirs()
    rows = song_list(phase)
    print(f"Resolving YouTube for {len(rows)} songs ({phase})")
    ok = 0
    for row in rows:
        sid = row["song_id"]
        artist = row.get("artist") or "Unknown"
        title = row.get("title") or sid
        meta_path = AUDIO_META / f"{sid}.youtube.json"
        if meta_path.exists():
            prev = json.loads(meta_path.read_text(encoding="utf-8"))
            if prev.get("ok"):
                ok += 1
                continue
        result = pick_best(artist, title)
        result["song_id"] = sid
        result["artist"] = artist
        result["title"] = title
        result["phase"] = phase
        meta_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if result.get("ok"):
            ok += 1
            title = str(result["chosen"].get("title") or "")
            safe = title.encode("ascii", "replace").decode("ascii")
            print(f"  OK {sid} -> {safe} score={result['chosen'].get('score')}")
        else:
            print(f"  SKIP {sid}: {result.get('skip_reason')}")
    print(f"Resolved ok={ok}/{len(rows)}")


if __name__ == "__main__":
    ph = sys.argv[1] if len(sys.argv) > 1 else "phase1"
    main(ph)
