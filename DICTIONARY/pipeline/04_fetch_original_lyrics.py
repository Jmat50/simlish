from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import DATA, ensure_dirs
from pipeline.lib.db import init_db, insert_lyric_doc, set_skip
from pipeline.lib.sources_lyrics import fetch_lrclib, load_override
from tqdm import tqdm


def already_has_original(conn, song_id: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM lyric_documents WHERE song_id=? AND side='original' LIMIT 1",
        (song_id,),
    )
    return cur.fetchone() is not None


def fetch_one(item: dict) -> tuple[str, dict | None]:
    song_id = item["song_id"]
    override = DATA / "lyrics" / "original" / "_overrides" / f"{song_id}.txt"
    doc = load_override(override) or fetch_lrclib(item["artist"], item["title"])
    return song_id, doc


def main() -> None:
    ensure_dirs()
    conn = init_db()
    rows = [
        dict(r)
        for r in conn.execute(
            """
            SELECT song_id, artist, title FROM songs
            WHERE has_real_world_original=1
            ORDER BY artist, title
            """
        ).fetchall()
    ]
    todo = [r for r in rows if not already_has_original(conn, r["song_id"])]
    print(f"Need originals for {len(todo)} / {len(rows)} songs")

    ok = len(rows) - len(todo)
    skip = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_one, item): item for item in todo}
        for fut in tqdm(as_completed(futs), total=len(futs), desc="original lyrics"):
            song_id, doc = fut.result()
            if not doc:
                set_skip(conn, song_id, "no_original_lyrics")
                skip += 1
                continue
            insert_lyric_doc(
                conn,
                {
                    "song_id": song_id,
                    "side": "original",
                    **{
                        k: doc[k]
                        for k in (
                            "source_kind",
                            "language",
                            "text",
                            "source_url",
                            "confidence",
                            "retrieved_at",
                        )
                    },
                },
            )
            out = DATA / "lyrics" / "original" / f"{song_id}.json"
            out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
            cur = conn.execute("SELECT skip_reason FROM songs WHERE song_id=?", (song_id,))
            if cur.fetchone()["skip_reason"] == "no_original_lyrics":
                conn.execute("UPDATE songs SET skip_reason=NULL WHERE song_id=?", (song_id,))
            ok += 1
            if ok % 20 == 0:
                conn.commit()

    conn.commit()
    conn.close()
    print(f"Original lyrics available for {ok}; newly skipped {skip}")


if __name__ == "__main__":
    main()
