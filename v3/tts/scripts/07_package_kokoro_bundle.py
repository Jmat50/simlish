"""
Build a cloud-ready Kokoro FT zip from ft_subset (+ optional IPA labels).

Layout (kokoro-recipe compatible):
  bundle/wavs/*.wav
  bundle/train.csv   — id,target_audio,text

If auto-IPA is unavailable, writes empty text column and a README telling
the cloud box to run phoneme ASR before training.

Usage (repo root, Python 3.12 recommended):
  python v3/tts/scripts/07_package_kokoro_bundle.py
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from v3.tts.config import DATA_DIR, MANIFEST_DIR, ensure_dirs  # noqa: E402

FT_DIR = DATA_DIR / "ft_subset"
BUNDLE_DIR = DATA_DIR / "kokoro_bundle"
WAVS_DIR = BUNDLE_DIR / "wavs"


def try_label(wav: Path) -> str:
    """Best-effort phoneme ASR; returns '' if torch/transformers unavailable."""
    try:
        import numpy as np
        import soundfile as sf
        import torch
        from transformers import AutoModelForCTC, AutoProcessor
    except Exception:
        return ""

    global _ASR
    if _ASR is None:
        name = "facebook/wav2vec2-lv-60-espeak-cv-ft"
        processor = AutoProcessor.from_pretrained(name)
        model = AutoModelForCTC.from_pretrained(name)
        model.eval()
        _ASR = (processor, model)
    processor, model = _ASR
    audio, sr = sf.read(str(wav))
    if getattr(audio, "ndim", 1) > 1:
        audio = audio.mean(axis=1)
    if sr != 16000:
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
    ap.add_argument("--limit", type=int, default=0, help="Max clips (0=all in ft_subset)")
    ap.add_argument("--label", action="store_true", help="Run phoneme ASR labeling")
    ap.add_argument("--zip", action="store_true", default=True)
    args = ap.parse_args()
    ensure_dirs()

    if not FT_DIR.exists() or not list(FT_DIR.glob("*.wav")):
        print("ft_subset empty — run 05_curate_refs.py first", file=sys.stderr)
        return 1

    if BUNDLE_DIR.exists():
        shutil.rmtree(BUNDLE_DIR)
    WAVS_DIR.mkdir(parents=True)

    files = sorted(FT_DIR.glob("*.wav"))
    if args.limit:
        files = files[: args.limit]

    rows = []
    labeled = 0
    for wav in files:
        dest_name = wav.name
        shutil.copy2(wav, WAVS_DIR / dest_name)
        text = try_label(wav) if args.label else ""
        if text:
            labeled += 1
        rows.append({"id": wav.stem, "target_audio": dest_name, "text": text})

    csv_path = BUNDLE_DIR / "train.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "target_audio", "text"])
        w.writeheader()
        w.writerows(rows)

    readme = BUNDLE_DIR / "README_CLOUD.txt"
    readme.write_text(
        "\n".join(
            [
                "Kokoro FT cloud bundle (private — do not publish)",
                "",
                "1. Use Python 3.12 on a 12–24 GB GPU box.",
                "2. Clone https://github.com/Jeevav62/tts-finetune-recipes",
                "3. Copy wavs/ + train.csv into kokoro-recipe/data/ per its README.",
                "4. If train.csv text column is empty, run phoneme ASR on the GPU box:",
                "     facebook/wav2vec2-lv-60-espeak-cv-ft",
                "5. Stage1 + Stage2 with batch_size=1, joint_epoch=99 on 12–16 GB.",
                "6. Export ONNX + voicepack to this repo's v3/tts/checkpoints/ (gitignored).",
                "7. Never commit EA audio or FT weights to the public GitHub repo.",
                "",
                f"Clips: {len(rows)}  Labeled here: {labeled}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    zip_path = DATA_DIR / "kokoro_ft_bundle.zip"
    if args.zip:
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in BUNDLE_DIR.rglob("*"):
                if p.is_file():
                    zf.write(p, arcname=str(p.relative_to(BUNDLE_DIR)))

    report = {
        "clips": len(rows),
        "labeled": labeled,
        "bundle_dir": str(BUNDLE_DIR),
        "zip": str(zip_path) if args.zip else None,
        "python_note": "Train with Python 3.12 (misaki/kokoro require <3.13)",
    }
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    (MANIFEST_DIR / "kokoro_bundle.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
