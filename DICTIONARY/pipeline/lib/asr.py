from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pipeline.config import WHISPER_FALLBACK, WHISPER_MODEL


def _latin_only(text: str) -> str:
    # Keep letters, apostrophes, spaces, newlines
    text = re.sub(r"[^A-Za-zÀ-ÿ'’\s\n]+", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def transcribe_audio(path: Path, model_size: str | None = None) -> dict[str, Any]:
    """
    Transcribe with faster-whisper. Returns text + confidence estimate.
    Phonetic caveat: Whisper invents orthography for nonsense speech.
    """
    from faster_whisper import WhisperModel

    size = model_size or WHISPER_MODEL
    try:
        model = WhisperModel(size, device="cpu", compute_type="int8")
    except Exception:  # noqa: BLE001
        model = WhisperModel(WHISPER_FALLBACK, device="cpu", compute_type="int8")
        size = WHISPER_FALLBACK

    segments_out = []
    texts = []
    probs = []
    segments, info = model.transcribe(
        str(path),
        language=None,
        task="transcribe",
        vad_filter=True,
        word_timestamps=True,
    )
    for seg in segments:
        t = (seg.text or "").strip()
        if not t:
            continue
        texts.append(t)
        if seg.avg_logprob is not None:
            # map logprob (~-1..0) to 0..1 soft score
            probs.append(max(0.0, min(1.0, 1.0 + float(seg.avg_logprob))))
        words = []
        if seg.words:
            for w in seg.words:
                words.append(
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "probability": w.probability,
                    }
                )
        segments_out.append(
            {
                "start": seg.start,
                "end": seg.end,
                "text": t,
                "avg_logprob": seg.avg_logprob,
                "words": words,
            }
        )

    full = _latin_only("\n".join(texts))
    conf = sum(probs) / len(probs) if probs else 0.4
    # Penalize ASR for nonsense language
    conf = conf * 0.75
    return {
        "model": size,
        "language": getattr(info, "language", None),
        "text": full,
        "confidence": conf,
        "segments": segments_out,
        "needs_review": conf < 0.55 or len(full) < 40,
    }
