from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python -m engine.cli` from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from engine.convert.pipeline import SimlishConverter


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="English→Simlish converter")
    ap.add_argument("text", nargs="?", help="English text to convert")
    ap.add_argument("-f", "--file", type=Path, help="Read English text from file")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args(argv)
    if args.file:
        text = args.file.read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read()
    conv = SimlishConverter()
    out = conv.convert_text(text)
    print(out)
    if args.debug:
        for line in text.splitlines():
            if line.strip():
                print(f"# {line} -> {conv.convert_line(line)}", file=sys.stderr)


if __name__ == "__main__":
    main()
