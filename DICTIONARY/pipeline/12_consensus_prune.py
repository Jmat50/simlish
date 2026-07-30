from __future__ import annotations

"""
Scan multi-form English↔Simlish maps for consensus across independent
official soundtrack songs (wiki_official only).

A pair (original, simlish) is consensus if it appears in ≥2 distinct song_ids.
When an English word has multiple Simlish forms and at least one consensus form,
keep only the consensus form(s) and delete other alignments for that English word.
Then rebuild the dictionary table.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import DATA, SIMLISH_COLS, ensure_dirs
from pipeline.lib.db import init_db
from pipeline.lib.english_filter import is_english_token, load_english


def rebuild_dictionary(conn, english: set[str]) -> tuple[int, int]:
    conn.execute("DELETE FROM dictionary")
    rows = conn.execute(
        """
        SELECT original_word, original_norm, simlish_word, simlish_norm, source_kind, confidence
        FROM word_alignments
        WHERE source_kind='wiki_official'
        """
    ).fetchall()

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
        cols = [
            sim_surface[on][sn].most_common(1)[0][0].casefold()
            for sn in ordered[:SIMLISH_COLS]
        ]
        extra = None
        if len(ordered) > SIMLISH_COLS:
            extra = json.dumps(
                [
                    sim_surface[on][sn].most_common(1)[0][0].casefold()
                    for sn in ordered[SIMLISH_COLS:]
                ],
                ensure_ascii=False,
            )
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

    n = conn.execute("SELECT COUNT(*) AS c FROM dictionary").fetchone()["c"]
    multi = conn.execute(
        "SELECT COUNT(*) AS c FROM dictionary WHERE simlish_2 IS NOT NULL"
    ).fetchone()["c"]
    return n, multi


def main() -> None:
    ensure_dirs()
    english = load_english()
    conn = init_db()

    rows = conn.execute(
        """
        SELECT alignment_id, original_norm, simlish_norm, source_kind, song_id
        FROM word_alignments
        WHERE source_kind='wiki_official'
        """
    ).fetchall()

    pair_songs: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_ids: dict[tuple[str, str], list[int]] = defaultdict(list)
    en_to_sim: dict[str, set[str]] = defaultdict(set)
    sim_to_en: dict[str, set[str]] = defaultdict(set)

    for r in rows:
        on, sn, sid = r["original_norm"], r["simlish_norm"], r["song_id"]
        if not on or not sn or is_english_token(sn, english):
            continue
        pair_songs[(on, sn)].add(sid)
        pair_ids[(on, sn)].append(r["alignment_id"])
        en_to_sim[on].add(sn)
        sim_to_en[sn].add(on)

    def is_consensus(on: str, sn: str) -> bool:
        return len(pair_songs[(on, sn)]) >= 2

    multi_en = {on: sims for on, sims in en_to_sim.items() if len(sims) > 1}
    multi_sim = {sn: ens for sn, ens in sim_to_en.items() if len(ens) > 1}

    consensus_pairs = {
        (on, sn): {"songs": sorted(pair_songs[(on, sn)])}
        for (on, sn) in pair_songs
        if is_consensus(on, sn)
    }

    prune_targets: dict[str, set[str]] = {}
    for on, sims in multi_en.items():
        keep = {sn for sn in sims if is_consensus(on, sn)}
        if keep:
            prune_targets[on] = keep

    sim_consensus_multi = []
    for sn, ens in multi_sim.items():
        keep_en = {on for on in ens if is_consensus(on, sn)}
        if keep_en:
            sim_consensus_multi.append(
                {
                    "simlish": sn,
                    "consensus_english": sorted(keep_en),
                    "other_english": sorted(ens - keep_en),
                }
            )

    report = {
        "alignment_rows_scanned": len(rows),
        "unique_pairs": len(pair_songs),
        "english_with_multiple_simlish": len(multi_en),
        "simlish_with_multiple_english": len(multi_sim),
        "pairs_with_2plus_songs": len(consensus_pairs),
        "english_pruned_to_consensus": len(prune_targets),
        "simlish_multi_with_consensus_english": len(sim_consensus_multi),
        "consensus_pair_details": [
            {"original": on, "simlish": sn, **meta}
            for (on, sn), meta in sorted(consensus_pairs.items())
        ],
        "prune_actions": [
            {
                "original": on,
                "keep": sorted(keep),
                "drop": sorted(en_to_sim[on] - keep),
                "keep_songs": {
                    sn: sorted(pair_songs[(on, sn)]) for sn in sorted(keep)
                },
            }
            for on, keep in sorted(prune_targets.items())
        ],
        "simlish_vice_versa_examples": sim_consensus_multi[:40],
    }

    deleted = 0
    for on, keep in prune_targets.items():
        for sn in en_to_sim[on] - keep:
            ids = pair_ids[(on, sn)]
            if not ids:
                continue
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"DELETE FROM word_alignments WHERE alignment_id IN ({placeholders})",
                ids,
            )
            deleted += len(ids)

    n, multi = rebuild_dictionary(conn, english)
    conn.commit()
    conn.close()
    conn = init_db()
    conn.execute("VACUUM")
    conn.close()

    report["alignments_deleted"] = deleted
    report["dictionary_entries_after"] = n
    report["dictionary_multi_form_after"] = multi

    out = DATA / "reports" / "consensus_prune.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "english_with_multiple_simlish",
                    "simlish_with_multiple_english",
                    "pairs_with_2plus_songs",
                    "english_pruned_to_consensus",
                    "alignments_deleted",
                    "dictionary_entries_after",
                    "dictionary_multi_form_after",
                )
            },
            indent=2,
        )
    )
    print(f"wrote {out}")
    for ex in report["prune_actions"]:
        print(f"PRUNE {ex['original']}: keep={ex['keep']} drop={ex['drop']}")


if __name__ == "__main__":
    main()
