# Engineering Report — *The Night in Bekoji* 

**Assignment:** B2W0: AI-Content Generation — Codebase and Report
**Repository:** `<INSERT YOUR PUBLIC GITHUB URL>`
**Film Outputs:** `outputs/final/the-night-in-bekoji_9x16.mp4` (vertical) and `the-night-in-bekoji_16x9.mp4` (horizontal), `75.0s`, `-14 LUFS`

---

## 1. What We Set Out to Make and For Whom

We set out to build **The Night in Bekoji ** — a 75-second heritage short film, narrated in Amharic with English subtitles, with an original AI-composed score, generated entirely from code.

**The story** is personal and true. In 1950 E.C., in the small highland town of Bekoji, my grandfather and his friend were on a journey to visit another girl when night fell. They stopped at a roadside home asking for shelter. Inside, by the warmth of a wood fire, my grandfather met my grandmother — then just 17 years old — for the first time. By morning, he chose her over his original journey. That decision is where our entire family begins.

**Who it is for:** My family — parents, aunts, uncles, and cousins — who watch on their phones in our family group chat. The primary format is **9:16 vertical** (phone-first), because that is how they consume video. The goal was for them to feel warmth, pride, and nostalgia: to see, as if for the first time, the night their grandparents' story began.

**Why AI:** The story has no photographs. The night happened over 70 years ago in rural Ethiopia. The only way to give it images is to generate them. AI allowed us to create painterly, stylized illustrations of characters who never existed in any archive, with Amharic narration synthesized without hiring a voice actor, and music composed without a studio — all within a free-tier budget of effectively **$0**.

---

## 2. Pipeline Architecture and Reproducibility

The entire pipeline is driven by a single human-readable contract: `storyboard.json`. Every stage reads from it, hashes its inputs, and writes deterministic outputs — meaning a re-run only regenerates what changed.

**The six stages:**

1. **Validate** (`pipeline.storyboard`): Checks the JSON schema, shot durations, and the `ETHICS.md` consent gate before any API call is made.
2. **Narrate** (`pipeline.narration`): Synthesizes 9 Amharic WAV files via Gemini TTS (`gemini-3.8-flash-tts`, voice: `Sulafat`).
3. **Draw** (`pipeline.keyframes`): Generates a golden style reference frame and two character reference sheets (grandfather, grandmother) via Cloudflare Workers AI (`flux-2-klein-4b`), then conditions all 9 shot keyframes on them.
4. **Animate** (`pipeline.shots` + `pipeline.kaggle_jobs`): Submits Wan 2.2 TI2V-5B image-to-video jobs to Kaggle T4 GPUs for the 4 motion-critical shots (`s02`, `s04`, `s05`, `s07`), with a **Ken Burns** (pan-and-zoom) fallback for all other shots — and for any GPU shot that has not yet returned.
5. **Score** (`pipeline.music`): Generates 3 ACE-Step 1.5 music candidates on Kaggle and uses the selected one (`c2`, seed 4244, −16.2 LUFS).
6. **Assemble** (`pipeline.assemble`): Cuts shots to narration timing, ducks the score under voice using FFmpeg side-chain compression, renders Amharic subtitles and an AI end card as PNG overlays via Pillow, normalises to −14 LUFS, and exports both 16:9 and 9:16 MP4s.

Every model call, cache hit, and failure is logged to `runs.jsonl`. Total list-price equivalent: **$0.0351**. Actual spend: **$0** (all free tiers). The test suite passes with **59 tests** and `ruff` reports no linting errors.

---

## 3. What We Learned From Our Audience

We ran two user tests: one on the radio cut (narration-only, no images) and one on the near-final visual rough cut.

**User Test 1 — Radio Cut (`run_id: 20261125T125406Z-2802`, 75 seconds):**

- *Family member*: "In the keyframe for shot seven, the boy's neck is cut off — his head doesn't appear fully in frame." → Updated the image prompt to explicitly show the full head, face, and shoulders; regenerated the shot with a new seed. The artifact disappeared completely.
- *Family member*: "The image of my grandmother looks too old — at the time of this story she was only 17 years old." → Removed the word "grandmother" from all image prompts (the model was biasing toward an older face from that word alone), rewrote the character description to "17-year-old Ethiopian teenage girl", and regenerated the character reference sheet plus all affected shots (`s04`, `s06`, `s07`, `s08`).
- *Family member*: "The narration feels warm and real, like someone is telling us the story in person — it brought tears." → No change needed. This confirmed the Amharic `Sulafat` TTS voice and the pacing of the narration were right.

**User Test 2 — Visual Rough Cut (`the-night-in-bekoji_9x16.mp4`, `run_id: 20261126T074027Z-88f1`):**

1. **Shot 7 anatomy artifact:** The head-cut issue from the radio cut test was confirmed fixed in the new keyframe.
2. **Grandmother age confirmed:** The regenerated character — described as a 17-year-old — read clearly and naturally as a young woman. Viewers accepted the change.
3. **Score feedback:** A family member noted the background music did not feel like a traditional Ethiopian highland evening. This was logged as a future improvement: the ACE-Step prompt would be updated to emphasise traditional instruments (krar, masenqo) and a slower, more intimate tempo.

