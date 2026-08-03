from __future__ import annotations

import re
import time
from typing import Any

import requests

from v2.config import REQUEST_SLEEP_S, USER_AGENT, WIKI_API, WIKI_PAGE


def wiki_get(params: dict[str, Any]) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(WIKI_API, params=params, headers=headers, timeout=60)
    r.raise_for_status()
    time.sleep(REQUEST_SLEEP_S)
    return r.json()


def fetch_wikitext(title: str = WIKI_PAGE) -> str:
    data = wiki_get(
        {
            "action": "parse",
            "page": title,
            "prop": "wikitext",
            "format": "json",
            "formatversion": 2,
        }
    )
    return data["parse"]["wikitext"]


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


def _clean_cell(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"\{\{.*?\}\}", "", text, flags=re.S)
    text = re.sub(r"\[\[([^|\]]*\|)?([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def parse_lyric_table(table_body: str) -> tuple[str, str, str, str] | None:
    headers: list[str] = []
    for line in table_body.splitlines():
        if not line.startswith("!"):
            if headers:
                break
            continue
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
    m = re.search(r"\|-\s*\n\|([\s\S]*)$", table_body)
    if not m:
        return None
    rest = m.group(1)
    parts = re.split(r"\n\|\n", rest, maxsplit=1)
    if len(parts) < 2:
        parts = re.split(r"\n\|(?=[^\|\-])", rest, maxsplit=1)
    if len(parts) < 2:
        return None
    c1 = _clean_cell(parts[0])
    c2 = _clean_cell(re.sub(r"\n\|\}[\s\S]*$", "", parts[1]))
    return h1, h2, c1, c2


def split_lyric_lines(text: str) -> list[str]:
    lines = []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln:
            lines.append(ln)
    return lines


def pair_cells(h1: str, h2: str, c1: str, c2: str) -> tuple[list[str], list[str]]:
    """Return (original_lines, simlish_lines) based on header order."""
    l1, l2 = split_lyric_lines(c1), split_lyric_lines(c2)
    if "SIMLISH" in h1.upper():
        return l2, l1
    return l1, l2
