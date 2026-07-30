from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import CONFIDENCE_MIN, SIMLISH_COLS, ensure_dirs
from pipeline.lib.db import init_db
from pipeline.lib.english_filter import is_english_token, load_english


def main() -> None:
    ensure_dirs()
    english = load_english()
    conn = init_db()
    conn.execute("DELETE FROM dictionary")

    rows = conn.execute(
        """
        SELECT original_word, original_norm, simlish_word, simlish_norm, source_kind, confidence
        FROM word_alignments
        WHERE source_kind='wiki_official' OR confidence >= ?
        """,
        (CONFIDENCE_MIN,),
    ).fetchall()

    # original_norm -> Counter of simlish_norm, and surface forms
    sim_counts: dict[str, Counter] = defaultdict(Counter)
    orig_surface: dict[str, Counter] = defaultdict(Counter)
    sim_surface: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    occ: Counter = Counter()

    for r in rows:
        on = r["original_norm"]
        sn = r["simlish_norm"]
        if not on or not sn:
            continue
        if is_english_token(sn, english) or is_english_token(r["simlish_word"], english):
            continue
        sim_counts[on][sn] += 1
        orig_surface[on][r["original_word"]] += 1
        sim_surface[on][sn][r["simlish_word"]] += 1
        occ[on] += 1

    for on, counter in sim_counts.items():
        ordered = [sn for sn, _ in counter.most_common()]
        surface_orig = orig_surface[on].most_common(1)[0][0].casefold()
        cols = []
        for sn in ordered[:SIMLISH_COLS]:
            cols.append(sim_surface[on][sn].most_common(1)[0][0].casefold())
        extra = None
        if len(ordered) > SIMLISH_COLS:
            extra_forms = []
            for sn in ordered[SIMLISH_COLS:]:
                extra_forms.append(sim_surface[on][sn].most_common(1)[0][0].casefold())
            extra = json.dumps(extra_forms, ensure_ascii=False)

        while len(cols) < SIMLISH_COLS:
            cols.append(None)

        conn.execute(
            """
            INSERT INTO dictionary (
              original_word,
              simlish_1, simlish_2, simlish_3, simlish_4, simlish_5,
              simlish_6, simlish_7, simlish_8, simlish_9, simlish_10,
              simlish_extra, occurrence_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (surface_orig, *cols, extra, int(occ[on])),
        )

    conn.commit()
    n = conn.execute("SELECT COUNT(*) AS c FROM dictionary").fetchone()["c"]
    multi = conn.execute(
        "SELECT COUNT(*) AS c FROM dictionary WHERE simlish_2 IS NOT NULL"
    ).fetchone()["c"]
    conn.execute("VACUUM")
    conn.close()
    print(f"dictionary entries={n} multi_form={multi}")


if __name__ == "__main__":
    main()