---

## 4. The Hardest Problem and How We Solved It

Two genuine production blockers stood out.

**Problem 1 — Wan 2.2 ran out of GPU memory on Kaggle (Failure F8):**
All four Wan 2.2 image-to-video jobs crashed with a CUDA out-of-memory error on the Kaggle Tesla T4. The model needed 14.28 GiB; the GPU only had 14.56 GiB free, leaving no headroom for PyTorch's allocator. The fix had three parts: switching to `enable_sequential_cpu_offload()` (which pages model weights through RAM rather than holding everything on VRAM), enabling `vae.enable_slicing()` to process the video decoder one frame at a time, and setting `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` to reduce fragmentation. We also reduced the draft from 121 frames to 81 (keeping 24 denoising steps). Crucially, because Kaggle GPU queues also ran 30+ minutes per job, we decoupled the video generation from the edit loop entirely: Wan 2.2 jobs run asynchronously in the background, their outputs land in `outputs/wan_kaggle/`, and the edit always runs with Ken Burns as a fast, deterministic local fallback. This meant audience feedback could be incorporated immediately without waiting for a GPU.

**Problem 2 — API authentication mismatches (Failures F6 and F7):**
Cloudflare's `flux-1-schnell` model rejected the `seed` field in the request body with a 400 error (code 5006) — a schema constraint not documented at the time. The Kaggle CLI also refused authentication because `KGAT_`-prefixed tokens must be passed as `KAGGLE_API_TOKEN`, not `KAGGLE_KEY`. Both were caught through live smoke testing, fixed in `pipeline/providers/cloudflare.py` and `pipeline/kaggle_jobs.py`, and confirmed by the full 59-test suite.

---

## 5. Suggested Practices Tested Honestly

**The practice that helped more than expected — Hash-based caching keyed on `storyboard.json`:**

Before this project, caching felt like premature optimisation. After audience feedback in User Test 1 required fixing shot 7 and re-aging the grandmother character, we re-ran `pipeline.keyframes` and watched it regenerate only the five affected outputs (`char-grandmother`, `s04`, `s06`, `s07`, `s08`) while leaving the other four shots and all nine narration WAVs completely untouched. That saved quota, time, and the risk of introducing new variation into shots that were already good. Caching is not a nice-to-have — it is what makes an AI pipeline iterable.

**The practice that did not work as expected — Treating cloud GPU generation as a synchronous step:**

The plan was to run Wan 2.2 on Kaggle and use the resulting video clips directly in each edit. In practice, Kaggle GPU queues took 30 minutes or more per submission, and four of the jobs crashed with out-of-memory errors before producing anything. Treating the GPU render as a blocking step made every feedback loop painfully slow. The better pattern — which we adopted — is to treat cloud GPU generation as an asynchronous background job: submit it, get on with the edit using a local fallback, and pull the GPU result in whenever it arrives. The pipeline now supports this natively via `pipeline.kaggle_jobs pull`.

---

## 6. Ceiling Work and What We Would Build Next

**Ceiling work completed beyond the core requirements:**

- Built `--dest` support in `pipeline/kaggle_jobs.py` so Wan 2.2 renders can be pulled into a separate folder (`outputs/wan_kaggle/`) without overwriting the working edit — enabling non-blocking asynchronous GPU rendering.
- Built a fully portable Pillow-based subtitle and end-card renderer (`pipeline/overlays.py`) that generates Ethiopic text overlays as PNG frames, working around the absence of `libass` and `freetype` in Homebrew FFmpeg. The pipeline now works on any macOS or Linux machine without recompiling FFmpeg.
- Measured all three ACE-Step score candidates using FFmpeg's `ebur128` integrated loudness filter (`Experiment E9`) to make music selection objective rather than subjective — `c2` scored −16.2 LUFS with an LRA of 8.9 LU, the most balanced of the three.
- Documented every model call, cache hit, failure, and audience-driven change across `runs.jsonl`, `EXPERIMENTS.md` (11 experiments), `FAILURES.md` (8 failures), and `DESIGN.md`.

**What we would build next:**

1. **Swap in the Wan 2.2 motion clips** for the four Ken Burns shots (`s02`, `s04`, `s05`, `s07`) once the Kaggle renders complete, then run a blind preference test (Experiment E12) with family members comparing motion video vs. still pan-and-zoom.
2. **Improve the score** by updating the ACE-Step prompt to emphasise traditional Ethiopian instruments — krar (lyre), masenqo (single-string fiddle), and kebero (drum) — and a slower, more intimate tempo in response to the User Test 2 music feedback.
3. **Add Afaan Oromo narration** as a second audio track, since Bekoji is in Oromia and many family members speak Oromo as their first language.
4. **Publish the pipeline as a template** so other members of the Ethiopian diaspora can generate their own family heritage films by editing only `storyboard.json` and `story/brief.md`.
