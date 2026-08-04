"""
Offline smoke: generate Simlish with stock Kokoro (Python), then
A/B tone-clone with OpenVoice v2 and/or Chatterbox using curated Sims refs.

Outputs under data/smoke/ (gitignored). Designed to degrade gracefully when
GPU/VRAM or packages are missing — writes a report either way.

Usage (repo root, preferably Python 3.10–3.12 venv):
  pip install kokoro soundfile numpy
  # OpenVoice extras — see script comments
  python v3/tts/scripts/06_smoke_voice_clone.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from v3.tts.config import DATA_DIR, MANIFEST_DIR, TOOLS_DIR, ensure_dirs  # noqa: E402

REFS_DIR = DATA_DIR / "refs"
SMOKE_DIR = DATA_DIR / "smoke"

# Sample Simlish lines (orthography → coarse IPA for Kokoro manual phonemes)
SAMPLES = [
    ("hilla_sho", "Hilla, sho!"),
    ("vous_chika", "Vous chika hip"),
    ("sheeky_dit", "Sheeky dit oxf"),
]


def simlish_to_kokoro_phonemes(text: str) -> str:
    """Minimal mirror of docs/js/simlish-ipa.js for offline Python smoke."""
    simp = [
        ("ch", "tʃ"), ("sh", "ʃ"), ("th", "θ"), ("ph", "f"), ("qu", "kw"),
        ("ng", "ŋ"), ("ck", "k"), ("oo", "u"), ("ee", "i"), ("ou", "aʊ"),
        ("ai", "eɪ"), ("ay", "eɪ"), ("oi", "ɔɪ"), ("oy", "ɔɪ"),
    ]
    vowel = {"a": "ɑ", "e": "ɛ", "i": "ɪ", "o": "o", "u": "ʊ", "y": "i"}

    def word_ipa(word: str) -> str:
        w = "".join(c for c in word.lower() if c.isalpha() or c == "'")
        phones: list[str] = []
        i = 0
        while i < len(w):
            matched = False
            for pat, ipa in simp:
                if w.startswith(pat, i):
                    phones.append(ipa)
                    i += len(pat)
                    matched = True
                    break
            if matched:
                continue
            ch = w[i]
            i += 1
            if ch == "'":
                continue
            phones.append(vowel.get(ch, ch))
        return "".join(phones)

    import re

    def repl(m: re.Match[str]) -> str:
        tok = m.group(0)
        ipa = word_ipa(tok)
        return f"[{tok}](/{ipa}/)" if ipa else tok

    return re.sub(r"[A-Za-z']+", repl, text)


def generate_kokoro(out_wav: Path, text: str, voice: str = "af_heart") -> dict:
    try:
        from kokoro import KPipeline
        import soundfile as sf
        import numpy as np
    except Exception as exc:
        return {"ok": False, "error": f"kokoro import failed: {exc}"}

    try:
        pipe = KPipeline(lang_code="a")
        prompt = simlish_to_kokoro_phonemes(text)
        chunks = []
        for _, _, audio in pipe(prompt, voice=voice):
            chunks.append(audio)
        if not chunks:
            return {"ok": False, "error": "kokoro produced no audio"}
        audio = chunks[0] if len(chunks) == 1 else __import__("numpy").concatenate(chunks)
        sf.write(str(out_wav), audio, 24000)
        return {"ok": True, "path": str(out_wav), "prompt": prompt, "voice": voice}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "trace": traceback.format_exc()[-800:]}


def try_openvoice(src_wav: Path, ref_wav: Path, out_wav: Path) -> dict:
    """Tone-color convert src toward ref using OpenVoice v2 if available."""
    ckpt = TOOLS_DIR / "OpenVoice" / "checkpoints_v2" / "converter"
    if not (ckpt / "config.json").exists():
        # HF snapshot layout
        alt = TOOLS_DIR / "OpenVoice" / "checkpoints_v2"
        if (alt / "converter" / "config.json").exists():
            ckpt = alt / "converter"
    if not (ckpt / "config.json").exists():
        return {
            "ok": False,
            "error": (
                "OpenVoice checkpoints_v2/converter missing. "
                "Run: python -c \"from huggingface_hub import snapshot_download; "
                "snapshot_download('myshell-ai/OpenVoiceV2', local_dir='v3/tts/tools/OpenVoice/checkpoints_v2')\""
            ),
        }

    try:
        # ensure local package importable without pip -e
        ov_root = str(TOOLS_DIR / "OpenVoice")
        if ov_root not in sys.path:
            sys.path.insert(0, ov_root)
        import torch
        from openvoice.api import ToneColorConverter
    except Exception as exc:
        return {"ok": False, "error": f"openvoice import failed: {exc}"}

    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        conv = ToneColorConverter(str(ckpt / "config.json"), device=device)
        conv.load_ckpt(str(ckpt / "checkpoint.pth"))
        # Bypass se_extractor Whisper/VAD path — extract SE from whole clips.
        tgt_se = conv.extract_se([str(ref_wav)], se_save_path=str(SMOKE_DIR / "se" / "tgt_se.pth"))
        src_se_path = TOOLS_DIR / "OpenVoice" / "checkpoints_v2" / "base_speakers" / "ses" / "en-default.pth"
        if src_se_path.exists():
            src_se = torch.load(str(src_se_path), map_location=device)
        else:
            src_se = conv.extract_se([str(src_wav)], se_save_path=str(SMOKE_DIR / "se" / "src_se.pth"))
        conv.convert(
            audio_src_path=str(src_wav),
            src_se=src_se,
            tgt_se=tgt_se,
            output_path=str(out_wav),
            message="@simlish-research",
        )
        return {"ok": True, "path": str(out_wav), "device": device, "ref": str(ref_wav)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "trace": traceback.format_exc()[-1200:]}


def try_chatterbox(text: str, ref_wav: Path, out_wav: Path) -> dict:
    try:
        import torch
        from chatterbox.tts import ChatterboxTTS
    except Exception as exc:
        # try turbo
        try:
            from chatterbox.tts import ChatterboxTurboTTS as ChatterboxTTS  # type: ignore
            import torch
        except Exception as exc2:
            return {"ok": False, "error": f"chatterbox not installed: {exc} / {exc2}"}

    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # phonetic-ish: feed plain Simlish orthography
        model = ChatterboxTTS.from_pretrained(device=device)
        wav = model.generate(text, audio_prompt_path=str(ref_wav))
        import torchaudio

        torchaudio.save(str(out_wav), wav.unsqueeze(0) if wav.dim() == 1 else wav, model.sr)
        return {"ok": True, "path": str(out_wav), "device": device, "ref": str(ref_wav)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "trace": traceback.format_exc()[-1200:]}


def pick_ref() -> Path | None:
    refs = sorted(REFS_DIR.glob("ref_*.wav"))
    return refs[0] if refs else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-openvoice", action="store_true")
    ap.add_argument("--skip-chatterbox", action="store_true")
    ap.add_argument("--skip-kokoro", action="store_true")
    args = ap.parse_args()
    ensure_dirs()
    SMOKE_DIR.mkdir(parents=True, exist_ok=True)

    ref = pick_ref()
    report: dict = {
        "ref": str(ref) if ref else None,
        "samples": [],
        "notes": [],
    }
    if not ref:
        report["notes"].append("No refs — run 05_curate_refs.py first")
        (MANIFEST_DIR / "smoke_voice_clone.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    for key, text in SAMPLES:
        sample_dir = SMOKE_DIR / key
        sample_dir.mkdir(parents=True, exist_ok=True)
        entry: dict = {"id": key, "text": text}
        base = sample_dir / "01_kokoro_base.wav"

        if args.skip_kokoro and base.exists():
            entry["kokoro"] = {"ok": True, "path": str(base), "skipped_regen": True}
        elif args.skip_kokoro:
            entry["kokoro"] = {"ok": False, "error": "skipped and missing"}
        else:
            entry["kokoro"] = generate_kokoro(base, text)

        ov_path = sample_dir / "02_openvoice.wav"
        if entry["kokoro"].get("ok") and not args.skip_openvoice:
            entry["openvoice"] = try_openvoice(base, ref, ov_path)
        elif ov_path.exists():
            entry["openvoice"] = {"ok": True, "path": str(ov_path), "skipped_regen": True}
        else:
            entry["openvoice"] = {"ok": False, "error": "skipped or no kokoro base"}

        cb_path = sample_dir / "03_chatterbox.wav"
        if not args.skip_chatterbox:
            entry["chatterbox"] = try_chatterbox(text, ref, cb_path)
        elif cb_path.exists():
            entry["chatterbox"] = {"ok": True, "path": str(cb_path), "skipped_regen": True}
        else:
            entry["chatterbox"] = {"ok": False, "error": "skipped"}

        report["samples"].append(entry)
        print(f"[{key}] kokoro={entry['kokoro'].get('ok')} ov={entry['openvoice'].get('ok')} cb={entry['chatterbox'].get('ok')}", flush=True)

    # winner heuristic for speak-decision docs
    ov_ok = any(s.get("openvoice", {}).get("ok") for s in report["samples"])
    cb_ok = any(s.get("chatterbox", {}).get("ok") for s in report["samples"])
    kk_ok = any(s.get("kokoro", {}).get("ok") for s in report["samples"])
    if ov_ok:
        report["recommended_local_stack"] = "kokoro_ipa_plus_openvoice_tone_color"
    elif cb_ok:
        report["recommended_local_stack"] = "chatterbox_zero_shot"
    elif kk_ok:
        report["recommended_local_stack"] = "stock_kokoro_ipa_only"
    else:
        report["recommended_local_stack"] = "stock_kokoro_browser_only"
        report["notes"].append(
            "Local Python smoke could not run clone models on this machine; "
            "Pages Speak stays stock Kokoro. Use Colab/cloud for OpenVoice/Chatterbox."
        )

    out = MANIFEST_DIR / "smoke_voice_clone.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"report {out}")
    print(f"recommended={report['recommended_local_stack']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
