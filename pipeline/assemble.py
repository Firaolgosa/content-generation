"""Stage: assembly. Everything from the storyboard, in code.

  --radio   narration over the placeholder bed on a black screen, with subtitles (the radio cut)
  default   picture for every shot, chosen score ducked under the voice, burned-in English
            subtitles, loudness-normalised, AI end card; exported 16:9 and 9:16

Outputs (outputs/final/): <slug>_16x9.mp4, <slug>_9x16.mp4, radio_cut.mp4, subtitles_en.srt,
timeline.json.

Run:  uv run python -m pipeline.assemble [--radio] [--aspect 16x9|9x16]
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Any

from pipeline import ffmpeg, mixdown, narration, overlays, storyboard, timeline, video
from pipeline.common import OUTPUTS, digest, log_event, rel, say, write_json

STAGE = "assemble"
FINAL = OUTPUTS / "final"
OVERLAY_DIR = OUTPUTS / "assembly" / "overlays"
RADIO_SIZE = {"width": 1280, "height": 720}


def slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s or "heritage-short"


def _subtitle_overlays(cues: list[timeline.Cue], size: dict[str, int]) -> list[video.Overlay]:
    """Render each cue (cheap, always fresh) and place it in its time window."""
    w, h = size["width"], size["height"]
    out = []
    for c in cues:
        png = OVERLAY_DIR / f"{w}x{h}" / f"sub_{digest({'t': c.text, 'w': w, 'h': h, 'v': 3})}.png"
        path, x, y = overlays.render_subtitle(c.text, w, h, png)
        out.append(video.Overlay(path, c.start, c.end, x, y))
    return out


def _end_card(sb: dict[str, Any], size: dict[str, int]) -> Path:
    w, h = size["width"], size["height"]
    lines = sb["end_card"]["lines"]
    png = OVERLAY_DIR / f"{w}x{h}" / f"endcard_{digest({'l': lines, 'w': w, 'h': h, 'v': 2})}.png"
    if not png.exists():
        overlays.render_end_card(lines, w, h, png)
    return png


def _metadata(sb: dict[str, Any]) -> dict[str, str]:
    m = sb["models"]
    return {
        "title": sb["title"],
        "comment": (f"Made with AI. Narration {m['tts']}; images {m['image']}; "
                    f"motion {m['video']}; music {m['music']}; assembled with FFmpeg."),
        "language": sb["language"],
    }


def _timed(label: str, fn: Any, *args: Any) -> Any:
    started = time.perf_counter()
    result = fn(*args)
    log_event({"stage": STAGE, "item": label, "provider": "ffmpeg", "status": "ok",
               "latency_s": round(time.perf_counter() - started, 3)})
    return result


def plan(sb: dict[str, Any]) -> tuple[list[timeline.Segment], list[timeline.Cue], float]:
    segments = timeline.build(sb, narration.durations(sb))
    cues = timeline.subtitle_cues(sb, segments)
    length = timeline.film_length(segments, sb)
    FINAL.mkdir(parents=True, exist_ok=True)
    (FINAL / "subtitles_en.srt").write_text(timeline.to_srt(cues), encoding="utf-8")
    write_json(FINAL / "timeline.json", {
        "length_s": length,
        "segments": [s.__dict__ for s in segments],
        "subtitles": [c.__dict__ for c in cues],
    })
    return segments, cues, length


def radio_cut(sb: dict[str, Any]) -> Path:
    say(f"[{STAGE}] radio cut")
    segments, cues, length = plan(sb)
    narr = mixdown.narration_track(sb, segments)
    bed, _ = mixdown.music_track(sb, segments, force_placeholder=True)
    audio = mixdown.final_mix(sb, narr, bed)
    ec = sb["end_card"]["duration_s"]
    over = [*_subtitle_overlays(cues, RADIO_SIZE),
            video.Overlay(_end_card(sb, RADIO_SIZE), length - ec, length)]
    fps = sb["render"]["fps"]
    base = ["-f", "lavfi", "-i",
            f"color=c=black:s={RADIO_SIZE['width']}x{RADIO_SIZE['height']}:r={fps}:d={length}"]
    out = _timed("radio_cut", video.finish, base, audio, over, length, fps,
                 FINAL / "radio_cut.mp4", _metadata(sb))
    say(f"  -> {rel(out)} ({length:.1f}s)")
    return out


def film(sb: dict[str, Any], aspects: list[str]) -> list[Path]:
    say(f"[{STAGE}] film {', '.join(aspects)}")
    segments, cues, length = plan(sb)
    narr = mixdown.narration_track(sb, segments)
    bed, sources = mixdown.music_track(sb, segments)
    for s in sources:
        if s["placeholder"]:
            say(f"  ! music cue {s['cue']}: no chosen candidate, using the placeholder bed")
    audio = mixdown.final_mix(sb, narr, bed)
    by_id = {s["id"]: s for s in sb["shots"]}
    fps = sb["render"]["fps"]
    outputs = []
    for aspect in aspects:
        size = sb["render"]["horizontal" if aspect == "16x9" else "vertical"]
        parts = [video.shot_segment(sb, by_id[seg.shot_id], seg, size) for seg in segments]
        parts.append(video.card_segment(_end_card(sb, size), sb["end_card"]["duration_s"], size, fps))
        picture = video.concat(parts, video.DIR / f"picture_{aspect}.mp4")
        out = FINAL / f"{slug(sb['title'])}_{aspect}.mp4"
        _timed(f"film_{aspect}", video.finish, ["-i", str(picture)], audio,
               _subtitle_overlays(cues, size), length, fps, out, _metadata(sb))
        say(f"  -> {rel(out)} ({ffmpeg.duration(out):.1f}s)")
        outputs.append(out)
    return outputs


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--radio", action="store_true", help="radio cut only")
    ap.add_argument("--aspect", choices=["16x9", "9x16"], help="render one aspect only")
    args = ap.parse_args(argv)
    ffmpeg.require()
    sb = storyboard.load()
    if args.radio:
        radio_cut(sb)
    else:
        film(sb, [args.aspect] if args.aspect else ["16x9", "9x16"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
