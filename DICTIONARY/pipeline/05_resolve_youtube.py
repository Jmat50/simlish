from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import DATA, ensure_dirs
from pipeline.lib.db import init_db, insert_lyric_doc, set_skip
from pipeline.lib.sources_youtube import (
    extract_description_lyrics,
    fetch_video_description,
    pick_best_video,
)
from tqdm import tqdm


def has_simlish_doc(conn, song_id: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM lyric_documents WHERE song_id=? AND side='simlish' LIMIT 1",
        (song_id,),
    )
    return cur.fetchone() is not None


def main() -> None:
    ensure_dirs()
    conn = init_db()
    rows = conn.execute(
        """
        SELECT s.song_id, s.artist, s.title FROM songs s
        WHERE s.has_real_world_original=1
          AND EXISTS (
            SELECT 1 FROM lyric_documents d
            WHERE d.song_id=s.song_id AND d.side='original'
          )
          AND NOT EXISTS (
            SELECT 1 FROM lyric_documents d
            WHERE d.song_id=s.song_id AND d.side='simlish'
          )
        ORDER BY s.artist, s.title
        """
    ).fetchall()
    print(f"YouTube resolve candidates: {len(rows)}")

    found = 0
    for row in tqdm(rows, desc="youtube resolve"):
        song_id = row["song_id"]
        meta = pick_best_video(row["artist"], row["title"])
        if not meta or not meta.get("url"):
            set_skip(conn, song_id, "no_youtube")
            continue

        (DATA / "youtube" / f"{song_id}.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        found += 1

        if (meta.get("score") or 0) < 3:
            continue

        try:
            desc = fetch_video_description(meta["url"])
            fan = extract_description_lyrics(desc)
            if fan:
                insert_lyric_doc(
                    conn,
                    {
                        "song_id": song_id,
                        "side": "simlish",
                        "source_kind": "fan_page",
                        "language": "simlish",
                        "text": fan,
                        "source_url": meta["url"],
                        "confidence": 0.7,
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                (DATA / "lyrics" / "simlish" / f"{song_id}.json").write_text(
                    json.dumps(
                        {"text": fan, "source_kind": "fan_page", "url": meta["url"]},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
        except Exception as exc:  # noqa: BLE001
            print(f"desc fail {song_id}: {exc}")

    conn.commit()
    conn.close()
    print(f"YouTube metadata saved for {found} songs")


if __name__ == "__main__":
    main()
