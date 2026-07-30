from __future__ import annotations

"""Fetch fan-published Simlish lyric sheets when YouTube ASR is unavailable."""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests
from slugify import slugify

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import DATA, REQUEST_SLEEP_S, USER_AGENT, ensure_dirs
from pipeline.lib.db import init_db, insert_lyric_doc, set_skip
from pipeline.lib.sources_lyrics import clean_lyrics


KNOWN_URLS = {
    "3oh-3__double-vision": "https://azlyrics.biz/3/3oh3-lyrics/3oh3-double-vision-simlish-version-lyrics/",
    "5-seconds-of-summer__want-you-back": "https://azlyrics.biz/5/5-seconds-of-summer-lyrics/5-seconds-of-summer-want-you-back-simlish-lyrics/",
}


def extract_azlyrics_biz(html: str) -> str | None:
    # Content is mostly plain after the h1; strip scripts/nav heuristically
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    # Keep from first [verse]/[chorus] or long nonsense block
    m = re.search(r"(\[[^\]]+\][\s\S]+?)(?:Random Lyrics|HOT LYRICS|$)", text, re.I)
    blob = m.group(1) if m else text
    blob = clean_lyrics(blob)
    # drop english-looking instructional lines
    lines = []
    for ln in blob.splitlines():
        low = ln.lower()
        if "lyrics" in low and len(ln.split()) < 8:
            continue
        if low.startswith("play music"):
            continue
        lines.append(ln)
    out = "\n".join(lines).strip()
    if len(re.findall(r"[A-Za-z']+", out)) < 40:
        return None
    return out


def fetch_url(url: str) -> str | None:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        time.sleep(REQUEST_SLEEP_S)
        if r.status_code != 200:
            return None
        return extract_azlyrics_biz(r.text)
    except Exception:  # noqa: BLE001
        return None


def guess_urls(artist: str, title: str) -> list[str]:
    a = slugify(artist)
    t = slugify(title)
    return [
        f"https://azlyrics.biz/{a[0]}/{a}-lyrics/{a}-{t}-simlish-lyrics/",
        f"https://azlyrics.biz/{a[0]}/{a}-lyrics/{a}-{t}-simlish-version-lyrics/",
        f"https://genius.com/{a}-{t}-simlish-version-lyrics",
    ]


def main() -> None:
    ensure_dirs()
    conn = init_db()
    rows = conn.execute(
        """
        SELECT s.song_id, s.artist, s.title FROM songs s
        WHERE EXISTS (
          SELECT 1 FROM lyric_documents d WHERE d.song_id=s.song_id AND d.side='original'
        ) AND NOT EXISTS (
          SELECT 1 FROM lyric_documents d WHERE d.song_id=s.song_id AND d.side='simlish'
        )
        """
    ).fetchall()
    print(f"Fan lyric candidates: {len(rows)}")
    got = 0
    for row in rows:
        song_id = row["song_id"]
        urls = []
        if song_id in KNOWN_URLS:
            urls.append(KNOWN_URLS[song_id])
        urls.extend(guess_urls(row["artist"], row["title"]))
        text = None
        used = None
        for url in urls:
            text = fetch_url(url)
            if text:
                used = url
                break
        if not text:
            # mark youtube blocked if we had a yt meta
            yt = DATA / "youtube" / f"{song_id}.json"
            if yt.exists():
                set_skip(conn, song_id, "youtube_bot_check_no_fan_lyrics")
            continue
        insert_lyric_doc(
            conn,
            {
                "song_id": song_id,
                "side": "simlish",
                "source_kind": "fan_page",
                "language": "simlish",
                "text": text,
                "source_url": used,
                "confidence": 0.75,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        (DATA / "lyrics" / "simlish" / f"{song_id}.json").write_text(
            json.dumps({"text": text, "source_kind": "fan_page", "url": used}, indent=2),
            encoding="utf-8",
        )
        conn.execute("UPDATE songs SET skip_reason=NULL WHERE song_id=?", (song_id,))
        got += 1
        print(f"Fan lyrics: {row['artist']} - {row['title']}")
    conn.commit()
    conn.close()
    print(f"Inserted fan Simlish for {got} songs")


if __name__ == "__main__":
    main()
