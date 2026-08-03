from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from v2.config import (
    AUDIO_SAMPLE_RATE,
    USER_AGENT,
    YT_COOKIES_FROM_BROWSER,
    YT_MIN_SCORE,
    YT_PLAYER_CLIENT,
    YT_SEARCH_RESULTS,
)


def search_videos(query: str, n: int = YT_SEARCH_RESULTS) -> list[dict[str, Any]]:
    def run(with_cookies: bool) -> tuple[list[dict[str, Any]], str]:
        cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--ignore-errors"]
        if with_cookies and YT_COOKIES_FROM_BROWSER and YT_COOKIES_FROM_BROWSER.lower() != "none":
            cmd += ["--cookies-from-browser", YT_COOKIES_FROM_BROWSER]
        if YT_PLAYER_CLIENT:
            cmd += ["--extractor-args", f"youtube:player_client={YT_PLAYER_CLIENT}"]
        cmd += [
            f"ytsearch{n}:{query}",
            "--dump-json",
            "--flat-playlist",
            "--skip-download",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except Exception as exc:  # noqa: BLE001
            return [], str(exc)
        out = []
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        err = (proc.stderr or "")[-800:]
        return out, err

    out, err = run(True)
    if not out:
        out, err2 = run(False)
        err = err or err2
    if not out:
        return [{"error": err or "no results", "query": query}]
    return out


def _yt_dlp_base(with_cookies: bool = True) -> list[str]:
    cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--ignore-errors"]
    if (
        with_cookies
        and YT_COOKIES_FROM_BROWSER
        and YT_COOKIES_FROM_BROWSER.lower() != "none"
    ):
        cmd += ["--cookies-from-browser", YT_COOKIES_FROM_BROWSER]
    if YT_PLAYER_CLIENT:
        cmd += ["--extractor-args", f"youtube:player_client={YT_PLAYER_CLIENT}"]
    return cmd


def score_candidate(meta: dict[str, Any], artist: str, title: str) -> int:
    if meta.get("error"):
        return -100
    t = f"{meta.get('title') or ''} {meta.get('description') or ''}".lower()
    ch = f"{meta.get('channel') or meta.get('uploader') or ''}".lower()
    score = 0
    if "simlish" in t or "simlish" in ch:
        score += 5
    for kw in ("sims", "soundtrack", "official", "sims 2", "sims 3", "sims 4", "the sims"):
        if kw in t or kw in ch:
            score += 2
    # title/artist hints
    for token in re.findall(r"[a-z0-9]+", title.lower()):
        if len(token) > 3 and token in t:
            score += 1
    for token in re.findall(r"[a-z0-9]+", artist.lower()):
        if len(token) > 3 and token in t:
            score += 1
    dur = meta.get("duration") or meta.get("duration_string")
    try:
        dur_s = int(dur) if dur is not None else 0
    except (TypeError, ValueError):
        dur_s = 0
    if dur_s and dur_s < 60:
        score -= 4
    if dur_s and dur_s >= 90:
        score += 1
    for bad in ("fan made", "nightcore", "karaoke", "cover by", "reaction"):
        if bad in t:
            score -= 3
    # Prefer explicit simlish; without it, require sims soundtrack cues
    if "simlish" not in t and "simlish" not in ch:
        if not any(k in t or k in ch for k in ("sims", "soundtrack")):
            score -= 5
    return score


def pick_best(artist: str, title: str) -> dict[str, Any] | None:
    queries = [
        f"{artist} {title} simlish",
        f"The Sims {title} simlish",
        f"{title} simlish soundtrack",
    ]
    best = None
    best_score = YT_MIN_SCORE - 1
    rejected: list[dict[str, Any]] = []
    all_tried = []
    for q in queries:
        results = search_videos(q)
        for meta in results:
            if meta.get("error"):
                rejected.append(meta)
                continue
            sc = score_candidate(meta, artist, title)
            vid = meta.get("id") or meta.get("url")
            entry = {
                "id": vid,
                "title": meta.get("title"),
                "channel": meta.get("channel") or meta.get("uploader"),
                "duration": meta.get("duration"),
                "score": sc,
                "query": q,
                "url": meta.get("url")
                or (f"https://www.youtube.com/watch?v={vid}" if vid else None),
            }
            all_tried.append(entry)
            if sc > best_score and entry.get("url"):
                best_score = sc
                best = entry
            elif sc < YT_MIN_SCORE:
                rejected.append(entry)
    if not best:
        return {
            "ok": False,
            "skip_reason": "no_simlish_youtube",
            "rejected": rejected[:20],
            "tried": all_tried[:30],
        }
    return {
        "ok": True,
        "chosen": best,
        "rejected": [r for r in all_tried if r is not best][:20],
    }


def download_audio(url: str, out_dir: Path, stem: str) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / f"{stem}.wav"
    if wav.exists() and wav.stat().st_size > 1000:
        return wav
    tmpl = str(out_dir / f"{stem}.%(ext)s")
    cmd = _yt_dlp_base(True) + [
        "-x",
        "--audio-format",
        "wav",
        "--audio-quality",
        "0",
        "-o",
        tmpl,
        "--postprocessor-args",
        f"ffmpeg:-ac 1 -ar {AUDIO_SAMPLE_RATE}",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if not (wav.exists() and wav.stat().st_size > 1000):
        cmd = _yt_dlp_base(False) + [
            "-x",
            "--audio-format",
            "wav",
            "--audio-quality",
            "0",
            "-o",
            tmpl,
            "--postprocessor-args",
            f"ffmpeg:-ac 1 -ar {AUDIO_SAMPLE_RATE}",
            url,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if wav.exists() and wav.stat().st_size > 1000:
        return wav
    # maybe different ext then convert
    for p in out_dir.glob(f"{stem}.*"):
        if p.suffix.lower() in {".wav", ".mp3", ".m4a", ".webm", ".opus", ".ogg"}:
            if p.suffix.lower() == ".wav":
                return p
            # ffmpeg convert
            conv = [
                "ffmpeg",
                "-y",
                "-i",
                str(p),
                "-ac",
                "1",
                "-ar",
                str(AUDIO_SAMPLE_RATE),
                str(wav),
            ]
            subprocess.run(conv, capture_output=True, text=True, timeout=300)
            if wav.exists():
                return wav
    err = (proc.stderr or proc.stdout or "")[-800:]
    (out_dir / f"{stem}.download_error.txt").write_text(err, encoding="utf-8")
    return None
