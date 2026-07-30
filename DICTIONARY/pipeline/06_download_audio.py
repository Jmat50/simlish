from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import DATA, ensure_dirs
from pipeline.lib.db import init_db
from pipeline.lib.sources_youtube import download_audio
from tqdm import tqdm


def has_simlish(conn, song_id: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM lyric_documents WHERE song_id=? AND side='simlish' LIMIT 1",
            (song_id,),
        ).fetchone()
        is not None
    )


def main() -> None:
    ensure_dirs()
    conn = init_db()
    yt_dir = DATA / "youtube"
    files = sorted(yt_dir.glob("*.json"))
    done = 0
    for fp in tqdm(files, desc="download audio"):
        song_id = fp.stem
        if has_simlish(conn, song_id):
            continue  # already have fan/official simlish; audio optional
        # still download for ASR if no simlish yet
        meta = json.loads(fp.read_text(encoding="utf-8"))
        url = meta.get("url")
        if not url:
            continue
        existing = list((DATA / "audio").glob(f"{song_id}.*"))
        if existing:
            done += 1
            continue
        path = download_audio(url, DATA / "audio", f"{song_id}.%(ext)s")
        if path:
            meta["audio_path"] = str(path)
            fp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            done += 1
        else:
            print(f"download failed: {song_id}")
    conn.close()
    print(f"Audio ready for {done} songs")


if __name__ == "__main__":
    main()
