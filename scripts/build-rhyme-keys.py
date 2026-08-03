"""Build docs/v2-models/rhyme_keys.json for the browser v2 converter."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pronouncing

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "docs" / "v2-models"


def rhyme_key(word: str) -> str:
    w = word.lower().strip("'")
    phones = pronouncing.phones_for_word(w)
    if phones:
        parts = phones[0].split()
        for i in range(len(parts) - 1, -1, -1):
            if re.search(r"\d", parts[i]):
                return " ".join(parts[i:])
        return parts[-1] if parts else (w[-3:] if len(w) >= 3 else w)
    return w[-3:] if len(w) >= 3 else w


def main() -> None:
    lex = json.loads((MODELS / "soundalike_rules.json").read_text(encoding="utf-8"))["lexicon"]
    fw = json.loads((MODELS / "function_words.json").read_text(encoding="utf-8"))
    mem = json.loads((MODELS / "phrase_memory.json").read_text(encoding="utf-8"))
    words: set[str] = set(lex) | set(fw)
    for row in mem:
        words.update(re.findall(r"[A-Za-z']+", row["original"].lower()))
    extras = """
        hello world love you me my we they she he it is are was were have has had
        do does did not no yes can could will would should may might must this that
        these those here there where when what who why how from with about into over
        under again never always forever tonight today tomorrow night day heart baby
        girl boy shake cold hot crazy beautiful dream dance sing song music party
        please thank thanks good morning afternoon evening friend friends family
        smile laugh cry happy sad alone together forever never stop start go come
        want need feel think know see look listen speak talk walk run jump play
        """.split()
    words.update(extras)
    index = {w: rhyme_key(w) for w in sorted(words) if w}
    out = MODELS / "rhyme_keys.json"
    out.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(index)} words, {out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
