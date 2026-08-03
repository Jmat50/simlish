from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from slugify import slugify as _slugify


def song_id(artist: str, title: str) -> str:
    return f"{_slugify(artist)}__{_slugify(title)}"

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from v2.config import (
    BOOTSTRAP_LYRICS,
    CATALOG_DIR,
    LYRICS_DIR,
    PHASE1_SONG_IDS,
    ensure_dirs,
)
from v2.lib.wiki import (
    SECTION_RE,
    TABLE_RE,
    fetch_wikitext,
    pair_cells,
    parse_artist_title,
    parse_lyric_table,
)


def bootstrap_from_dictionary() -> list[str]:
    copied = []
    if not BOOTSTRAP_LYRICS.exists():
        return copied
    for src in BOOTSTRAP_LYRICS.glob("*.json"):
        dest = LYRICS_DIR / src.name
        shutil.copy2(src, dest)
        copied.append(src.stem)
    return copied


def parse_from_wikitext(wt: str) -> list[str]:
    written = []
    # split by === headings
    parts = SECTION_RE.split(wt)
    # parts[0] preamble; then heading, body, heading, body...
    it = iter(parts[1:])
    for head, body in zip(it, it):
        artist, title = parse_artist_title(head)
        sid = song_id(artist, title)
        table_m = TABLE_RE.search(body)
        if not table_m:
            continue
        parsed = parse_lyric_table(table_m.group("table"))
        if not parsed:
            continue
        h1, h2, c1, c2 = parsed
        orig_lines, sim_lines = pair_cells(h1, h2, c1, c2)
        n = min(len(orig_lines), len(sim_lines))
        if n < 2:
            continue
        pairs = [
            {
                "line_index": i,
                "original": orig_lines[i],
                "simlish": sim_lines[i],
            }
            for i in range(n)
        ]
        payload = {
            "song_id": sid,
            "artist": artist,
            "title": title,
            "original_header": h1,
            "simlish_header": h2,
            "pairs": pairs,
        }
        (LYRICS_DIR / f"{sid}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        written.append(sid)
    return written


def main() -> None:
    ensure_dirs()
    written: list[str] = []
    try:
        wt = fetch_wikitext()
        written = parse_from_wikitext(wt)
        print(f"Parsed parallel lyric tables from wiki: {len(written)}")
    except Exception as exc:  # noqa: BLE001
        print(f"Wiki lyric parse failed ({exc}); bootstrapping")
        written = bootstrap_from_dictionary()
        print(f"Bootstrapped {len(written)} lyric files")

    if not written:
        written = bootstrap_from_dictionary()
        print(f"Fallback bootstrap {len(written)}")

    # Ensure phase1 set present
    missing = [s for s in PHASE1_SONG_IDS if not (LYRICS_DIR / f"{s}.json").exists()]
    if missing and BOOTSTRAP_LYRICS.exists():
        for sid in missing:
            src = BOOTSTRAP_LYRICS / f"{sid}.json"
            if src.exists():
                shutil.copy2(src, LYRICS_DIR / f"{sid}.json")
                written.append(sid)

    parallel = []
    for p in sorted(LYRICS_DIR.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        parallel.append(
            {
                "song_id": d["song_id"],
                "artist": d.get("artist"),
                "title": d.get("title"),
                "n_pairs": len(d.get("pairs") or []),
            }
        )
    (CATALOG_DIR / "parallel_songs.json").write_text(
        json.dumps(parallel, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"parallel_songs={len(parallel)} -> {CATALOG_DIR / 'parallel_songs.json'}")


if __name__ == "__main__":
    main()
