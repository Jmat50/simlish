# Simlish v3 TTS — Sims 3 VO → Speak research

Local-only research pipeline. **Do not commit** extracted audio or fine-tuned weights.

## Install audio source

Default: `C:\Program Files (x86)\R.G. Catalyst\The Sims 3 Deluxe Edition\`  
Override with `SIMS3_ROOT`.

## Quick path (this machine)

```bash
# Phase 1 extract/decode (already run for ~4k clips)
python v3/tts/scripts/run_phase1_base.py --limit 4000

# Curate refs + FT subset
.\v3\tts\.venv\Scripts\python.exe v3/tts/scripts/05_curate_refs.py

# A/B smoke: Kokoro base + OpenVoice tone-color + Chatterbox
.\v3\tts\.venv\Scripts\python.exe v3/tts/scripts/06_smoke_voice_clone.py

# Local Speak (winning stack)
.\v3\tts\.venv\Scripts\python.exe v3/tts/scripts/08_local_speak.py "Hilla, sho!"
```

See [SPEAK_STACK.md](SPEAK_STACK.md) for the Pages vs local decision.
See [TRAINING.md](TRAINING.md) for optional cloud Kokoro FT.

## Tools

- `ffmpeg` on PATH
- `v3/tts/tools/ealayer3-bin/...` for EALayer3
- OpenVoiceV2 checkpoints under `tools/OpenVoice/checkpoints_v2/` (HF: `myshell-ai/OpenVoiceV2`)
