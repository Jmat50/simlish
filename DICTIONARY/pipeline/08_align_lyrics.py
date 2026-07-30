from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import CONFIDENCE_MIN, DATA, ensure_dirs
from pipeline.lib.align import align_lines, alignments_from_line_pair
from pipeline.lib.db import clear_song_alignments, init_db
from pipeline.lib.tokenize import split_lyric_lines
from tqdm import tqdm


def main() -> None:
    ensure_dirs()
    conn = init_db()
    # Songs that have both sides but may lack line_pairs (official already has pairs)
    rows = conn.execute(
        """
        SELECT s.song_id FROM songs s
        WHERE EXISTS (
          SELECT 1 FROM lyric_documents d WHERE d.song_id=s.song_id AND d.side='original'
        ) AND EXISTS (
          SELECT 1 FROM lyric_documents d WHERE d.song_id=s.song_id AND d.side='simlish'
        )
        """
    ).fetchall()

    aligned = 0
    for row in tqdm(rows, desc="align"):
        song_id = row["song_id"]
        # Skip if official alignments already present
        existing = conn.execute(
            "SELECT COUNT(*) AS c FROM word_alignments WHERE song_id=? AND source_kind='wiki_official'",
            (song_id,),
        ).fetchone()["c"]
        if existing:
            aligned += 1
            continue

        orig = conn.execute(
            """
            SELECT text, source_kind, confidence FROM lyric_documents
            WHERE song_id=? AND side='original'
            ORDER BY confidence DESC, doc_id DESC LIMIT 1
            """,
            (song_id,),
        ).fetchone()
        sim = conn.execute(
            """
            SELECT text, source_kind, confidence FROM lyric_documents
            WHERE song_id=? AND side='simlish'
            ORDER BY
              CASE source_kind
                WHEN 'wiki_official' THEN 3
                WHEN 'fan_page' THEN 2
                WHEN 'whisper' THEN 1
                ELSE 0
              END DESC,
              confidence DESC, doc_id DESC
            LIMIT 1
            """,
            (song_id,),
        ).fetchone()
        if not orig or not sim:
            continue

        o_lines = split_lyric_lines(orig["text"])
        s_lines = split_lyric_lines(sim["text"])
        pairs, method = align_lines(o_lines, s_lines)
        if not pairs:
            continue

        conf = min(float(orig["confidence"] or 0.5), float(sim["confidence"] or 0.5))
        if sim["source_kind"] == "whisper":
            conf = min(conf, 0.6)
        if conf < CONFIDENCE_MIN and sim["source_kind"] != "wiki_official":
            # still align but low conf rows may be filtered later
            pass

        clear_song_alignments(conn, song_id)
        payload = []
        for i, (ol, sl) in enumerate(pairs):
            cur = conn.execute(
                """
                INSERT INTO line_pairs (song_id, line_index, original_line, simlish_line, align_method)
                VALUES (?, ?, ?, ?, ?)
                """,
                (song_id, i, ol, sl, method if method != "wiki_cell_parallel" else "length_ratio"),
            )
            pair_id = cur.lastrowid
            payload.append({"original": ol, "simlish": sl})
            for al in alignments_from_line_pair(ol, sl):
                conn.execute(
                    """
                    INSERT INTO word_alignments (
                      song_id, pair_id, original_word, original_norm,
                      simlish_word, simlish_norm, source_kind, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        song_id,
                        pair_id,
                        al["original_word"],
                        al["original_norm"],
                        al["simlish_word"],
                        al["simlish_norm"],
                        sim["source_kind"],
                        conf,
                    ),
                )
        (DATA / "alignments" / f"{song_id}.json").write_text(
            json.dumps({"song_id": song_id, "pairs": payload, "confidence": conf}, indent=2),
            encoding="utf-8",
        )
        aligned += 1
        conn.execute("UPDATE songs SET skip_reason=NULL WHERE song_id=?", (song_id,))

    conn.commit()
    conn.close()
    print(f"Aligned {aligned} songs with both lyric sides")


if __name__ == "__main__":
    main()
