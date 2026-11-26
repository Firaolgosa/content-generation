# Heritage Short — *The Night in Bekoji* (`የበቆጂው ምሽት`)

A small, reproducible film studio in code. One central contract, [`storyboard.json`](storyboard.json), defines a **75-second Amharic-narrated short film** set in **1950 E.C. Bekoji**: its shots, durations, prompts, seeds, Amharic narration, English subtitles, audio mix settings, and music cues.

The pipeline validates the contract, synthesizes speech, generates style- and character-consistent keyframes, schedules optional GPU video/music jobs on Kaggle (with deterministic local fallbacks), mixes and normalizes audio to **-14 LUFS**, burns in subtitles and an AI disclosure end card, and exports both **16:9 (horizontal)** and **9:16 (vertical)** MP4s. Every model call, retry, failure, and cache hit is logged to [`runs.jsonl`](runs.jsonl).

---

## Quickstart (One Command)

### Option A: With `uv` and `make`
```bash
git clone <https://github.com/Firaolgosa/content-generation > && cd content-generation
cp .env.example .env        # fill in your API keys (see Requirements below)
make install                # installs Python >=3.12 deps via uv; FFmpeg must be on PATH
make film                   # validate → narration → keyframes → shots → music → assemble
```

### Option B: With standard Python 3.12+ `.venv` (if `uv` is not installed)
```bash
git clone <https://github.com/Firaolgosa/content-generation > && cd content-generation
cp .env.example .env        # fill in your API keys
python3.12 -m venv .venv
.venv/bin/pip install "google-genai>=2.25.0" "httpx>=0.27" "jsonschema>=4.22" "python-dotenv>=1.0" "pillow>=10.3" "kaggle>=1.7" "six>=1.17.0" "pytest>=8.0" "pytest-cov>=5.0" "ruff>=0.6"
.venv/bin/python -m pipeline.run
```

**Outputs:**
- `outputs/final/the-night-in-bekoji_9x16.mp4` (vertical, 1080×1920, 24 fps, -14 LUFS)
- `outputs/final/the-night-in-bekoji_16x9.mp4` (horizontal, 1920×1080, 24 fps, -14 LUFS)
- `outputs/final/subtitles_en.srt` & `outputs/final/timeline.json`

> Generated media is cached under `outputs/`. On a clean clone with `outputs/` present, running the pipeline re-assembles the film from cache with zero API calls (`"status": "cache_hit"` in `runs.jsonl`). Change one prompt or narration line, and only that item regenerates.

---

## System Architecture & Pipeline Stages

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full Mermaid flowchart, cache-key definitions, and failure-handling matrix.

| Stage | Module | What it does | Output |
|---|---|---|---|
| **1. Validate** | `pipeline/storyboard.py` | Validates `storyboard.json` against `schema/storyboard.schema.json`, cross-field rules, and the `ETHICS.md` consent gate | Exit code + summary |
| **2. Script** *(optional)* | `pipeline/script.py` | Drafts `storyboard.draft.json` from `story/brief.md` via Gemini | `storyboard.draft.json` |
| **3. Narration** | `pipeline/narration.py` | Calls Gemini 3.8 Flash TTS (`Sulafat`) once per shot | `outputs/narration/<shot>_<key>.wav` |
| **4. Keyframes** | `pipeline/keyframes.py` | Generates golden style frame + character sheets, then conditions every shot keyframe on them | `outputs/references/*.png`, `outputs/keyframes/<shot>_<key>.png` |
| **5. Shots** | `pipeline/shots.py` + `kaggle/wan_i2v.py` | Prepares Wan 2.2 TI2V-5B jobs for Kaggle T4; assembly uses eased **Ken Burns** motion if clips are pending | `outputs/wan/jobs.json`, `outputs/wan/<shot>_<key>.mp4` |
| **6. Music** | `pipeline/music.py` + `kaggle/ace_step.py` | Generates 3 ACE-Step 1.5 score candidates on Kaggle (`c0`, `c1`, `c2`); `c2` (`seed 4244`) is selected | `outputs/music/jobs.json`, `outputs/music/<cue>_<key>_c<i>.wav` |
| **7. Assemble** | `pipeline/assemble.py`, `timeline.py`, `mixdown.py`, `video.py`, `overlays.py` | Cuts shots to voice timing, ducks music (`sidechaincompress`), renders Pillow PNG subtitles/end card, normalizes to `-14 LUFS`, exports 16:9 & 9:16 | `outputs/final/*.mp4` |

