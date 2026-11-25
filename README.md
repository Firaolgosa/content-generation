# Heritage Short

A small film studio in code. One file, [`storyboard.json`](storyboard.json), describes a
60–90 second short film: its shots, prompts, seeds, Amharic narration, English subtitles and
music cues. The pipeline turns it into keyframes, moving shots, a score, narration and a
finished edit in 16:9 and 9:16, and logs every model call to `runs.jsonl`.

> **Status:** the pipeline works end to end. `storyboard.json` still holds a **placeholder**
> story (`"status": "placeholder"`, no real people) that is used to test every stage. The real
> story replaces it, with consent recorded in [ETHICS.md](ETHICS.md) first.

## One command

```bash
git clone <this repo> && cd content-generation
cp .env.example .env        # add your keys (see below)
make install                # uv sync; FFmpeg must be on PATH
make film                   # validate → narration → keyframes → shots → music → assemble
```

Output: `outputs/final/<title>_16x9.mp4`, `<title>_9x16.mp4`, `subtitles_en.srt` and
`timeline.json`.

Generated media is committed under `outputs/`. On a clean clone, `make film` therefore
re-assembles the film from cache without calling any model, and the log shows only
`cache_hit` lines. Change one prompt or one narration line and only that item is regenerated.

## Requirements

| Tool | Why | Install |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Python 3.12+ and dependencies | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| FFmpeg | assembly (any build; subtitles are rendered with Pillow) | `brew install ffmpeg` / `apt install ffmpeg` |
| Gemini API key | script, translation, narration (TTS) | [Google AI Studio](https://aistudio.google.com/apikey), free tier |
| Cloudflare account | keyframes (FLUX on Workers AI) | Account ID plus an API token with the *Workers AI* template |
| Kaggle account, phone-verified | Wan 2.2 and ACE-Step on a free T4 GPU | Settings → API → Create New Token |

`.env` is git-ignored. Missing keys produce an error that names the variable.

## Stages

| Command | What it does |
|---|---|
| `make smoke` | Calls every provider once and logs latency (first thing to run) |
| `make validate` | Checks the storyboard against the JSON Schema, cross-field rules and the consent gate |
| `make draft` | Gemini drafts `storyboard.draft.json` from `story/brief.md` (review it before use) |
| `make narration` | Gemini 3.8 Flash TTS, one WAV per shot |
| `make radio` | **Radio cut**: narration over a placeholder bed on black, with subtitles (for the first user test) |
| `make refs` / `make keyframes` | Golden style frame and character sheets, then one keyframe per shot conditioned on them |
| `make shots` | Lists which Wan clips are ready or pending and writes `outputs/wan/jobs.json` |
| `make kaggle-wan` → `make kaggle-wan-wait` | Renders the pending clips on a Kaggle T4 and pulls them back |
| `make music` / `make kaggle-music` → `make kaggle-music-wait` | Same flow for the ACE-Step score candidates |
| `make assemble` | Cut, duck, subtitle, loudness and end card, in both aspect ratios |
| `make film` | All of the above except the Kaggle pushes |
| `make costs` | Rebuilds the measurement table in COSTS.md from `runs.jsonl` |
| `make test` | Unit tests with coverage |

Wan and ACE-Step run as Kaggle kernels because they need a GPU. `make film` uses whichever
clips and candidates already exist, and falls back to Ken Burns moves and the placeholder
bed for the rest. The film always renders.

## Regenerating one shot (the walkthrough demo)

```bash
# 1. edit one field, e.g. shots[2].image_prompt or shots[4].narration
# 2. re-run
make film
# 3. see exactly what happened
tail -n 40 runs.jsonl | grep -v cache_hit
```

Only the edited shot produces a new `"status": "ok"` model call. Every other item is a
`cache_hit`. See [ARCHITECTURE.md](ARCHITECTURE.md#caching-re-runs-regenerate-only-what-changed)
for what each cache key contains.

## Choosing the score

`music.cues[].candidates` (default 3) are generated with seeds `seed`, `seed+1`, and so on.
Listen to `outputs/music/<cue>_<key>_c*.wav` under the narration, set `"chosen": <index>` and
a `"reason"`, then log the comparison in [EXPERIMENTS.md](EXPERIMENTS.md).

## Repository map

```
storyboard.json            the contract: shots, durations, prompts, seeds, narration, music cues
schema/                    JSON Schema for the storyboard, validated before every run
pipeline/                  one module per stage, plus common (log, cache, retry), timeline, mixdown, video
  providers/               thin Gemini and Cloudflare clients
kaggle/                    GPU kernels: wan_i2v.py, ace_step.py
outputs/                   generated media, kept so the run can be inspected
runs.jsonl                 one line per model call, cache hit and retry
tests/                     pytest (make test)
DESIGN.md                  audience, intent, user tests and what changed because of them
ARCHITECTURE.md            stages, contracts, caching, failure handling
EXPERIMENTS.md             hypothesis → change → result
FAILURES.md                what broke, what we tried, what fixed it
COSTS.md                   measured latency and GPU minutes per stage, list-price equivalent
ETHICS.md                  consent records, licences of every model and output, labelling plan
```

## What it costs

Actual spend is $0, because every service is a free tier. The measured latency, GPU minutes
and list-price equivalents are in [COSTS.md](COSTS.md), which `make costs` generates from
`runs.jsonl`.

## Licences

Code: MIT. Fonts: Noto Sans and Noto Sans Ethiopic (SIL OFL 1.1, `assets/fonts/OFL.txt`).
Model and output licences are listed in [ETHICS.md](ETHICS.md).
