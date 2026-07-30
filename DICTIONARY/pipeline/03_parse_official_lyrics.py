from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from slugify import slugify

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import DATA, ensure_dirs
from pipeline.lib.align import align_lines, alignments_from_line_pair
from pipeline.lib.db import clear_song_alignments, init_db, insert_lyric_doc, upsert_song
from pipeline.lib.tokenize import split_lyric_lines


SECTION_RE = re.compile(r"^===\s*(.+?)\s*===\s*$", re.M)
TABLE_RE = re.compile(
    r"\{\|\s*class=\"wikitable\"(?P<table>[\s\S]*?)\|\}",
    re.M,
)


def parse_artist_title(head: str) -> tuple[str, str]:
    head = re.sub(r"<ref.*", "", head).strip()
    head = re.sub(r"\[\[|\]\]", "", head)
    for sep in (" - ", " – ", " — "):
        if sep in head:
            a, t = head.split(sep, 1)
            return a.strip(), t.strip()
    return "Unknown", head


def parse_table(table_body: str) -> tuple[str, str, str, str] | None:
    """Return (h1, h2, cell1, cell2) or None."""
    # Headers: lines starting with !  (may be !A!!B on one line)
    headers: list[str] = []
    for line in table_body.splitlines():
        if not line.startswith("!"):
            if headers:
                break
            continue
        # split wiki header cells
        raw = line.lstrip("!")
        parts = re.split(r"!!", raw)
        for part in parts:
            part = part.strip()
            if "|" in part:
                part = part.split("|")[-1].strip()
            if part:
                headers.append(part)
        if len(headers) >= 2:
            break
    if len(headers) < 2:
        return None
    h1, h2 = headers[0], headers[1]
    if "SIMLISH" not in (h1 + h2).upper():
        return None

    # After first |- following headers, two cells separated by leading |
    # Find content after first data row marker
    m = re.search(r"\|-\s*\n\|([\s\S]*)$", table_body)
    if not m:
        return None
    rest = m.group(1)
    # Split into two cells on a line that is exactly "|"
    parts = re.split(r"\n\|\n", rest, maxsplit=1)
    if len(parts) < 2:
        # try split on \n| at start of cell2
        parts = re.split(r"\n\|(?=[^\|\-])", rest, maxsplit=1)
    if len(parts) < 2:
        return None
    c1 = parts[0].strip()
    c2 = parts[1].strip()
    # trim trailing table junk
    c2 = re.sub(r"\n\|\}[\s\S]*$", "", c2).strip()
    return h1, h2, c1, c2


def find_song_id(conn, artist: str, title: str) -> str:
    cur = conn.execute(
        "SELECT song_id FROM songs WHERE lower(artist)=lower(?) AND lower(title)=lower(?)",
        (artist, title),
    )
    row = cur.fetchone()
    if row:
        return row["song_id"]
    # Prefer same artist + fuzzy title
    first = artist.casefold().split()[0] if artist else ""
    cur = conn.execute(
        "SELECT song_id, artist, title FROM songs WHERE lower(title)=lower(?)",
        (title,),
    )
    rows = cur.fetchall()
    for r in rows:
        if first and first in r["artist"].casefold():
            return r["song_id"]
    # Do not bind unrelated artists that share a title (e.g. Overwerk vs Paramore "Pressure")
    sid = f"{slugify(artist)}__{slugify(title)}"
    upsert_song(
        conn,
        {
            "song_id": sid,
            "artist": artist,
            "title": title,
            "game_section": "Simlish Lyrics",
            "pack": None,
            "station": None,
            "notes": "from official lyric section",
            "has_real_world_original": 1,
            "skip_reason": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return sid


def main() -> None:
    ensure_dirs()
    wt = (DATA / "catalog" / "Songs_in_Simlish.wikitext").read_text(encoding="utf-8")
    idx = wt.find("==Simlish Lyrics==")
    body = wt[idx:] if idx >= 0 else wt

    # Split body by === headings
    heads = list(SECTION_RE.finditer(body))
    conn = init_db()
    now = datetime.now(timezone.utc).isoformat()
    count = 0

    for i, hm in enumerate(heads):
        head = hm.group(1).strip()
        start = hm.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        chunk = body[start:end]
        tm = TABLE_RE.search(chunk)
        if not tm:
            continue
        parsed = parse_table(tm.group("table"))
        if not parsed:
            print(f"Skip (no SIMLISH table): {head}")
            continue
        h1, h2, c1, c2 = parsed
        if "SIMLISH" in h2.upper():
            orig_h, sim_h, orig_c, sim_c = h1, h2, c1, c2
        else:
            orig_h, sim_h, orig_c, sim_c = h2, h1, c2, c1

        artist, title = parse_artist_title(head)
        song_id = find_song_id(conn, artist, title)
        orig_lines = split_lyric_lines(orig_c)
        sim_lines = split_lyric_lines(sim_c)
        pairs, method = align_lines(orig_lines, sim_lines)
        if not pairs:
            print(f"No pairs for {head} ({len(orig_lines)} vs {len(sim_lines)})")
            continue

        lang = "gsw" if "GERMAN" in orig_h.upper() else "en"
        # Remove prior official docs for idempotency
        conn.execute(
            "DELETE FROM lyric_documents WHERE song_id=? AND source_kind='wiki_official'",
            (song_id,),
        )
        insert_lyric_doc(
            conn,
            {
                "song_id": song_id,
                "side": "original",
                "source_kind": "wiki_official",
                "language": lang,
                "text": "\n".join(orig_lines),
                "source_url": "https://sims.fandom.com/wiki/Songs_in_Simlish",
                "confidence": 1.0,
                "retrieved_at": now,
            },
        )
        insert_lyric_doc(
            conn,
            {
                "song_id": song_id,
                "side": "simlish",
                "source_kind": "wiki_official",
                "language": "simlish",
                "text": "\n".join(sim_lines),
                "source_url": "https://sims.fandom.com/wiki/Songs_in_Simlish",
                "confidence": 1.0,
                "retrieved_at": now,
            },
        )

        clear_song_alignments(conn, song_id)
        payload_pairs = []
        for li, (ol, sl) in enumerate(pairs):
            cur = conn.execute(
                """
                INSERT INTO line_pairs (song_id, line_index, original_line, simlish_line, align_method)
                VALUES (?, ?, ?, ?, ?)
                """,
                (song_id, li, ol, sl, method),
            )
            pair_id = cur.lastrowid
            payload_pairs.append({"line_index": li, "original": ol, "simlish": sl})
            for al in alignments_from_line_pair(ol, sl):
                conn.execute(
                    """
                    INSERT INTO word_alignments (
                      song_id, pair_id, original_word, original_norm,
                      simlish_word, simlish_norm, source_kind, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, 'wiki_official', 1.0)
                    """,
                    (
                        song_id,
                        pair_id,
                        al["original_word"],
                        al["original_norm"],
                        al["simlish_word"],
                        al["simlish_norm"],
                    ),
                )

        (DATA / "lyrics" / "official" / f"{song_id}.json").write_text(
            json.dumps(
                {
                    "song_id": song_id,
                    "artist": artist,
                    "title": title,
                    "original_header": orig_h,
                    "simlish_header": sim_h,
                    "pairs": payload_pairs,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        conn.execute("UPDATE songs SET skip_reason=NULL WHERE song_id=?", (song_id,))
        count += 1
        print(f"Official lyrics: {artist} - {title} ({len(pairs)} lines)")

    conn.commit()
    conn.close()
    print(f"Parsed {count} official lyric tables")


if __name__ == "__main__":
    main()
