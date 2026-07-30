from __future__ import annotations

import sqlite3
from pathlib import Path

from pipeline.config import DB_PATH, SCHEMA_PATH


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    own = conn is None
    conn = conn or connect()
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()
    if own:
        return conn
    return conn


def upsert_song(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        """
        INSERT INTO songs (
          song_id, artist, title, game_section, pack, station, notes,
          has_real_world_original, skip_reason, created_at
        ) VALUES (
          :song_id, :artist, :title, :game_section, :pack, :station, :notes,
          :has_real_world_original, :skip_reason, :created_at
        )
        ON CONFLICT(song_id) DO UPDATE SET
          artist=excluded.artist,
          title=excluded.title,
          game_section=excluded.game_section,
          pack=excluded.pack,
          station=excluded.station,
          notes=excluded.notes,
          has_real_world_original=excluded.has_real_world_original,
          skip_reason=COALESCE(excluded.skip_reason, songs.skip_reason)
        """,
        row,
    )


def set_skip(conn: sqlite3.Connection, song_id: str, reason: str) -> None:
    conn.execute(
        "UPDATE songs SET skip_reason=? WHERE song_id=?",
        (reason, song_id),
    )


def insert_lyric_doc(conn: sqlite3.Connection, row: dict) -> int:
    cur = conn.execute(
        """
        INSERT INTO lyric_documents (
          song_id, side, source_kind, language, text, source_url, confidence, retrieved_at
        ) VALUES (
          :song_id, :side, :source_kind, :language, :text, :source_url, :confidence, :retrieved_at
        )
        """,
        row,
    )
    return int(cur.lastrowid)


def clear_song_alignments(conn: sqlite3.Connection, song_id: str) -> None:
    conn.execute("DELETE FROM word_alignments WHERE song_id=?", (song_id,))
    conn.execute("DELETE FROM line_pairs WHERE song_id=?", (song_id,))
