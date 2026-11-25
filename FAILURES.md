# Failures journal

What broke, what we tried, and what fixed it or worked around it. The newest entry is at the
bottom. Each entry links to evidence (log lines in `runs.jsonl`, commits, files).

Format: **symptom** → **cause** → **tried** → **resolution** → **evidence**.

---

### F1. The reference repo's providers are all unusable from here (2026-11-25)
- **Symptom:** the starter codebase (`ai-content`) targets Lyria, Veo, Imagen, Kling and
  MiniMax. Its own notes record `429 RESOURCE_EXHAUSTED` (Veo, Imagen) and
  `err_unverified_card` (AIMLAPI).
- **Cause:** those models moved behind paid billing or were retired, as the brief says.
- **Resolution:** kept its useful patterns (result objects, retry with backoff, hash-based
  duplicate detection, the FFmpeg wrapper) and rebuilt the providers on the free stack:
  Gemini TTS, FLUX on Cloudflare Workers AI, Wan 2.2 and ACE-Step on Kaggle.

### F2. Gemini TTS is no longer called through `generate_content` (2026-11-25)
- **Symptom:** most tutorials show `client.models.generate_content(..., response_modalities=["AUDIO"], speech_config=...)`.
- **Cause:** the current docs (ai.google.dev now redirects to aistudio.google.com/docs) use
  the **Interactions API**, `client.interactions.create(...)`, with `gemini-3.8-flash-tts`.
  It needs google-genai ≥ 2.25 and returns a full WAV instead of headerless PCM.
- **Resolution:** `pipeline/providers/gemini.py` uses the Interactions API, pins
  `google-genai>=2.25.0`, and `ensure_wav()` still wraps raw PCM in case an older model returns it.

### F3. FLUX.2 klein request fields are not documented by Cloudflare (2026-11-25)
- **Symptom:** the published input schema for `@cf/black-forest-labs/flux-2-klein-4b` is only a
  generic `multipart` wrapper. It has no field names for prompt, size or reference images.
- **Tried:** used the field names from the FLUX.2 examples (`prompt`, `width`, `height`,
  `seed`, `input_image_0..3`).
- **Resolution:** `make smoke` makes one text→image call and one reference→image call to
  confirm them. If klein rejects the request, keyframes fall back to FLUX.1 schnell (text
  only), which is logged as `"fallback": true`.
- **Evidence:** TODO after `make smoke` → paste the `stage=smoke` lines here.

### F4. Homebrew's FFmpeg cannot burn subtitles or draw text (2026-11-25)
- **Symptom:** `brew info ffmpeg` (9.1) lists no libass and no freetype dependency, so the
  `subtitles` and `drawtext` filters are missing.
- **Cause:** Homebrew slimmed the core ffmpeg formula. Other machines will have different builds.
- **Resolution:** subtitles and the end card are rendered as transparent PNGs with Pillow
  (`pipeline/overlays.py`) and composited with the `overlay` filter, which every build has.
  The bundled Noto Sans Ethiopic font means Amharic renders the same on every machine.

### F5. System Python is 3.9 and the network is slow (2026-11-25)
- **Symptom:** `/usr/bin/python3` is 3.9.6, and `uv python install 3.12` stalled on a slow download.
- **Resolution:** uv already had CPython 3.13 cached. `requires-python = ">=3.12"`, so
  `uv sync --python 3.13` works without downloading anything.

<!-- Next entries: quota hits, OOM on the T4, identity drift across keyframes, Amharic
     pronunciation errors in TTS, black frames from fp16 on Turing, ... -->
