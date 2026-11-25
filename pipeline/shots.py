"""Stage: moving shots.

Shots marked `video: "wan"` get an image-to-video clip from Wan 2.2 TI2V-5B, which runs on
a Kaggle GPU (see pipeline/kaggle_jobs.py). This stage:
  - computes each shot's clip cache key = hash(keyframe bytes, motion prompt, seed, Wan params),
  - lists the clips that already exist in outputs/wan/ (cache hits),
  - writes outputs/wan/jobs.json with only the missing clips, for the Kaggle kernel.
Shots without a clip (Ken Burns by choice, or Wan not run yet / failed) are animated from the
still in FFmpeg during assembly, so the film always renders.

Run:  uv run python -m pipeline.shots
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pipeline import keyframes, storyboard
from pipeline.common import OUTPUTS, CallSpec, digest, file_digest, log_cache_hit, say, write_json

STAGE = "shots"
WAN_DIR = OUTPUTS / "wan"
JOBS = WAN_DIR / "jobs.json"


def clip_key(sb: dict[str, Any], shot: dict[str, Any], keyframe: Path) -> str:
    wan = sb["render"]["wan"]
    return digest({"keyframe": file_digest(keyframe), "motion": shot["motion_prompt"].strip(),
                   "seed": shot["seed"], "wan": wan, "model": sb["models"]["video"]})


def clip_path(sb: dict[str, Any], shot: dict[str, Any]) -> Path | None:
    kf = keyframes.resolve(sb, shot)
    if kf is None:
        return None
    return WAN_DIR / f"{shot['id']}_{clip_key(sb, shot, kf)}.mp4"


def resolve_clip(sb: dict[str, Any], shot: dict[str, Any]) -> Path | None:
    """The Wan clip for this shot if it was requested and exists; None means Ken Burns."""
    if shot["video"] != "wan":
        return None
    p = clip_path(sb, shot)
    return p if p and p.exists() else None


def pending_jobs(sb: dict[str, Any]) -> list[dict[str, Any]]:
    wan = sb["render"]["wan"]
    jobs = []
    for shot in sb["shots"]:
        if shot["video"] != "wan":
            continue
        kf = keyframes.resolve(sb, shot)
        if kf is None:
            say(f"  ! {shot['id']}: no keyframe yet; run the keyframes stage first")
            continue
        key = clip_key(sb, shot, kf)
        out = WAN_DIR / f"{shot['id']}_{key}.mp4"
        spec = CallSpec(stage=STAGE, provider="kaggle", model=sb["models"]["video"],
                        item=shot["id"], seed=shot["seed"], cache_key=key)
        if out.exists():
            log_cache_hit(spec, out)
            continue
        jobs.append({
            "shot_id": shot["id"], "key": key, "keyframe": kf.name, "output": out.name,
            "prompt": shot["motion_prompt"].strip(), "negative": wan.get("negative", ""),
            "seed": shot["seed"], "width": wan["width"], "height": wan["height"],
            "num_frames": wan["num_frames"], "steps": wan["steps"], "guidance": wan["guidance"],
            "fps": sb["render"]["fps"], "model": sb["models"]["video"],
        })
    return jobs


def run(sb: dict[str, Any]) -> list[dict[str, Any]]:
    say(f"[{STAGE}] {sb['models']['video']} on Kaggle; Ken Burns fallback in assembly")
    jobs = pending_jobs(sb)
    write_json(JOBS, {"jobs": jobs})
    wan_shots = [s["id"] for s in sb["shots"] if s["video"] == "wan"]
    ready = [s["id"] for s in sb["shots"] if resolve_clip(sb, s)]
    say(f"  wan requested: {len(wan_shots)}  ready: {len(ready)}  pending: {len(jobs)}")
    if jobs:
        say("  pending clips listed in outputs/wan/jobs.json -> `make kaggle-wan` to render them; "
            "until then those shots use Ken Burns")
    return jobs


def main(argv: list[str]) -> int:  # noqa: ARG001
    run(storyboard.load())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
