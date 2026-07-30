from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from slugify import slugify

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import (
    DATA,
    MAXIS_ONLY_TITLES,
    URBZ_ORIGINAL_ARTISTS,
    ensure_dirs,
)
from pipeline.lib.db import init_db, upsert_song


SECTION_RE = re.compile(r"^(={2,3})\s*([^=]+?)\s*\1\s*$", re.M)
ROW_RE = re.compile(
    r'^\|\s*(?P<artist>.+?)\s*\|\|\s*"(?P<title>[^"]+)"\s*(?:\|\|\s*(?P<rest>.*))?$',
    re.M,
)


def strip_wiki_links(s: str) -> str:
    s = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.I | re.S)
    s = re.sub(r"<ref[^/]*/>", "", s, flags=re.I)
    s = re.sub(r"'{2,}", "", s)
    return s.strip()


def parse_rest(rest: str | None) -> tuple[str | None, str | None]:
    if not rest:
        return None, None
    parts = [p.strip() for p in rest.split("||")]
    station = strip_wiki_links(parts[0]) if parts else None
    notes = strip_wiki_links(parts[1]) if len(parts) > 1 else None
    if station == "":
        station = None
    if notes == "":
        notes = None
    return station, notes


def current_section_stack(text: str, pos: int) -> tuple[str | None, str | None]:
    """Return (h2, h3) active at character position."""
    h2 = None
    h3 = None
    for m in SECTION_RE.finditer(text):
        if m.start() > pos:
            break
        level = len(m.group(1))
        title = strip_wiki_links(m.group(2))
        title = re.sub(r"<ref.*", "", title).strip()
        if level == 2:
            h2 = title
            h3 = None
        elif level == 3:
            h3 = title
    return h2, h3


def is_real_world(artist: str, title: str, game_section: str | None) -> bool:
    t = title.casefold().strip()
    a = artist.casefold().strip()
    if t in MAXIS_ONLY_TITLES:
        return False
    if game_section and "urbz" in game_section.casefold():
        if a in URBZ_ORIGINAL_ARTISTS:
            return False
    return True


def make_song_id(artist: str, title: str, used: set[str]) -> str:
    base = f"{slugify(artist)}__{slugify(title)}"
    sid = base
    n = 2
    while sid in used:
        sid = f"{base}_{n}"
        n += 1
    used.add(sid)
    return sid


def main() -> None:
    ensure_dirs()
    wt_path = DATA / "catalog" / "Songs_in_Simlish.wikitext"
    if not wt_path.exists():
        raise SystemExit("Run 01_fetch_wiki.py first")
    text = wt_path.read_text(encoding="utf-8")

    songs = []
    used_ids: set[str] = set()
    now = datetime.now(timezone.utc).isoformat()

    for m in ROW_RE.finditer(text):
        artist = strip_wiki_links(m.group("artist"))
        title = m.group("title").strip()
        station, notes = parse_rest(m.group("rest"))
        game, pack = current_section_stack(text, m.start())
        # Skip header-ish false positives
        if artist.lower() in {"artist", "! width"} or title.lower() == "song":
            continue
        song_id = make_song_id(artist, title, used_ids)
        real = is_real_world(artist, title, game)
        row = {
            "song_id": song_id,
            "artist": artist,
            "title": title,
            "game_section": game,
            "pack": pack,
            "station": station,
            "notes": notes,
            "has_real_world_original": 1 if real else 0,
            "skip_reason": None if real else "simlish_original_no_english",
            "created_at": now,
        }
        songs.append(row)

    out = DATA / "catalog" / "songs.json"
    out.write_text(json.dumps(songs, ensure_ascii=False, indent=2), encoding="utf-8")

    conn = init_db()
    for row in songs:
        upsert_song(conn, row)
    conn.commit()
    conn.close()
    print(f"Catalogued {len(songs)} songs -> {out}")


if __name__ == "__main__":
    main()
