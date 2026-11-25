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
| E3 | planned | narration | TTS mispronounces names and places | Native-speaker listen on every proper noun; respell phonetically where wrong | | |
| E4 | planned | keyframes | Conditioning on the character sheet keeps the face consistent across shots | Shots s02/s04/s07 with vs without the reference image (same seeds) | | |
| E5 | planned | keyframes | FLUX.2 klein follows composition better than FLUX.1 schnell | Same prompt and seed on both | | |
| E6 | planned | keyframes | Putting the style block in every prompt prevents drift | Style block appended vs only in the first shot | | |
| E7 | planned | shots | Motion-only prompts beat re-describing the subject in image-to-video | s05 motion-only vs full description | | |
| E8 | planned | shots | 480p drafts are good enough to choose shots before spending on 720p | GPU minutes and visual check at 832×480 vs 1280×704 on one shot | | |
| E9 | planned | music | Of three ACE-Step seeds, the sparsest sits best under narration | c0/c1/c2 auditioned at low volume under the radio cut | | |
| E10 | planned | mix | Ducking ratio 6 / release 1500 ms keeps the music audible without masking the voice | ratio 4 vs 6 vs 10, listened on a phone speaker | | |
| E11 | planned | assembly | `fit_blur` beats a tight crop for low-res Wan clips in 9:16 | Same shot, both modes | | |
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
