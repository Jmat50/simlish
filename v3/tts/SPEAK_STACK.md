# Speak stack decision (2026-08)

## Public GitHub Pages (shipped)

**Stock Kokoro** in the browser via [`docs/js/speak.js`](../../docs/js/speak.js) + improved Simlish IPA in [`docs/js/simlish-ipa.js`](../../docs/js/simlish-ipa.js).

- No EA audio or EA-derived weights
- First load ~90 MB ONNX from Hugging Face / jsDelivr
- Voice: `af_heart` (not marketed as Sims)

## Local research stack (winning smoke)

Smoke report: `data/manifests/smoke_voice_clone.json`

**Recommended:** `kokoro_ipa_plus_openvoice_tone_color`

1. Generate Simlish with stock Kokoro + IPA prompt
2. Tone-color convert with **OpenVoice v2** toward a curated Sims VO ref from `data/refs/`

A/B also produced **Chatterbox** zero-shot clones (`chatterbox_zero_shot`) — usable, but plan primary is OpenVoice because it preserves Kokoro’s IPA-driven Simlish content while only transferring timbre.

```bash
# one-time: Python 3.12 venv under v3/tts/.venv (already created on this machine)
.\v3\tts\.venv\Scripts\python.exe v3/tts/scripts/05_curate_refs.py
.\v3\tts\.venv\Scripts\python.exe v3/tts/scripts/06_smoke_voice_clone.py
.\v3\tts\.venv\Scripts\python.exe v3/tts/scripts/08_local_speak.py "Vous chika hip"
```

OpenVoice weights: `huggingface_hub.snapshot_download('myshell-ai/OpenVoiceV2', local_dir='v3/tts/tools/OpenVoice/checkpoints_v2')` (gitignored under `tools/`).

## Optional Kokoro fine-tune (cloud GPU)

GT 750M cannot train. Bundle ready:

- `data/kokoro_ft_bundle.zip` (200 clips, unlabeled text column)
- On a **12–24 GB** GPU + Python 3.12: label with wav2vec2 phoneme CTC, then [kokoro-recipe](https://github.com/Jeevav62/tts-finetune-recipes/tree/main/kokoro-recipe)

```bash
# cloud one-liner sketch
pip install torch transformers soundfile
# unzip kokoro_ft_bundle.zip, ASR-label train.csv, then follow kokoro-recipe Stage1/2
```

Never commit the zip, WAVs, or FT checkpoints.

## Why Pages does not ship OpenVoice/Chatterbox

- Python runtime + multi-hundred-MB models; not a drop-in for static Pages
- EA-timbre outputs must stay private
- Stock Kokoro + IPA already gives client-side Speak without IP risk
