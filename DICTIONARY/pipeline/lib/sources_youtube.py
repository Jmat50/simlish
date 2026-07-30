from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import REQUEST_SLEEP_S, USER_AGENT, YT_SEARCH_RESULTS


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_yt_dlp(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "yt_dlp", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def search_simlish_videos(artist: str, title: str, n: int = YT_SEARCH_RESULTS) -> list[dict[str, Any]]:
    query = f"ytsearch{n}:{artist} {title} simlish"
    proc = _run_yt_dlp(
        [
            "--flat-playlist",
            "--dump-json",
            "--no-download",
            query,
        ]
    )
    time.sleep(REQUEST_SLEEP_S)
    results = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return results


def score_video(meta: dict[str, Any], artist: str, title: str) -> float:
    t = (meta.get("title") or "").lower()
    ch = (meta.get("channel") or meta.get("uploader") or "").lower()
    dur = meta.get("duration") or 0
    score = 0.0
    if "simlish" in t:
        score += 5
    if "sims" in t:
        score += 2
    if any(x in t for x in ("sims 2", "sims 3", "sims 4", "the sims")):
        score += 2
    if artist.lower().split()[0] in t:
        score += 1
    if title.lower().split()[0] in t:
        score += 1
    if any(x in ch for x in ("ea", "electronic arts", "the sims", "lyric")):
        score += 1.5
    if isinstance(dur, (int, float)) and 90 <= dur <= 420:
        score += 1.5
    elif isinstance(dur, (int, float)) and dur > 600:
        score -= 2
    return score


def pick_best_video(artist: str, title: str) -> dict[str, Any] | None:
    results = search_simlish_videos(artist, title)
    if not results:
        return None
    ranked = sorted(results, key=lambda m: score_video(m, artist, title), reverse=True)
    best = ranked[0]
    if score_video(best, artist, title) < 3:
        # weak match — still return but mark low confidence later
        pass
    vid = best.get("id") or best.get("url")
    url = best.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else None)
    if not url:
        return None
    return {
        "video_id": best.get("id"),
        "url": url,
        "title": best.get("title"),
        "channel": best.get("channel") or best.get("uploader"),
        "duration": best.get("duration"),
        "score": score_video(best, artist, title),
        "retrieved_at": _now(),
    }


def extract_description_lyrics(description: str) -> str | None:
    if not description or len(description) < 80:
        return None
    # Heuristic: many short nonsense-looking tokens
    words = re.findall(r"[A-Za-z']+", description)
    if len(words) < 40:
        return None
    # Prefer block after "lyrics" heading
    lower = description.lower()
    idx = lower.find("lyrics")
    blob = description[idx:] if idx >= 0 else description
    lines = [ln.strip() for ln in blob.splitlines() if ln.strip()]
    # Drop URLs / social
    lines = [ln for ln in lines if not ln.startswith("http") and "http" not in ln.lower()]
    text = "\n".join(lines)
    if len(re.findall(r"[A-Za-z']+", text)) < 40:
        return None
    return text


def fetch_video_description(url: str) -> str:
    proc = _run_yt_dlp(["--skip-download", "--print", "%(description)s", url])
    time.sleep(REQUEST_SLEEP_S)
    return (proc.stdout or "").strip()


def download_audio(url: str, out_dir: Path, out_tmpl: str) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / out_tmpl
    common = [
        "-x",
        "--audio-format",
        "m4a",
        "--audio-quality",
        "0",
        "-o",
        str(dest),
        "--no-playlist",
        "--no-warnings",
    ]
    attempts = [
        common + ["--cookies-from-browser", "chrome", url],
        common + ["--cookies-from-browser", "edge", url],
        common + [url],
    ]
    for args in attempts:
        proc = _run_yt_dlp(args)
        time.sleep(REQUEST_SLEEP_S)
        matches = list(out_dir.glob(Path(out_tmpl).stem + ".*"))
        matches = [
            m
            for m in matches
            if m.suffix.lower() in {".m4a", ".webm", ".mp3", ".opus", ".wav"}
        ]
        if matches:
            return matches[0]
        err = (proc.stderr or "")[-300:]
        if "cookies" not in err.lower() and "bot" not in err.lower():
            # non-auth failure — don't keep retrying browsers forever
            break
    return None
