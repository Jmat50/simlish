from __future__ import annotations

"""Remove English dictionary words from simlish_1..simlish_10 (and simlish_extra)."""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import DB_PATH, SIMLISH_COLS
from pipeline.lib.english_filter import is_english_token, load_english


def compact(forms: list[str]) -> tuple[list[str | None], str | None]:
    uniq: list[str] = []
    seen = set()
    for f in forms:
        key = f.casefold()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f.casefold())
    cols = uniq[:SIMLISH_COLS]
    while len(cols) < SIMLISH_COLS:
        cols.append(None)
    extra = json.dumps(uniq[SIMLISH_COLS:], ensure_ascii=False) if len(uniq) > SIMLISH_COLS else None
    return cols, extra


def main() -> None:
    english = load_english()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT * FROM dictionary").fetchall()
    removed_cells = 0
    deleted_rows = 0
    updated = 0

    for row in rows:
        forms: list[str] = []
        for i in range(1, SIMLISH_COLS + 1):
            v = row[f"simlish_{i}"]
            if not v:
                continue
            if is_english_token(v, english):
                removed_cells += 1
                continue
            forms.append(v)
        if row["simlish_extra"]:
            try:
                extra_list = json.loads(row["simlish_extra"])
            except json.JSONDecodeError:
                extra_list = []
            for v in extra_list:
                if is_english_token(str(v), english):
                    removed_cells += 1
                    continue
                forms.append(str(v))

        cols, extra = compact(forms)
        if cols[0] is None:
            conn.execute("DELETE FROM dictionary WHERE original_word=?", (row["original_word"],))
            deleted_rows += 1
            continue

        conn.execute(
            """
            UPDATE dictionary SET
              simlish_1=?, simlish_2=?, simlish_3=?, simlish_4=?, simlish_5=?,
              simlish_6=?, simlish_7=?, simlish_8=?, simlish_9=?, simlish_10=?,
              simlish_extra=?
            WHERE original_word=?
            """,
            (*cols, extra, row["original_word"]),
        )
        updated += 1

    align_removed = 0
    for (aid, sw) in conn.execute("SELECT alignment_id, simlish_word FROM word_alignments"):
        if is_english_token(sw, english):
            conn.execute("DELETE FROM word_alignments WHERE alignment_id=?", (aid,))
            align_removed += 1

    conn.commit()
    remaining = conn.execute("SELECT COUNT(*) FROM dictionary").fetchone()[0]
    conn.close()
    print(
        f"removed_cells={removed_cells} updated_rows={updated} "
        f"deleted_rows={deleted_rows} alignments_removed={align_removed} "
        f"dictionary_remaining={remaining}"
    )


if __name__ == "__main__":
    main()
