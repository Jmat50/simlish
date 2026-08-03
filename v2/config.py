from __future__ import annotations

from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent
REPO_ROOT = V2_ROOT.parent

CATALOG_DIR = V2_ROOT / "catalog"
LYRICS_DIR = V2_ROOT / "lyrics" / "official"
AUDIO_PHASE1 = V2_ROOT / "audio" / "phase1"
AUDIO_PHASE2 = V2_ROOT / "audio" / "phase2"
AUDIO_META = V2_ROOT / "audio" / "meta"
ANALYSIS_TEXT = V2_ROOT / "analysis" / "text"
ANALYSIS_AUDIO = V2_ROOT / "analysis" / "audio"
ANALYSIS_REPORTS = V2_ROOT / "analysis" / "reports"
MODELS_DIR = V2_ROOT / "models"
PHRASE_LM_DIR = MODELS_DIR / "phrase_lm"

# Bootstrap parallel lyrics from existing official exports if wiki fetch fails
BOOTSTRAP_LYRICS = REPO_ROOT / "DICTIONARY" / "data" / "lyrics" / "official"
BOOTSTRAP_CATALOG = REPO_ROOT / "DICTIONARY" / "data" / "catalog" / "songs.json"

WIKI_API = "https://sims.fandom.com/api.php"
WIKI_PAGE = "Songs_in_Simlish"
USER_AGENT = "SimlishV2Research/1.0 (+https://github.com/Jmat50/simlish; research)"

REQUEST_SLEEP_S = 0.4
YT_SEARCH_RESULTS = 10
YT_MIN_SCORE = 3
YT_COOKIES_FROM_BROWSER = "chrome"  # chrome|edge|firefox|none
YT_PLAYER_CLIENT = "android,web"

WHISPER_MODEL = "base"
AUDIO_SAMPLE_RATE = 16000

NN_RETRIEVAL_THRESHOLD = 0.82
SOUNDALIKE_ALIGN_THRESHOLD = 0.45

# Seed Phase-1 parallel song ids (wiki EN|SIMLISH tables)
PHASE1_SONG_IDS = [
    "katy-perry__hot-n-cold",
    "kisha__sowieso",
    "lily-allen__smile",
    "luke-bryan__country-girl-shake-it-for-me",
    "my-chemical-romance__na-na-na",
    "paramore__pressure",
    "the-young-punx-vs-the-camden-choral-collective__in-the-bleak-midwinter",
]


def ensure_dirs() -> None:
    for p in (
        CATALOG_DIR,
        LYRICS_DIR,
        AUDIO_PHASE1,
        AUDIO_PHASE2,
        AUDIO_META,
        ANALYSIS_TEXT,
        ANALYSIS_AUDIO,
        ANALYSIS_REPORTS,
        MODELS_DIR,
        PHRASE_LM_DIR,
    ):
        p.mkdir(parents=True, exist_ok=True)
