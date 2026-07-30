from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import DATA, ensure_dirs
from pipeline.lib.asr import transcribe_audio
from pipeline.lib.db import init_db, insert_lyric_doc
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
    audio_files = sorted((DATA / "audio").glob("*"))
    n = 0
    for audio in tqdm(audio_files, desc="whisper"):
        song_id = audio.stem
        if has_simlish(conn, song_id):
            continue
        try:
            result = transcribe_audio(audio)
        except Exception as exc:  # noqa: BLE001
            print(f"ASR failed {song_id}: {exc}")
            continue
        (DATA / "transcripts" / f"{song_id}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if result.get("needs_review") and (not result.get("text") or len(result["text"]) < 20):
            continue
        insert_lyric_doc(
            conn,
            {
                "song_id": song_id,
                "side": "simlish",
                "source_kind": "whisper",
                "language": "simlish",
                "text": result["text"],
                "source_url": None,
                "confidence": float(result.get("confidence") or 0.4),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        (DATA / "lyrics" / "simlish" / f"{song_id}.json").write_text(
            json.dumps(
                {
                    "text": result["text"],
                    "source_kind": "whisper",
                    "confidence": result.get("confidence"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        n += 1
    conn.commit()
    conn.close()
    print(f"Whisper transcripts inserted for {n} songs")


if __name__ == "__main__":
    main()
