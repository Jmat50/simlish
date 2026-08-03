from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from v2.config import ANALYSIS_AUDIO, AUDIO_META, AUDIO_PHASE1, LYRICS_DIR, WHISPER_MODEL, ensure_dirs


def energy_fallback_alignment(wav: Path, pairs: list[dict]) -> dict:
    """Low-quality equal-time slices when Whisper unavailable."""
    try:
        import librosa
        import numpy as np

        y, sr = librosa.load(str(wav), sr=16000, mono=True)
        dur = float(len(y) / sr)
    except Exception:  # noqa: BLE001
        dur = max(30.0, len(pairs) * 2.5)
    n = max(1, len(pairs))
    slice_len = dur / n
    aligned = []
    for i, pair in enumerate(pairs):
        aligned.append(
            {
                "line_index": pair.get("line_index", i),
                "start": round(i * slice_len, 3),
                "end": round((i + 1) * slice_len, 3),
                "simlish_line": pair["simlish"],
                "en_line": pair["original"],
            }
        )
    return {"align_quality": "low", "method": "equal_time", "duration": dur, "lines": aligned}


def whisper_prompt_alignment(wav: Path, pairs: list[dict]) -> dict | None:
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:  # noqa: BLE001
        print(f"faster-whisper unavailable: {exc}")
        return None
    prompt = " ".join(p["simlish"] for p in pairs)[:800]
    try:
        model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        segments, info = model.transcribe(
            str(wav),
            language=None,
            task="transcribe",
            initial_prompt=prompt,
            word_timestamps=False,
            vad_filter=True,
        )
        segs = list(segments)
    except Exception as exc:  # noqa: BLE001
        print(f"whisper failed: {exc}")
        return None
    if not segs:
        return None
    # Map lyric lines to segments by order / duration proportion
    total = segs[-1].end if segs else 1.0
    aligned = []
    n = len(pairs)
    for i, pair in enumerate(pairs):
        # pick segment by fractional position
        t0 = total * i / n
        t1 = total * (i + 1) / n
        # nearest segment mid
        best = min(segs, key=lambda s: abs(((s.start + s.end) / 2) - (t0 + t1) / 2))
        aligned.append(
            {
                "line_index": pair.get("line_index", i),
                "start": round(float(best.start), 3),
                "end": round(float(best.end), 3),
                "simlish_line": pair["simlish"],
                "en_line": pair["original"],
                "asr_text": (best.text or "").strip(),
            }
        )
    return {
        "align_quality": "medium",
        "method": "whisper_prompt_order",
        "duration": float(total),
        "language": getattr(info, "language", None),
        "lines": aligned,
    }


def main() -> None:
    ensure_dirs()
    for fp in sorted(LYRICS_DIR.glob("*.json")):
        doc = json.loads(fp.read_text(encoding="utf-8"))
        sid = doc["song_id"]
        wav = AUDIO_PHASE1 / f"{sid}.wav"
        if not wav.exists():
            # any audio ext
            cands = list(AUDIO_PHASE1.glob(f"{sid}.*"))
            cands = [c for c in cands if c.suffix.lower() in {".wav", ".mp3", ".m4a", ".webm"}]
            wav = cands[0] if cands else None
        out = ANALYSIS_AUDIO / f"{sid}.alignment.json"
        if wav is None:
            payload = {
                "song_id": sid,
                "align_quality": "none",
                "method": "no_audio",
                "lines": [
                    {
                        "line_index": p.get("line_index"),
                        "start": None,
                        "end": None,
                        "simlish_line": p["simlish"],
                        "en_line": p["original"],
                    }
                    for p in doc.get("pairs") or []
                ],
            }
        else:
            payload = whisper_prompt_alignment(wav, doc.get("pairs") or [])
            if payload is None:
                payload = energy_fallback_alignment(wav, doc.get("pairs") or [])
            payload["song_id"] = sid
            payload["audio_path"] = str(wav)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"aligned {sid} quality={payload.get('align_quality')}")


if __name__ == "__main__":
    main()
