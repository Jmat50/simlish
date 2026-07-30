from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import DATA, ensure_dirs
from pipeline.lib.wiki import fetch_wikitext


def main() -> None:
    ensure_dirs()
    data = fetch_wikitext()
    raw_path = DATA / "catalog" / "Songs_in_Simlish.json"
    wt_path = DATA / "catalog" / "Songs_in_Simlish.wikitext"
    raw_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    wikitext = data["parse"]["wikitext"]["*"]
    wt_path.write_text(wikitext, encoding="utf-8")
    print(f"Wrote {raw_path} ({raw_path.stat().st_size} bytes)")
    print(f"Wrote {wt_path} ({len(wikitext)} chars)")


if __name__ == "__main__":
    main()
