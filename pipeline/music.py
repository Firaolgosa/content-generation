"""Stage: music. ACE-Step 1.5 candidates per cue, rendered on Kaggle (pipeline/kaggle_jobs.py).

Each cue in storyboard.music.cues asks for N candidates (seed, seed+1, ...). You listen,
set `chosen` to the index you keep and write the reason (and an EXPERIMENTS.md entry).
Until a candidate is chosen, assembly uses a quiet generated placeholder bed (the "temp track").

The requested duration is bucketed from *planned* shot lengths, not narration timing, so
re-timing one narration line never invalidates the score.

Run:  uv run python -m pipeline.music
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

from pipeline import storyboard
from pipeline.common import OUTPUTS, CallSpec, digest, log_cache_hit, say, write_json

STAGE = "music"
DIR = OUTPUTS / "music"
JOBS = DIR / "jobs.json"
HEADROOM_S = 15
BUCKET_S = 10


def requested_duration(sb: dict[str, Any], cue: dict[str, Any]) -> int:
    ids = [s["id"] for s in sb["shots"]]
    a, b = ids.index(cue["from_shot"]), ids.index(cue["to_shot"])
    planned = sum(s["duration_s"] for s in sb["shots"][a : b + 1])
    if cue is sb["music"]["cues"][-1]:
        planned += sb["end_card"]["duration_s"]
    return int(math.ceil((planned + HEADROOM_S) / BUCKET_S) * BUCKET_S)


def cue_key(sb: dict[str, Any], cue: dict[str, Any]) -> str:
    return digest({"caption": cue["caption"].strip(), "bpm": cue["bpm"],
                   "keyscale": cue["keyscale"], "seed": cue["seed"],
                   "duration": requested_duration(sb, cue), "model": sb["models"]["music"]})


def candidate_path(sb: dict[str, Any], cue: dict[str, Any], index: int) -> Path:
    return DIR / f"{cue['id']}_{cue_key(sb, cue)}_c{index}.wav"


def chosen_path(sb: dict[str, Any], cue: dict[str, Any]) -> Path | None:
    """The chosen candidate if one is chosen and present; None means placeholder bed."""
    idx = cue.get("chosen")
    if idx is None:
        return None
    p = candidate_path(sb, cue, idx)
    return p if p.exists() else None


def pending_jobs(sb: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = []
    for cue in sb["music"]["cues"]:
        key = cue_key(sb, cue)
        for i in range(cue["candidates"]):
            out = candidate_path(sb, cue, i)
            spec = CallSpec(stage=STAGE, provider="kaggle", model=sb["models"]["music"],
                            item=f"{cue['id']}#c{i}", seed=cue["seed"] + i, cache_key=key)
            if out.exists():
                log_cache_hit(spec, out)
                continue
            jobs.append({
                "cue_id": cue["id"], "key": key, "candidate": i, "output": out.name,
                "caption": cue["caption"].strip(), "bpm": cue["bpm"], "keyscale": cue["keyscale"],
                "duration": requested_duration(sb, cue), "seed": cue["seed"] + i,
                "model": sb["models"]["music"],
            })
    return jobs


def run(sb: dict[str, Any]) -> list[dict[str, Any]]:
    say(f"[{STAGE}] {sb['models']['music']} on Kaggle; placeholder bed until a candidate is chosen")
    jobs = pending_jobs(sb)
    write_json(JOBS, {"jobs": jobs})
    for cue in sb["music"]["cues"]:
        chosen = chosen_path(sb, cue)
        state = f"chosen c{cue['chosen']}" if chosen else (
            "chosen candidate missing!" if cue.get("chosen") is not None else "placeholder bed")
        say(f"  cue {cue['id']}: {cue['candidates']} candidate(s), "
            f"{requested_duration(sb, cue)}s requested, {state}")
    if jobs:
        say(f"  {len(jobs)} candidate(s) pending -> `make kaggle-music`")
    return jobs


def main(argv: list[str]) -> int:  # noqa: ARG001
    run(storyboard.load())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
