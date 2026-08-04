from __future__ import annotations

from pathlib import Path

TTS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TTS_ROOT.parents[1]

# Personal Sims 3 Deluxe install (override with SIMS3_ROOT env)
DEFAULT_SIMS3_ROOT = Path(
    r"C:\Program Files (x86)\R.G. Catalyst\The Sims 3 Deluxe Edition"
)

DATA_DIR = TTS_ROOT / "data"
SNR_DIR = DATA_DIR / "snr"
WAV_DIR = DATA_DIR / "wav"
FILTERED_DIR = DATA_DIR / "wav_filtered"
IPA_DIR = DATA_DIR / "ipa"
MANIFEST_DIR = DATA_DIR / "manifests"
CHECKPOINTS_DIR = TTS_ROOT / "checkpoints"
TOOLS_DIR = TTS_ROOT / "tools"

TYPE_SNR = 0x01A527DB  # voice / aud
TYPE_SNS = 0x01EEF63A  # music / fx
TYPE_NMAP = 0x0166038C

CODEC_XAS = 0x04
CODEC_EALAYER3 = 0x05

# Speech clip duration gate (seconds) after decode
MIN_DURATION_S = 0.45
MAX_DURATION_S = 12.0

TARGET_SR = 24000

# First-pass training subset size (full bank is ~49k base / ~161k all packs)
DEFAULT_EXTRACT_LIMIT = 4000


def ensure_dirs() -> None:
    for p in (SNR_DIR, WAV_DIR, FILTERED_DIR, IPA_DIR, MANIFEST_DIR, CHECKPOINTS_DIR, TOOLS_DIR):
        p.mkdir(parents=True, exist_ok=True)
