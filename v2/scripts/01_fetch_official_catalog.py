from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from slugify import slugify

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from v2.config import BOOTSTRAP_CATALOG, CATALOG_DIR, ensure_dirs
from v2.lib.wiki import fetch_wikitext, parse_artist_title, SECTION_RE


MAXIS_HINTS = re.compile(
    r"maxis|original|composed|no real.?world|simlish.?original",
    re.I,
)


def main() -> None:
    ensure_dirs()
    songs = []
    try:
        wt = fetch_wikitext()
        (CATALOG_DIR / "Songs_in_Simlish.wikitext").write_text(wt, encoding="utf-8")
        current_game = ""
        for m in SECTION_RE.finditer(wt):
            # also track == Game == headers
            pass
        # crude: split by === sections for catalog entries
        game = "Unknown"
        for line in wt.splitlines():
            if line.startswith("== ") and not line.startswith("==="):
                game = line.strip("= ").strip()
            if line.startswith("==="):
                head = line.strip("= ").strip()
                artist, title = parse_artist_title(head)
                sid = slugify(f"{artist}__{title}")
                songs.append(
                    {
                        "song_id": sid,
                        "artist": artist,
                        "title": title,
                        "game_section": game,
                        "has_real_world_original": 0 if MAXIS_HINTS.search(head) else 1,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
        print(f"Fetched wiki catalog entries: {len(songs)}")
        if len(songs) < 50 and BOOTSTRAP_CATALOG.exists():
            print("Wiki section parse looks incomplete; merging bootstrap catalog")
            songs = json.loads(BOOTSTRAP_CATALOG.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"Wiki fetch failed ({exc}); bootstrapping from DICTIONARY catalog")
        if BOOTSTRAP_CATALOG.exists():
            songs = json.loads(BOOTSTRAP_CATALOG.read_text(encoding="utf-8"))
        else:
            raise

    (CATALOG_DIR / "songs.json").write_text(
        json.dumps(songs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {CATALOG_DIR / 'songs.json'} n={len(songs)}")


if __name__ == "__main__":
    main()
