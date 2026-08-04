# Kokoro fine-tune (cloud only — not GT 750M)

This machine's NVIDIA GT 750M (2 GB) cannot fine-tune Kokoro-82M.
Use **Python 3.12** (`v3/tts/.venv`) — misaki/kokoro require `<3.13`.

## Local prep (done / repeatable)

```bash
py -3.12 -m venv v3/tts/.venv
.\v3\tts\.venv\Scripts\python.exe -m pip install kokoro "misaki[en]" soundfile torch --index-url https://download.pytorch.org/whl/cpu
# then other deps from pypi as needed

python v3/tts/scripts/05_curate_refs.py          # refs + ft_subset
python v3/tts/scripts/07_package_kokoro_bundle.py  # -> data/kokoro_ft_bundle.zip
```

## Cloud GPU (12–24 GB)

1. Upload `data/kokoro_ft_bundle.zip` (private).
2. If `train.csv` `text` is empty, label with `facebook/wav2vec2-lv-60-espeak-cv-ft`.
   - Needs **eSpeak NG** on the host (`PHONEMIZER_ESPEAK_LIBRARY` on Windows pointing at `libespeak-ng.dll`).
   - Local smoke: `04_auto_ipa.py --limit 10 --require-asr` and `07_package_kokoro_bundle.py --label --limit 20` both work under Python 3.12 once eSpeak is installed.
3. Clone https://github.com/Jeevav62/tts-finetune-recipes → `kokoro-recipe`.
4. Stage 1 + Stage 2: `batch_size: 1`, `joint_epoch: 99` on 12–16 GB.
5. Export ONNX + voicepack into **gitignored** `v3/tts/checkpoints/`.

Colab / HF Jobs sketch:

```bash
# cloud one-liner sketch (after unzipping kokoro_ft_bundle.zip)
pip install torch transformers soundfile phonemizer
# apt-get install -y espeak-ng   # Linux
python - <<'PY'
# run phoneme ASR into train.csv text column, then follow kokoro-recipe Stage1/2
print("label then train")
PY
```

## Prefer OpenVoice for Sims timbre

See [SPEAK_STACK.md](SPEAK_STACK.md). Kokoro FT is optional for a pure-browser custom voice; OpenVoice + stock Kokoro IPA is the better unlabeled-VO path.

## Do not

- Commit WAVs, SNR, FT weights, or `kokoro_ft_bundle.zip` to the public repo
- Publish EA-derived voice models to GitHub Pages / public HF