---

## Technology Stack ($0 Free Tiers)

| Role | Model / Tool | Provider / Runtime | License / Terms |
|---|---|---|---|
| **Script & Translation** | `gemini-3.8-flash` | Google AI Studio (Free tier) | Gemini API Terms |
| **Amharic Narration** | `gemini-3.8-flash-tts` (`Sulafat`) | Google AI Studio (Interactions API) | Gemini API Terms |
| **Keyframes & Refs** | `@cf/black-forest-labs/flux-2-klein-4b` | Cloudflare Workers AI (Free daily neurons) | Apache 2.0 |
| **Image Fallback** | `@cf/black-forest-labs/flux-1-schnell` | Cloudflare Workers AI | Apache 2.0 |
| **Moving Shots** | `Wan-AI/Wan2.2-TI2V-5B-Diffusers` | Kaggle Notebook (Tesla T4, free weekly quota) | Apache 2.0 |
| **Music Score** | `ACE-Step/acestep-v15-turbo` | Kaggle Notebook (Tesla T4) | MIT |
| **Assembly & Overlays** | `FFmpeg` + `Pillow` + `Noto Sans Ethiopic` | Local machine | LGPL/GPL / SIL OFL 1.1 |

---

## Requirements & `.env` Setup

1. **FFmpeg** on `PATH` (`brew install ffmpeg` on macOS, `apt install ffmpeg` on Linux). Subtitles and end cards are rendered as transparent PNGs with Pillow (`pipeline/overlays.py`), so any FFmpeg build works—even without `libass` or `freetype`.
2. **Python 3.12+** (with `uv` or `.venv`).
3. **API Credentials** in `.env` (git-ignored; copy from `.env.example`):

| Variable | Provider | Where to get it |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare Workers AI | Cloudflare Dashboard → Account ID |
| `CLOUDFLARE_API_TOKEN` | Cloudflare Workers AI | API Tokens → *Workers AI* template |
| `KAGGLE_USERNAME` | Kaggle (phone-verified) | Kaggle Account → Settings |
| `KAGGLE_API_TOKEN` *(or `KAGGLE_KEY`)* | Kaggle API | Settings → API → Create New Token (`KGAT_...` tokens are supported automatically) |

---

## Commands Reference

Every `make` target can also be run directly with `.venv/bin/python -m <module>`:

| `make` target | Direct `.venv` command | What it does |
|---|---|---|
| `make smoke` | `.venv/bin/python -m pipeline.smoke` | Calls every provider once (`--skip kaggle` supported) and logs latency to `runs.jsonl` |
| `make validate` | `.venv/bin/python -m pipeline.storyboard` | Validates `storyboard.json` schema, cross-field rules, and `ETHICS.md` consent gate |
| `make draft` | `.venv/bin/python -m pipeline.script story/brief.md` | Drafts `storyboard.draft.json` from `story/brief.md` |
| `make narration` | `.venv/bin/python -m pipeline.narration` | Generates Amharic TTS WAVs (cached) |
| `make radio` | `.venv/bin/python -m pipeline.run --radio` | **Radio cut**: narration + placeholder bed on black with subtitles (Phase 1 user test) |
| `make refs` | `.venv/bin/python -m pipeline.keyframes --refs-only` | Generates style frame + character sheets only |
| `make keyframes` | `.venv/bin/python -m pipeline.keyframes` | Generates reference sheets + all shot keyframes (cached) |
| `make shots` | `.venv/bin/python -m pipeline.shots` | Lists ready/pending Wan 2.2 clips and writes `outputs/wan/jobs.json` |
| `make kaggle-wan` | `.venv/bin/python -m pipeline.kaggle_jobs push wan` | Pushes pending Wan 2.2 clips to Kaggle T4 |
| `make kaggle-wan-wait` | `.venv/bin/python -m pipeline.kaggle_jobs wait wan` | Polls Kaggle and pulls clips (`--dest outputs/wan_kaggle` pulls to a separate folder) |
| `make music` | `.venv/bin/python -m pipeline.music` | Lists ready/pending ACE-Step candidates |
| `make kaggle-music` | `.venv/bin/python -m pipeline.kaggle_jobs push music` | Pushes ACE-Step job to Kaggle |
| `make kaggle-music-wait` | `.venv/bin/python -m pipeline.kaggle_jobs wait music` | Polls Kaggle and pulls score candidates into `outputs/music/` |
| `make assemble` | `.venv/bin/python -m pipeline.assemble` | Cuts, ducks, subtitles, normalizes (`-14 LUFS`), and exports 16:9 & 9:16 MP4s |
| `make film` | `.venv/bin/python -m pipeline.run` | **Full pipeline:** `validate` → `narration` → `keyframes` → `shots` → `music` → `assemble` |
| `make costs` | `.venv/bin/python -m pipeline.costs` | Summarizes `runs.jsonl` into `COSTS.md` |
| `make test` | `.venv/bin/pytest --cov=pipeline -q` | Runs all 59 unit tests with coverage |
| `make lint` | `.venv/bin/ruff check pipeline tests kaggle` | Runs Ruff linter |

