# Engineering Report — *The Night in Bekoji* (`የበቆጂው ምሽት`)

**Assignment:** B2W0: AI-Content Generation — Codebase and Report  
**Repository:** `<INSERT YOUR PUBLIC GITHUB URL>`  
**Film Outputs:** `outputs/final/the-night-in-bekoji_9x16.mp4` (vertical) and `the-night-in-bekoji_16x9.mp4` (horizontal), `75.0s`, `-14 LUFS`

---

## 1. What We Set Out to Make and For Whom

We built **The Night in Bekoji (`የበቆጂው ምሽት`)**, a 75-second Amharic-narrated heritage short film with English subtitles and an original AI-composed Ethiopian-inspired acoustic score, generated end-to-end from a single JSON contract (`storyboard.json`).

- **Story:** In **1950 E.C.** in **Bekoji**, my grandfather and his friend were travelling to see another young woman when night fell late. They stopped at a home along the road for shelter. Inside, by the warmth of the hearth, he met my grandmother (then 17 years old) for the first time—and by morning chose her over his original journey.
- **Audience & Intent:** My family (parents, aunts, uncles, and cousins) watching on their phones in the family group chat (`9:16` vertical first), designed so they feel warmth, pride, and nostalgia remembering how their parents' and grandparents' story began.
- **Ethics & Consent:** Recorded in `ETHICS.md`. Because no real photographs, likenesses, or cloned voices are used (`"real_person": false` for all characters and voice), stylized painterly illustrations and the prebuilt Gemini TTS voice (`Sulafat`) depict the story respectfully while keeping private family names out of free-tier API prompts.

---

## 2. Pipeline Architecture & Reproducibility

The pipeline is structured around a single validated contract (`storyboard.json` + `schema/storyboard.schema.json`):
1. **`pipeline.storyboard`**: Validates schema, shot durations, and the `ETHICS.md` consent gate.
2. **`pipeline.narration`**: Synthesizes 9 Amharic WAVs via `gemini-3.8-flash-tts` (`Sulafat`).
3. **`pipeline.keyframes`**: Generates the golden style frame (`style_4b73f7d04b77.png`) and character sheets (`grandfather`, `grandmother`) via Cloudflare Workers AI (`flux-2-klein-4b`), then conditions all 9 shot keyframes on them.
4. **`pipeline.shots` & `pipeline.kaggle_jobs`**: Prepares Wan 2.2 TI2V-5B jobs for Kaggle T4 GPU, with deterministic **Ken Burns** fallback in assembly whenever GPU clips are pending or unavailable.
5. **`pipeline.music`**: Generates 3 ACE-Step 1.5 score candidates on Kaggle (`c0`, `c1`, `c2`) and uses the selected candidate (`c2`, `seed 4244`).
6. **`pipeline.assemble`**: Cuts shots to narration timing, ducks music under voice via FFmpeg `sidechaincompress` (`threshold=0.02, ratio=6`), renders Amharic/English PNG overlays via Pillow (working around Homebrew FFmpeg's missing `libass`/`freetype`), normalizes to `-14 LUFS`, and exports both `16:9` and `9:16` MP4s with a 3-second AI end card.

Every model call, retry, failure, and cache hit is logged to `runs.jsonl`. Total list-price equivalent across all runs is **$0.0351** (actual spend: **$0** on free tiers).

---

## 3. What We Learned From Our Audience

- **User Test 1 (Radio Cut — `run_id: 20261125T125406Z-2802`):**  
  *[INSERT 3+ AUDIENCE QUOTES & WHAT CHANGED IN `DESIGN.md`]*
- **User Test 2 (Visual Rough Cut — `the-night-in-bekoji_9x16.mp4`):**
  1. **Anatomy artifact caught (`s07`):** A viewer spotted that in `s07_50bda4c118a1.png`, the young man's head was severed at the neck. We updated `s07`'s prompt to explicitly frame his full head, face, and shoulders (`seed: 2957` -> `s07_40b851668d4b.png`).
  2. **Character age bias caught (`grandmother`):** Viewers noted the grandmother looked too old for a 17-year-old at the time of the story (`s06_bb6ea3c9b799.png`). Removing the word `"grandmother"` from the image prompts and updating `characters[1].description` to `"A 17-year-old Ethiopian teenage girl..."` (`sheet_seed: 3051`) produced a natural 17-year-old portrait (`s06_016b1e61b700.png`).
  *[INSERT ANY ADDITIONAL FAMILY FEEDBACK FROM YOUR FINAL SCREENING]*

---

## 4. The Hardest Problem and How We Solved It

Two real production blockers stood out (documented in `FAILURES.md`):
1. **Wan 2.2 `CUDA OutOfMemoryError` on Kaggle Tesla T4 (`F8`):** All 4 Wan 2.2 jobs OOM'd at `14.28 GiB` on a `14.56 GiB` T4 (`run_id=20261126T065022Z-ae1b`). We switched `kaggle/wan_i2v.py` to `enable_sequential_cpu_offload()`, enabled `vae.enable_slicing()` + `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, and lowered draft frames from `121` to `81` (`24` steps). Because GPU queues on Kaggle also took 30+ minutes, we used the pipeline's deterministic Ken Burns fallback to keep iterating on the film without blocking, and added `--dest outputs/wan_kaggle` to `pipeline/kaggle_jobs.py` so background Kaggle renders can be pulled separately.
2. **Cloudflare `flux-1-schnell` schema mismatch & Kaggle `KGAT_` auth (`F6`, `F7`):** Live smoke testing caught that `flux-1-schnell` rejects `seed` (`400 code 5006`) and `kaggle` CLI v2.2.5 requires `KAGGLE_API_TOKEN` for `KGAT_` tokens rather than `KAGGLE_KEY`. Both were fixed in `pipeline/providers/cloudflare.py` and `pipeline/kaggle_jobs.py` and verified with 59 passing unit tests.

---

## 5. Suggested Practices Tested Honestly

- **Practice that beat our instinct — Hash-based caching around `storyboard.json`:**  
  At first, building content-hashed cache keys for every stage felt like extra plumbing. When audience feedback required fixing `s07` and aging down the `grandmother` character, re-running `pipeline.keyframes` regenerated **only** `char-grandmother`, `s04`, `s06`, `s07`, and `s08`—leaving `s01`, `s02`, `s03`, `s05`, `s09`, and all 9 narration WAVs untouched. That saved both Cloudflare quota and iteration time.
- **Practice that did not match our expectation — Relying on Kaggle Wan 2.2 in the critical path:**  
  With a 30+ minute GPU queue and 14.56 GiB VRAM OOMs on T4, waiting for cloud video generation on every edit stalls creative iteration. Treating Wan 2.2 as an asynchronous enhancement (pulled to `outputs/wan_kaggle/`) while keeping Ken Burns as the fast local baseline proved far more practical.

---

## 6. Ceiling Work & What We Would Build Next

- **Ceiling Work:** Added `--dest` support in `pipeline/kaggle_jobs.py` for non-blocking asynchronous GPU renders (`outputs/wan_kaggle/`), built Pillow-based Ethiopic subtitle/end-card rendering (`pipeline/overlays.py`) so the pipeline is portable across FFmpeg builds without `libass`, and measured all 3 ACE-Step candidates via `ebur128` (`E9`).
- **What We Would Build Next:** Swap in the completed `outputs/wan_kaggle/` clips for `s02`, `s04`, `s05`, and `s07`, run a blind preference test (`E12`) comparing Ken Burns vs. Wan 2.2 with family members, and add Afaan Oromo narration alongside Amharic.
