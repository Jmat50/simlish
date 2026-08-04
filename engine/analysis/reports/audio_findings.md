# Audio findings 

- Alignments processed: **7**
- With measurable meter: **7**

## Notes

- Alignments use lyrics-constrained Whisper prompting when audio exists; otherwise equal-time fallback (`align_quality=low`) or `none`.
- Meter score compares Simlish line duration to a naive English syllable duration prior — high scores suggest sung Simlish preserves English timing.
- F0/RMS are descriptive; rhyme evidence remains primarily orthographic from text analysis.

## Per-song meter

- `katy-perry__hot-n-cold` quality=low meter=0.0
- `kisha__sowieso` quality=medium meter=0.0
- `lily-allen__smile` quality=low meter=0.025441597093382954
- `luke-bryan__country-girl-shake-it-for-me` quality=medium meter=0.03308315384299102
- `my-chemical-romance__na-na-na` quality=low meter=0.31241252452453766
- `paramore__pressure` quality=low meter=0.0
- `the-young-punx-vs-the-camden-choral-collective__in-the-bleak-midwinter` quality=low meter=0.0
