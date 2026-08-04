from __future__ import annotations

"""Validate models exist and smoke-convert a few lines; write converter manifest."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.config import MODELS_DIR, ANALYSIS_REPORTS, ensure_dirs
from engine.convert.pipeline import SimlishConverter


REQUIRED = [
    "soundalike_rules.json",
    "rhyme_classes.json",
    "syllable_templates.json",
    "phrase_memory.json",
]


def main() -> None:
    ensure_dirs()
    missing = [r for r in REQUIRED if not (MODELS_DIR / r).exists()]
    if missing:
        raise SystemExit(f"Missing models: {missing}; run 08_induce_rules_and_stats.py first")
    conv = SimlishConverter()
    samples = [
        "You're yes then you're no",
        "I can feel the pressure",
        "Always speak cryptically",
        "Hello world",
    ]
    results = [{"en": s, "simlish": conv.convert_line(s)} for s in samples]
    manifest = {
        "models": REQUIRED,
        "smoke": results,
    }
    (MODELS_DIR / "converter_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ANALYSIS_REPORTS / "converter_smoke.md").write_text(
        "# Converter smoke\n\n"
        + "\n".join(f"- `{r['en']}` → `{r['simlish']}`" for r in results)
        + "\n",
        encoding="utf-8",
    )
    for r in results:
        print(f"{r['en']}  =>  {r['simlish']}")


if __name__ == "__main__":
    main()
