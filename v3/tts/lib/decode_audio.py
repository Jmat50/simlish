"""Decode Sims 3 SNR/SNS payloads to WAV via ffmpeg (XAS) or ealayer3."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from v3.tts.config import CODEC_EALAYER3, CODEC_XAS, TARGET_SR, TOOLS_DIR


class DecodeError(RuntimeError):
    pass


def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise DecodeError("ffmpeg not found on PATH")
    return exe


def find_ealayer3() -> Path:
    candidates = [
        TOOLS_DIR / "ealayer3-bin" / "ealayer3-0.6.2-win32" / "ealayer3.exe",
        TOOLS_DIR / "ealayer3.exe",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise DecodeError(
        "ealayer3.exe not found under v3/tts/tools — place the 0.6.2 win32 build there"
    )


def codec_of(payload: bytes) -> int:
    if not payload:
        raise DecodeError("empty payload")
    return payload[0]


def decode_snr_to_wav(payload: bytes, out_wav: Path, *, sample_rate: int = TARGET_SR) -> Path:
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    codec = codec_of(payload)
    with tempfile.TemporaryDirectory(prefix="simlish_snr_") as td:
        td_path = Path(td)
        snr_path = td_path / "clip.snr"
        snr_path.write_bytes(payload)
        raw_wav = td_path / "raw.wav"

        if codec == CODEC_XAS:
            ff = find_ffmpeg()
            cmd = [
                ff,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "ea_cdata",
                "-i",
                str(snr_path),
                str(raw_wav),
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0 or not raw_wav.exists():
                raise DecodeError(f"ffmpeg XAS failed: {r.stderr.strip()}")
        elif codec == CODEC_EALAYER3:
            eal = find_ealayer3()
            # must run with cwd = ealayer3 dir so libmpg123 loads
            cmd = [str(eal), "-mc", str(snr_path.name)]
            # copy next to exe
            work = eal.parent / "_work"
            work.mkdir(exist_ok=True)
            local = work / snr_path.name
            local.write_bytes(payload)
            r = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True)
            produced = work / "clip.wav"
            if r.returncode != 0 or not produced.exists():
                raise DecodeError(f"ealayer3 failed ({r.returncode}): {r.stderr or r.stdout}")
            shutil.move(str(produced), str(raw_wav))
            local.unlink(missing_ok=True)
        else:
            raise DecodeError(f"unknown codec byte 0x{codec:02x}")

        # resample / mono 24 kHz
        ff = find_ffmpeg()
        cmd = [
            ff,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(raw_wav),
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            str(out_wav),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not out_wav.exists():
            raise DecodeError(f"ffmpeg resample failed: {r.stderr.strip()}")
    return out_wav
