# Architecture

One file, `storyboard.json`, is the contract between every stage. Each stage is a Python
module that reads the storyboard, checks its cache, calls one kind of model, and writes files
under `outputs/` whose names contain a hash of their inputs. `make film` runs them in order.

```
                 schema/storyboard.schema.json
                              │ validates (+ cross-field rules, consent gate)
                              ▼
 story/brief.md ──script──▶ storyboard.json ───────────────────────────────────────────┐
   (Gemini Flash)              │                                                       │
          ┌────────────────────┼───────────────────┬──────────────────────┐            │
          ▼                    ▼                   ▼                      ▼            │
     narration            keyframes             shots                  music           │
   Gemini 3.8 TTS     FLUX.2 klein (CF AI)   Wan 2.2 TI2V-5B        ACE-Step 1.5        │
   1 WAV / shot       refs → 1 PNG / shot    Kaggle T4, jobs.json   Kaggle, jobs.json   │
          │                    │                   │                      │            │
          │                    └──── keyframe ─────┘                      │            │
          ▼                                        ▼                      ▼            ▼
      timeline  ──────────────────────────────▶  assemble (FFmpeg + Pillow)  ◀── end card,
   (cut to the voice)                          segments · duck · loudnorm ·      subtitles
                                               subtitles · 16:9 + 9:16
                                                         │
                                                         ▼
                                    outputs/final/*.mp4, subtitles_en.srt, timeline.json
     every model call / cache hit / retry ──▶ runs.jsonl ──▶ pipeline/costs.py ──▶ COSTS.md
```

## Stages and their contracts

| Stage | Module | Reads from storyboard | Writes | Model |
|---|---|---|---|---|
| validate | `pipeline/storyboard.py` | everything | exit code + messages | none |
| script (optional) | `pipeline/script.py` | technical sections | `storyboard.draft.json` | Gemini Flash |
| narration | `pipeline/narration.py` | `shots[].narration`, `voice`, `models.tts` | `outputs/narration/<shot>_<key>.wav` | Gemini 3.8 Flash TTS |
| keyframes | `pipeline/keyframes.py` | `style`, `characters`, `shots[].image_prompt/seed`, `render.keyframe` | `outputs/references/*.png`, `outputs/keyframes/<shot>_<key>.png` | FLUX.2 klein 4B, fallback FLUX.1 schnell |
| shots | `pipeline/shots.py` + `kaggle/wan_i2v.py` | `shots[].motion_prompt/seed/video`, `render.wan` | `outputs/wan/jobs.json`, `outputs/wan/<shot>_<key>.mp4` | Wan 2.2 TI2V-5B |
| music | `pipeline/music.py` + `kaggle/ace_step.py` | `music.cues[]` | `outputs/music/jobs.json`, `outputs/music/<cue>_<key>_c<i>.wav` | ACE-Step 1.5 turbo |
| assemble | `pipeline/assemble.py`, `mixdown.py`, `video.py`, `overlays.py`, `timeline.py` | `mix`, `render`, `end_card`, subtitles | `outputs/final/` | none (FFmpeg) |

Rules that keep the stages independent:

- **Prompts, seeds and model IDs live in the storyboard**, never in code, so a run can be
  reproduced and explained from one file.
- **A stage finds its inputs by recomputing their keys**, rather than reading a "latest"
  pointer. The shots stage asks `keyframes.resolve(shot)`, and assembly asks
  `narration.path_for(shot)`. Nothing goes stale.
- **The schema is strict** (`additionalProperties: false` everywhere), so a typo in a field
  name fails validation instead of being silently ignored.
- **Validation goes beyond the schema**: unique shot IDs, known character IDs, music cues
  that point at real shots in the right order, `chosen < candidates`, Wan
  `num_frames = 4k+1`, and a subtitle for every narration line.
- **Consent gate in code.** A character or voice with `real_person: true` needs a
  `consent_ref` that exists as an anchor in `ETHICS.md`. Otherwise validation fails and no
  stage runs.

## Caching: re-runs regenerate only what changed

Each output is named `<item>_<key>.<ext>`, where `key = sha256(inputs)[:12]` over exactly
the inputs that affect it:

| Output | Key inputs |
|---|---|
| narration WAV | text, TTS model, voice, style |
| reference sheet | prompt, seed, model, size |
| keyframe | full prompt (shot + character descriptions + style block), seed, model, size, **bytes of the reference images used** |
| Wan clip | **keyframe bytes**, motion prompt, seed, Wan params, model |
| music candidate | caption, bpm, key, seed, model, **bucketed** duration |
| video segment | source clip/still bytes, exact segment duration, size, framing, camera |
| audio mixes | bytes of every input stem, mix settings |