---

## Hash-Based Caching & Single-Shot Regeneration

Every generated file is keyed by `sha256(inputs)[:12]`:
- Editing **one shot's `image_prompt`** regenerates only that shot's keyframe (and its Wan clip/segment).
- Editing **one shot's `narration`** regenerates only that shot's WAV and re-assembles the timeline.
- Editing **a character's `description`** regenerates only that character sheet and the keyframes referencing it.

To demonstrate single-shot regeneration:
```bash
# 1. Edit one field in storyboard.json (e.g. shots[0].image_prompt)
# 2. Re-run the pipeline:
.venv/bin/python -m pipeline.run
# 3. Inspect runs.jsonl to verify only that shot made a new model call:
tail -n 30 runs.jsonl | grep -v cache_hit
```

---

## What It Costs

**Actual spend: \$0** (all stages run on free tiers).  
Measured latency, GPU minutes, and list-price equivalents (**\$0.0351** total across all logged runs) are tracked automatically in [COSTS.md](COSTS.md) via `pipeline/costs.py`.

---

## Repository Map

```text
├── storyboard.json            # Central contract: shots, prompts, seeds, narration, cues, mix
├── schema/                    # JSON Schema (draft 2020-12) validated before every run
├── story/brief.md             # Story brief (input to make draft)
├── pipeline/                  # Modular Python stages + common.py (logging, hashing, retries)
│   └── providers/             # Thin Gemini (Interactions API) & Cloudflare Workers AI clients
├── kaggle/                    # GPU kernels: wan_i2v.py (Wan 2.2) & ace_step.py (ACE-Step 1.5)
├── assets/fonts/              # Bundled Noto Sans & Noto Sans Ethiopic (SIL OFL 1.1)
├── outputs/                   # Cached media artifacts (narration, references, keyframes, music, final)
├── runs.jsonl                 # Structured JSONL audit log (every call, retry, failure, cache_hit)
├── tests/                     # 59 offline unit & integration tests (pytest)
├── DESIGN.md                  # Audience, intent, shot reasons, and user test notes
├── ARCHITECTURE.md            # Mermaid architecture diagram, cache keys, and failure handling
├── EXPERIMENTS.md             # Hypothesis → change → result log
├── FAILURES.md                # Real blockers encountered and resolutions
├── COSTS.md                   # Measured latency, GPU minutes, and list-price equivalents
├── ETHICS.md                  # Consent policy, model/output licences, and AI labelling plan
└── REPORT.md                  # Engineering report for Assignment 1
```

---

## Licences

- **Code:** MIT
- **Fonts:** Noto Sans and Noto Sans Ethiopic (`assets/fonts/OFL.txt`, SIL OFL 1.1)
- **Models & Outputs:** Listed per model in [ETHICS.md](ETHICS.md) (FLUX.2 klein 4B Apache 2.0, Wan 2.2 Apache 2.0, ACE-Step 1.5 MIT).
