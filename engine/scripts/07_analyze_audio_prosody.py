from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.config import ANALYSIS_AUDIO, ANALYSIS_REPORTS, ANALYSIS_TEXT, ensure_dirs
from engine.lib.textfeat import line_syllables


def prosody_for_file(align_path: Path) -> dict:
    data = json.loads(align_path.read_text(encoding="utf-8"))
    audio_path = data.get("audio_path")
    lines_out = []
    y = None
    sr = 16000
    if audio_path and Path(audio_path).exists():
        try:
            import librosa
            import numpy as np

            y, sr = librosa.load(audio_path, sr=16000, mono=True)
        except Exception as exc:  # noqa: BLE001
            print(f"librosa load fail {audio_path}: {exc}")
            y = None

    meter_scores = []
    for ln in data.get("lines") or []:
        start, end = ln.get("start"), ln.get("end")
        dur = None
        syll_rate = None
        f0_mean = None
        rms = None
        en_syl = line_syllables(ln.get("en_line") or "", simlish=False)
        sim_syl = line_syllables(ln.get("simlish_line") or "", simlish=True)
        if start is not None and end is not None and end > start:
            dur = float(end - start)
            syll_rate = sim_syl / dur if dur > 0 else None
            # meter: sung duration vs naive 0.2s * english syllables
            expected = max(0.15, en_syl * 0.22)
            meter_scores.append(1.0 - min(1.0, abs(dur - expected) / max(expected, 0.1)))
            if y is not None:
                import numpy as np
                import librosa

                i0 = int(start * sr)
                i1 = int(end * sr)
                seg = y[i0:i1]
                if len(seg) > 10:
                    rms = float(np.sqrt(np.mean(seg**2)))
                    try:
                        f0, _, _ = librosa.pyin(
                            seg, fmin=80, fmax=600, sr=sr, frame_length=1024
                        )
                        f0_clean = f0[~np.isnan(f0)] if f0 is not None else []
                        if len(f0_clean):
                            f0_mean = float(np.mean(f0_clean))
                    except Exception:  # noqa: BLE001
                        pass
        lines_out.append(
            {
                "line_index": ln.get("line_index"),
                "duration": dur,
                "en_syllables": en_syl,
                "sim_syllables": sim_syl,
                "syllable_rate": syll_rate,
                "rms": rms,
                "f0_mean": f0_mean,
            }
        )
    return {
        "song_id": data.get("song_id"),
        "align_quality": data.get("align_quality"),
        "mean_meter_score": float(sum(meter_scores) / len(meter_scores)) if meter_scores else None,
        "lines": lines_out,
    }


def main() -> None:
    ensure_dirs()
    results = []
    for fp in sorted(ANALYSIS_AUDIO.glob("*.alignment.json")):
        results.append(prosody_for_file(fp))
        print(f"prosody {fp.stem}")
    (ANALYSIS_TEXT / "prosody_summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with_audio = [r for r in results if r.get("mean_meter_score") is not None]
    md = [
        "# Audio findings ",
        "",
        f"- Alignments processed: **{len(results)}**",
        f"- With measurable meter: **{len(with_audio)}**",
        "",
        "## Notes",
        "",
        "- Alignments use lyrics-constrained Whisper prompting when audio exists; otherwise equal-time fallback (`align_quality=low`) or `none`.",
        "- Meter score compares Simlish line duration to a naive English syllable duration prior — high scores suggest sung Simlish preserves English timing.",
        "- F0/RMS are descriptive; rhyme evidence remains primarily orthographic from text analysis.",
        "",
        "## Per-song meter",
        "",
    ]
    for r in results:
        md.append(
            f"- `{r['song_id']}` quality={r.get('align_quality')} "
            f"meter={r.get('mean_meter_score')}"
        )
    (ANALYSIS_REPORTS / "audio_findings.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("wrote audio_findings.md")


if __name__ == "__main__":
    main()
