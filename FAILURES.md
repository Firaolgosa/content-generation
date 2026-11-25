# Failures journal

What broke, what we tried, and what fixed it or worked around it. The newest entry is at the
bottom. Each entry links to evidence (log lines in `runs.jsonl`, commits, files).

Format: **symptom** → **cause** → **tried** → **resolution** → **evidence**.

---
### F1. Gemini TTS is no longer called through `generate_content` (2026-11-25)
- **Symptom:** most tutorials show `client.models.generate_content(..., response_modalities=["AUDIO"], speech_config=...)`.
- **Cause:** the current docs (ai.google.dev now redirects to aistudio.google.com/docs) use
  the **Interactions API**, `client.interactions.create(...)`, with `gemini-3.8-flash-tts`.
  It needs google-genai ≥ 2.25 and returns a full WAV instead of headerless PCM.
- **Resolution:** `pipeline/providers/gemini.py` uses the Interactions API, pins
  `google-genai>=2.25.0`, and `ensure_wav()` still wraps raw PCM in case an older model returns it.

### F2. FLUX.2 klein request fields are not documented by Cloudflare (2026-11-25)
- **Symptom:** the published input schema for `@cf/black-forest-labs/flux-2-klein-4b` is only a
  generic `multipart` wrapper. It has no field names for prompt, size or reference images.
- **Tried:** used the field names from the FLUX.2 examples (`prompt`, `width`, `height`,
  `seed`, `input_image_0..3`).
- **Resolution:** `make smoke` makes one text→image call and one reference→image call to
  confirm them. If klein rejects the request, keyframes fall back to FLUX.1 schnell (text
  only), which is logged as `"fallback": true`.
- **Evidence:** `runs.jsonl` (`run_id: 20261125T121125Z-30bc`, `item=cloudflare_flux2`,
  `status=ok`, `latency_s=9.831`, `detail="text->image (512, 512), reference->image ok"`).

### F3. Homebrew's FFmpeg cannot burn subtitles or draw text (2026-11-25)
- **Symptom:** `brew info ffmpeg` (9.1) lists no libass and no freetype dependency, so the
  `subtitles` and `drawtext` filters are missing.
- **Cause:** Homebrew slimmed the core ffmpeg formula. Other machines will have different builds.
- **Resolution:** subtitles and the end card are rendered as transparent PNGs with Pillow
  (`pipeline/overlays.py`) and composited with the `overlay` filter, which every build has.
  The bundled Noto Sans Ethiopic font means Amharic renders the same on every machine.

### F4. System Python is 3.9 and the network is slow (2026-11-25)
- **Symptom:** `/usr/bin/python3` is 3.9.6, and `uv python install 3.12` stalled on a slow download.
- **Resolution:** uv already had CPython 3.13 cached. `requires-python = ">=3.12"`, so
  `uv sync --python 3.13` works without downloading anything.

### F5. Cloudflare `flux-1-schnell` rejects `seed` in JSON payload (2026-11-25)
- **Symptom:** `cloudflare_schnell` smoke check failed with `400 Bad Input: Additional or unevaluated properties '/seed' at '/' not allowed` (`code: 5006`).
- **Cause:** `pipeline/providers/cloudflare.py` sent `{"prompt": ..., "steps": ..., "seed": ...}` to `@cf/black-forest-labs/flux-1-schnell`, but Cloudflare's schema for `flux-1-schnell` does not accept `seed`.
- **Resolution:** Updated `flux_schnell()` in `pipeline/providers/cloudflare.py` to omit `seed` from the JSON payload (keeping the parameter for call-site compatibility) and updated `tests/test_providers.py`. Re-running `pipeline.smoke` confirmed `cloudflare_schnell` now succeeds (`(1024, 1024)`).
- **Evidence:** `runs.jsonl` (`run_id: 20261125T121125Z-30bc`, `item=cloudflare_schnell`, `status=failed`; and re-run `status=ok` with `(1024, 1024)`).

### F6. `gemini-3.8-flash` returned transient 503 high demand (2026-11-25)
- **Symptom:** `gemini_text` smoke check failed on both attempts with `503: This model is currently experiencing high demand.` (`latency_s=2.133` and `87.119`).
- **Cause:** Upstream capacity spike on `gemini-3.8-flash`. `GEMINI_API_KEY` itself is valid—`gemini_tts` (`gemini-3.8-flash-tts`) succeeded in the same run (`4.866s`, `179 KB -> tts_amharic.wav`).
- **Resolution:** Re-run `pipeline.smoke` (skipping Kaggle until configured) or retry when demand subsides.
- **Evidence:** `runs.jsonl` (`run_id: 20261125T121125Z-30bc`, `item=gemini_text` & `item=gemini_tts`).

### F7. Kaggle credentials not configured in `.env` (2026-11-25)
- **Symptom:** `kaggle` smoke check failed with `Missing environment variable(s): KAGGLE_USERNAME, KAGGLE_KEY`.
- **Cause:** `.env` currently has `GEMINI_API_KEY`, `CLOUDFLARE_ACCOUNT_ID`, and `CLOUDFLARE_API_TOKEN`, but not `KAGGLE_USERNAME` and `KAGGLE_KEY`.
- **Resolution:** Add `KAGGLE_USERNAME` and `KAGGLE_KEY` to `.env` (from Kaggle Account Settings -> API -> Create New Token) when ready for Phase 2 (Wan 2.2 / ACE-Step 1.5).

<!-- Next entries: quota hits, OOM on the T4, identity drift across keyframes, Amharic
     pronunciation errors in TTS, black frames from fp16 on Turing, ... -->