# Costs and measurements

Actual spend is **$0**: every service is a free tier, used from Ethiopia without a payment
card. Below are the free-tier limits as checked on 2026-11-25, and the measured cost per
stage generated from `runs.jsonl` by `make costs`.

## Free tiers as found

| Service | Used for | Free allowance (checked 2026-11-25) | List price if paid |
|---|---|---|---|
| Gemini API (AI Studio key) | text, TTS | Free tier, rate-limited per model. TODO: record the RPM/RPD shown in AI Studio for gemini-3.8-flash and gemini-3.8-flash-tts | TODO: from ai.google.dev pricing |
| Cloudflare Workers AI | FLUX keyframes | 10,000 neurons/day, reset at 00:00 UTC | $0.011 per 1,000 neurons |
| ↳ flux-2-klein-4b | | 26.05 neurons per output 512² tile + 5.37 per input tile, about 156 neurons for a 1536×864 keyframe without references | |
| ↳ flux-1-schnell | | 4.80 neurons per 512² tile + 9.60 per step, about 57 neurons for 1024², 4 steps | |
| Kaggle | Wan 2.2, ACE-Step | ~30 GPU hours/week (T4), phone verification, 12 h sessions | List-price proxy: GCP on-demand T4, about $0.35/h |

## Measured per stage

`latency` is wall-clock per successful call. `GPU min` comes from the Kaggle kernels'
own timing. The list-price equivalent uses the prices above.

<!-- costs:begin -->
_Run `make costs` after the first pipeline run to fill this table._
<!-- costs:end -->

## Notes

- Draft Wan at 832×480 and finish only the chosen shots at 1280×704 (see EXPERIMENTS E8).
- `cache_hit` lines cost nothing. The ratio of cache hits to calls on a re-run shows how much
  the caching saves.
