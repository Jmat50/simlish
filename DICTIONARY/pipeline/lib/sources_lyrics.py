from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests

from pipeline.config import LRCLIB_TIMEOUT_S, REQUEST_SLEEP_S, USER_AGENT


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_lyrics(text: str) -> str:
    if not text:
        return ""
    lines = []
    for line in text.replace("\r\n", "\n").split("\n"):
        s = line.strip()
        if not s:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if re.fullmatch(r"\[.*?\]", s):
            continue
        if s.lower().startswith("http"):
            continue
        lines.append(s)
    return "\n".join(lines).strip()


def fetch_lrclib(artist: str, title: str) -> dict[str, Any] | None:
    headers = {"User-Agent": USER_AGENT}
    url = "https://lrclib.net/api/search"
    try:
        r = requests.get(
            url,
            params={"artist_name": artist, "track_name": title},
            headers=headers,
            timeout=LRCLIB_TIMEOUT_S,
        )
        time.sleep(REQUEST_SLEEP_S)
        results = []
        if r.status_code == 200:
            results = r.json() or []
        if not results:
            r2 = requests.get(
                url,
                params={"q": f"{artist} {title}"},
                headers=headers,
                timeout=LRCLIB_TIMEOUT_S,
            )
            time.sleep(REQUEST_SLEEP_S)
            if r2.status_code == 200:
                results = r2.json() or []
        if not results:
            return None
        best = results[0]
        plain = best.get("plainLyrics") or best.get("syncedLyrics") or ""
        plain = re.sub(r"\[\d+:\d+(?:\.\d+)?\]", "", plain)
        plain = clean_lyrics(plain)
        if len(plain) < 40:
            return None
        return {
            "text": plain,
            "source_kind": "lrclib",
            "source_url": f"https://lrclib.net/api/search?artist_name={quote(artist)}&track_name={quote(title)}",
            "language": "und",
            "confidence": 0.85,
            "retrieved_at": _now(),
        }
    except Exception:  # noqa: BLE001
        return None


def load_override(path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    text = clean_lyrics(path.read_text(encoding="utf-8"))
    if len(text) < 10:
        return None
    return {
        "text": text,
        "source_kind": "override",
        "source_url": str(path),
        "language": "und",
        "confidence": 1.0,
        "retrieved_at": _now(),
    }
