from __future__ import annotations

import time
from typing import Any

import requests

from pipeline.config import USER_AGENT, WIKI_API, WIKI_PAGE


def fetch_wikitext(page: str = WIKI_PAGE, retries: int = 4) -> dict[str, Any]:
    params = {
        "action": "parse",
        "page": page,
        "prop": "wikitext",
        "format": "json",
    }
    headers = {"User-Agent": USER_AGENT}
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(WIKI_API, params=params, headers=headers, timeout=60)
            r.raise_for_status()
            data = r.json()
            if "parse" not in data:
                raise RuntimeError(f"Unexpected API payload: {list(data)[:5]}")
            return data
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch wiki: {last_err}")
