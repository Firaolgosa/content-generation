# Experiments

One entry per experiment: **hypothesis → change (one variable, other seeds fixed) → result →
decision**, with evidence from `runs.jsonl` (run_id or cache_key) or a file in `outputs/`.
The target is at least ten entries.

Entries marked *planned* have not been run yet. Their result must be written from what was
actually observed.

| # | Status | Stage | Hypothesis | Change | Result | Decision |
|---|---|---|---|---|---|---|
| E1 | planned | narration | A short style instruction improves Amharic prosody more than switching voices | Same line, voice Sulafat; style "" vs "warm, unhurried…" | | |
| E2 | planned | narration | Voice choice matters for warmth | Same line and style; Sulafat vs Achernar vs Gacrux | | |
| E3 | done | narration | Gemini 3.8 Flash TTS handles Amharic narration cleanly across 9 shots | Synthesized all 9 Amharic lines (`s01`–`s09`) with `voice=Sulafat` | 9 WAVs (`5.0s`–`7.5s`, `run_id=20261125T125406Z-2802`), median `4.67s` latency | Kept `Sulafat` for all 9 shots; verify proper nouns with native speakers |
| E4 | done | keyframes | Character sheet + age-specific wording prevents aging and anatomy artifacts | Updated `grandmother` (`sheet_seed: 3051`, "17-year-old teenage girl", removed `"grandmother"` from prompts) + fixed `s07` (`seed: 2957`) | `s06_016b1e61b700.png` renders 17yo; `s07_40b851668d4b.png` fixes severed neck (`s07_50bda4c118a1.png`) | Kept updated prompts; hash cache regenerated only 5 items (`char-grandmother`, `s04`, `s06`–`s08`) |
| E5 | done | keyframes | FLUX.2 klein follows reference conditioning while FLUX.1 schnell is text-only | Tested both in `pipeline.smoke` (`run_id=20261125T121125Z-30bc`) | `flux-2-klein-4b` supports `input_image_0..3` (`9.83s`); `flux-1-schnell` rejects `seed` (`400 code 5006`) | Use `flux-2-klein-4b` primary; removed `seed` from `flux_schnell()` fallback |
| E6 | done | keyframes | Putting the style block in every prompt prevents visual drift | Appended `style.block` to all 9 shots + conditioned on `style_4b73f7d04b77.png` | Consistent ochre/umber/green painterly look across `s01`–`s09` | Kept `style.block` + golden reference conditioning on every shot |
| E7 | planned | shots | Motion-only prompts beat re-describing the subject in image-to-video | s05 motion-only vs full description | | |
| E8 | done | shots | Reducing `num_frames` + sequential CPU offload avoids T4 OOM | `121 frames` + `enable_model_cpu_offload` vs `81 frames` + `enable_sequential_cpu_offload` | `121f` hit `CUDA OutOfMemoryError` (`14.28 GiB` on T4, `run_id=20261126T065022Z-ae1b`); `81f` queued cleanly | Use `enable_sequential_cpu_offload()`, `vae.enable_slicing()`, `81` frames, `24` steps |
| E9 | done | music | Of three ACE-Step seeds, the sparsest sits best under narration | c0 (4242), c1 (4243), c2 (4244) measured via ebur128 & auditioned | c0: -15.8 LUFS (LRA 8.8), c1: -16.0 LUFS (LRA 9.6), c2: -16.2 LUFS (LRA 8.9) | Selected c2 (quietest integrated loudness, clean tail) |
| E10 | done | mix | Ducking ratio 6 / release 1500 ms keeps music audible without masking voice | Assembled `s01`–`s09` with `sidechaincompress` (`threshold=0.02, ratio=6`) + `loudnorm` | Input `-16.98 LUFS` normalized to `-14 LUFS` (`run_id=20261126T071737Z-fc42`) | Kept `ratio=6`, `release=1500ms`, `-14 LUFS` target |
| E11 | done | assembly | Ken Burns fallback + centred framing produces clean 16:9 & 9:16 rough cuts without blocking on Kaggle | Assembled all 9 shots via Ken Burns while Wan 2.2 runs on Kaggle | 75.0s MP4s in 16:9 and 9:16 normalized to -14 LUFS; 100% cache reuse | Kept Ken Burns rough cut; pull Wan clips to `outputs/wan_kaggle` when ready |
| E12 | planned | benchmark | A frontier model (if org access) beats Wan 2.2 in a blind test | Same keyframe and motion; ≥5 people choose blind | | |

## Detailed entries

<!-- Copy this block per experiment.
### E1. <title>
- **Hypothesis:**
- **Change (one variable):**
- **Held fixed:** seeds …, model …
- **Evidence:** runs.jsonl run_id=…, files outputs/…
- **Result:**
- **Decision and why:**
-->
