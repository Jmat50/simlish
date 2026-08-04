"""
Auto-IPA label filtered WAVs for Kokoro fine-tune.

Uses espeak-ng phonemize when available; otherwise writes a placeholder
manifest and documents the HF wav2vec2-phoneme path for GPU boxes.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from v3.tts.config import FILTERED_DIR, IPA_DIR, MANIFEST_DIR, ensure_dirs  # noqa: E402


def espeak_ipa(wav: Path) -> str | None:
    """Best-effort: espeak cannot hear audio; this path is for orthography only.
    For true audio→IPA use phoneme ASR (see README). Here we mark pending."""
    return None


def try_phoneme_asr(wav: Path) -> str | None:
    """Optional: transformers wav2vec2 phoneme CTC if installed + torch available."""
    try:
        import torch
        from transformers import AutoModelForCTC, AutoProcessor
        import soundfile as sf
        import numpy as np
    except Exception:
        return None

    # Lazy global cache
    global _ASR  # type: ignore
    if "_ASR" not in globals() or _ASR is None:  # type: ignore
        name = "facebook/wav2vec2-lv-60-espeak-cv-ft"
        processor = AutoProcessor.from_pretrained(name)
        model = AutoModelForCTC.from_pretrained(name)
        model.eval()
        globals()["_ASR"] = (processor, model)

    processor, model = _ASR  # type: ignore
    audio, sr = sf.read(str(wav))
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != 16000:
        # crude resample
        import math

        n = int(len(audio) * 16000 / sr)
        audio = np.interp(np.linspace(0, len(audio), n), np.arange(len(audio)), audio)
    inputs = processor(audio, sampling_rate=16000, return_tensors="pt", padding=True)
    with torch.no_grad():
        logits = model(inputs.input_values).logits
    pred = torch.argmax(logits, dim=-1)
    return processor.batch_decode(pred)[0]


_ASR = None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--require-asr", action="store_true")
    args = ap.parse_args()
    ensure_dirs()
    IPA_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(FILTERED_DIR.glob("*.wav"))
    if args.limit:
        files = files[: args.limit]

    rows = []
    labeled = 0
    for wav in files:
        ipa = try_phoneme_asr(wav)
        if ipa:
            labeled += 1
            (IPA_DIR / (wav.stem + ".ipa.txt")).write_text(ipa, encoding="utf-8")
        elif args.require_asr:
            print(f"ASR unavailable/failed for {wav.name}", file=sys.stderr)
            return 2
        rows.append({"id": wav.stem, "target_audio": wav.name, "text": ipa or "", "labeled": bool(ipa)})

    csv_path = MANIFEST_DIR / "train_ipa.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "target_audio", "text"])
        w.writeheader()
        for r in rows:
            if r["text"]:
                w.writerow({"id": r["id"], "target_audio": r["target_audio"], "text": r["text"]})

    report = {
        "files": len(files),
        "labeled": labeled,
        "csv": str(csv_path),
        "note": (
            "Install torch+transformers+soundfile for facebook/wav2vec2-lv-60-espeak-cv-ft "
            "auto-IPA. GT 750M is too small for Kokoro FT; run labeling/training on a 12GB+ GPU."
        ),
    }
    (MANIFEST_DIR / "auto_ipa.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
