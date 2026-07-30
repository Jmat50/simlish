from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import DATA, ensure_dirs
from pipeline.lib.db import init_db


def main() -> None:
    ensure_dirs()
    conn = init_db()
    reports = DATA / "reports"

    total = conn.execute("SELECT COUNT(*) AS c FROM songs").fetchone()["c"]
    official = conn.execute(
        "SELECT COUNT(DISTINCT song_id) AS c FROM lyric_documents WHERE source_kind='wiki_official' AND side='simlish'"
    ).fetchone()["c"]
    originals = conn.execute(
        "SELECT COUNT(DISTINCT song_id) AS c FROM lyric_documents WHERE side='original'"
    ).fetchone()["c"]
    simlish = conn.execute(
        "SELECT COUNT(DISTINCT song_id) AS c FROM lyric_documents WHERE side='simlish'"
    ).fetchone()["c"]
    aligned = conn.execute(
        "SELECT COUNT(DISTINCT song_id) AS c FROM word_alignments"
    ).fetchone()["c"]
    dict_n = conn.execute("SELECT COUNT(*) AS c FROM dictionary").fetchone()["c"]
    multi = conn.execute(
        "SELECT COUNT(*) AS c FROM dictionary WHERE simlish_2 IS NOT NULL"
    ).fetchone()["c"]
    official_align = conn.execute(
        "SELECT COUNT(*) AS c FROM word_alignments WHERE source_kind='wiki_official'"
    ).fetchone()["c"]

    skips = conn.execute(
        "SELECT skip_reason, COUNT(*) AS c FROM songs WHERE skip_reason IS NOT NULL GROUP BY skip_reason"
    ).fetchall()

    # skips.csv — every song status
    with (reports / "skips.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["song_id", "artist", "title", "status", "skip_reason"])
        for row in conn.execute("SELECT song_id, artist, title, skip_reason FROM songs ORDER BY artist, title"):
            has_a = conn.execute(
                "SELECT 1 FROM word_alignments WHERE song_id=? LIMIT 1", (row["song_id"],)
            ).fetchone()
            if has_a:
                status = "aligned"
            elif row["skip_reason"]:
                status = "skipped"
            else:
                status = "partial"
            w.writerow([row["song_id"], row["artist"], row["title"], status, row["skip_reason"] or ""])

    # conflicts: many divergent simlish forms
    with (reports / "conflicts.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["original_word", "n_forms", "forms"])
        for row in conn.execute(
            """
            SELECT original_word, simlish_1, simlish_2, simlish_3, simlish_4, simlish_5,
                   simlish_6, simlish_7, simlish_8, simlish_9, simlish_10, simlish_extra
            FROM dictionary
            """
        ):
            forms = [row[f"simlish_{i}"] for i in range(1, 11) if row[f"simlish_{i}"]]
            if row["simlish_extra"]:
                forms.append(row["simlish_extra"])
            if len(forms) >= 4:
                w.writerow([row["original_word"], len(forms), "|".join(forms[:10])])

    top = conn.execute(
        "SELECT original_word, occurrence_count, simlish_1, simlish_2 FROM dictionary ORDER BY occurrence_count DESC LIMIT 20"
    ).fetchall()

    spot = conn.execute(
        """
        SELECT original_word, simlish_1, simlish_2, occurrence_count
        FROM dictionary
        WHERE original_word IN ('pressure','smile','hot','cold','empty','feeling')
        ORDER BY original_word
        """
    ).fetchall()

    lines = [
        "# Coverage report",
        "",
        f"- Songs catalogued: **{total}**",
        f"- Songs with official wiki Simlish lyrics: **{official}**",
        f"- Songs with original lyric docs: **{originals}**",
        f"- Songs with Simlish lyric docs: **{simlish}**",
        f"- Songs with word alignments: **{aligned}**",
        f"- Official word_alignment rows: **{official_align}**",
        f"- Dictionary entries: **{dict_n}** (multi-form: **{multi}**)",
        "",
        "## Skip reasons",
        "",
    ]
    for s in skips:
        lines.append(f"- `{s['skip_reason']}`: {s['c']}")
    lines += ["", "## Top 20 original words", ""]
    for t in top:
        lines.append(
            f"- `{t['original_word']}` -> `{t['simlish_1']}`"
            + (f" / `{t['simlish_2']}`" if t["simlish_2"] else "")
            + f" (n={t['occurrence_count']})"
        )
    lines += ["", "## Spot checks", ""]
    if spot:
        for s in spot:
            lines.append(f"- `{s['original_word']}` -> `{s['simlish_1']}` (n={s['occurrence_count']})")
    else:
        lines.append("- (no spot-check hits yet)")

    (reports / "coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        print("\n".join(lines))
    except UnicodeEncodeError:
        print((reports / "coverage.md").read_text(encoding="utf-8"))
    conn.close()


if __name__ == "__main__":
    main()
