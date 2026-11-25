"""One command for the whole pipeline: validate -> narration -> keyframes -> shots -> music -> assemble.

Every stage is cached by a hash of its inputs, so a re-run only regenerates what changed.
Wan clips and ACE-Step candidates are rendered on Kaggle (`make kaggle-wan`,
`make kaggle-music`); this command uses whichever exist and falls back to Ken Burns moves and
the placeholder bed for the rest, so it always produces a film.

Run:  uv run python -m pipeline.run [--radio]
"""

from __future__ import annotations

import argparse
import sys
import time

from pipeline import assemble, ffmpeg, keyframes, music, narration, shots, storyboard
from pipeline.common import RUN_ID, log_event, say


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--radio", action="store_true", help="stop after the radio cut")
    args = ap.parse_args(argv)
    ffmpeg.require()
    started = time.perf_counter()
    sb = storyboard.load()
    for w in storyboard.warnings(sb):
        say(f"warning  {w}")
    say(f"run {RUN_ID}: {sb['title']} ({len(sb['shots'])} shots)")

    narration.run(sb)
    if args.radio:
        assemble.radio_cut(sb)
    else:
        keyframes.run(sb)
        shots.run(sb)
        music.run(sb)
        assemble.film(sb, ["16x9", "9x16"])
    total = round(time.perf_counter() - started, 1)
    log_event({"stage": "pipeline", "item": "radio" if args.radio else "film", "status": "ok",
               "provider": "local", "latency_s": total})
    say(f"done in {total}s  (see runs.jsonl for every call, run_id={RUN_ID})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