So:

- Editing one shot's `image_prompt` changes its keyframe key, which changes its Wan clip key
  and its segment. No other shot is touched.
- Editing one `narration` line regenerates one WAV. The new length can re-time that shot,
  which shifts later segment start times but **not their content keys**, so only the edited
  shot's segment and the audio mixes are re-rendered.
- Editing a character description changes that character's sheet, and therefore the keys of
  the keyframes that use it.
- Music duration is bucketed (planned shot lengths + 15 s, rounded up to 10 s), so narration
  edits never invalidate the score. Assembly trims and fades each cue to its real window.

A hit is logged as `"status": "cache_hit"` in `runs.jsonl`, so the walkthrough can show that
a re-run made exactly one new model call.

Writes are atomic (temp file plus rename), so a crash never leaves a half-written file that
would later count as a cache hit.

## Failure handling

| Failure | Handling |
|---|---|
| 429 / 5xx / timeout from any API | `TransientError` → `call_logged` retries with exponential backoff (4 s, 8 s; 3 attempts). Every attempt gets its own log line (`retry`, `failed`, `ok`). |
| 400 / auth / bad schema | `PermanentError` → logged and raised immediately, no wasted retries. |
| FLUX.2 klein unavailable or its API changed | Fall back to FLUX.1 schnell (text only), logged with `"fallback": true`. The fallback file is kept under its own key. |
| Reference sheet fails | Keyframes continue without that reference (logged). |
| No Wan clip for a shot (not run yet, quota gone, black/NaN frames on T4) | Assembly animates the keyframe with an eased Ken Burns move (FFmpeg `zoompan`). The film always renders. |
| Wan clip shorter than the shot | Trim the weak first 0.25 s, slow down by up to 1.6×, then hold the last frame. |
| No music candidate chosen yet | A quiet, deterministic placeholder bed (generated in FFmpeg) is used, with a warning. |
| Kaggle session dies mid-batch | The kernel saves each clip as it finishes and stops starting jobs after an 8 h budget. `pull` collects what exists, and the next `push` only sends the missing keys. |
| One Kaggle job crashes | Caught per job and logged. The other jobs continue. |
| FFmpeg without libass/freetype (Homebrew's build) | Subtitles and the end card are rendered as PNGs with Pillow and overlaid, so they work with any FFmpeg. |
| Missing secrets | `require_env` names the missing variable and points to `.env.example`. |

## Assembly details

1. **Timeline** (`timeline.py`, pure functions). Each shot lasts
   `max(planned, lead + narration + tail)`, because picture is cut to the voice. English
   subtitle cues are split at sentence boundaries into chunks of at most 2 lines × 42
   characters, and timed across the narration in proportion to their length.
2. **Narration track**: per-line WAVs placed with `adelay`, then levelled to −16 LUFS.
3. **Music bed**: each cue trimmed to its window, faded in and out, levelled to −16 LUFS, then
   `music_gain_db` applied.
4. **Ducking**: `sidechaincompress`, with the voice as the sidechain (threshold 0.02,
   ratio 6, attack 300 ms, release 1500 ms by default; all values in `mix.duck`).
5. **Loudness**: two-pass `loudnorm` to −14 LUFS integrated with a −1 dB true peak. The
   measured input loudness is logged.
6. **Picture**: one segment per shot and aspect ratio, at an exact frame count and the same
   codec, then joined with the concat demuxer without re-encoding. For 9:16, each shot either
   crops a vertical strip at `vertical_focus_x` or uses `fit_blur` (the whole frame over a
   blurred fill), which suits low-resolution Wan drafts.
7. **Finish**: subtitle PNGs overlaid with time windows, AAC 192k, H.264 CRF 18,
   `+faststart`. Container metadata says "Made with AI" and lists the models. The end card
   says the same on screen.

## Observability: `runs.jsonl`

One JSON object per line:
`ts, run_id, stage, item, provider, model, params, seed, cache_key, attempt, status,
latency_s, cost_usd | neurons_est | gpu_s, output, error`.
Kaggle kernels write their own `kernel_runs.jsonl` (latency and GPU seconds per clip), and
`kaggle_jobs pull` merges it into the main log. `make costs` turns the log into the table in
`COSTS.md`.
