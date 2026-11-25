"""Picture: one normalised segment per shot and aspect, end card, concat, subtitle burn-in.

A shot segment comes from its Wan clip when one exists, otherwise from a Ken Burns move over
the keyframe (FFmpeg zoompan). Segments are cached by hash of their inputs and the exact
duration, so a narration edit re-renders only the shot whose length changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline import ffmpeg, keyframes, shots
from pipeline.common import OUTPUTS, digest, file_digest
from pipeline.timeline import Segment

DIR = OUTPUTS / "assembly"
KB_ZOOM = 0.10  # Ken Burns travel
KB_STATIC_ZOOM = 0.02  # "static" still breathes a little so it does not look frozen
WAN_TRIM_HEAD_S = 0.25  # first frames of generated clips are often weak
WAN_MAX_STRETCH = 1.6  # slow a short clip down at most this much, then hold the last frame
X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]

EASE = "(3*pow(on/{n},2)-2*pow(on/{n},3))"


def kenburns_expr(camera: str, frames: int) -> tuple[str, str, str]:
    """zoompan (z, x, y) expressions for a camera move, eased in and out."""
    e = EASE.format(n=max(frames - 1, 1))
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    z_travel = f"1+{KB_ZOOM}"
    moves = {
        "push_in": (f"1+{KB_ZOOM}*{e}", cx, cy),
        "pull_out": (f"1+{KB_ZOOM}*(1-{e})", cx, cy),
        "pan_left": (z_travel, f"(iw-iw/zoom)*(1-{e})", cy),
        "pan_right": (z_travel, f"(iw-iw/zoom)*{e}", cy),
        "tilt_up": (z_travel, cx, f"(ih-ih/zoom)*(1-{e})"),
        "tilt_down": (z_travel, cx, f"(ih-ih/zoom)*{e}"),
        "static": (f"1+{KB_STATIC_ZOOM}*{e}", cx, cy),
    }
    return moves[camera]


def frame_filter(w: int, h: int, mode: str, focus_x: float) -> str:
    """Fill a WxH frame from any source: crop at focus_x, or fit over a blurred copy."""
    if mode == "fit_blur":
        return (f"split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                f"boxblur=20:2,eq=brightness=-0.06[bg];[b]scale={w}:-2[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2")
    return (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h}:x=(iw-{w})*{focus_x}:y=(ih-{h})/2")


def _framing(shot: dict[str, Any], vertical: bool) -> tuple[str, float]:
    if not vertical:
        return "crop", 0.5
    return shot.get("vertical_mode", "crop"), shot.get("vertical_focus_x", 0.5)


def shot_segment(sb: dict[str, Any], shot: dict[str, Any], seg: Segment, size: dict[str, int]
                 ) -> Path:
    w, h, fps = size["width"], size["height"], sb["render"]["fps"]
    vertical = h > w
    mode, fx = _framing(shot, vertical)
    clip = shots.resolve_clip(sb, shot)
    still = keyframes.resolve(sb, shot)
    if clip is None and still is None:
        raise FileNotFoundError(f"{shot['id']}: no keyframe or clip; run the keyframes stage")
    src = clip or still
    key = digest({"src": file_digest(src), "dur": seg.duration, "w": w, "h": h, "fps": fps,
                  "mode": mode, "fx": fx, "camera": shot["camera"], "v": 3})
    out = DIR / f"{w}x{h}" / f"{shot['id']}_{key}.mp4"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    frames = max(int(round(seg.duration * fps)), 1)
    if clip is not None:
        clip_s = max(ffmpeg.duration(clip) - WAN_TRIM_HEAD_S, 0.5)
        stretch = min(max(seg.duration / clip_s, 1.0), WAN_MAX_STRETCH)
        graph = (f"[0:v]trim=start={WAN_TRIM_HEAD_S},setpts=(PTS-STARTPTS)*{stretch:.4f},"
                 f"fps={fps},{frame_filter(w, h, mode, fx)},"
                 f"tpad=stop_mode=clone:stop_duration={seg.duration},setsar=1[v]")
        args = ["-i", str(clip)]
    else:
        z, x, y = kenburns_expr(shot["camera"], frames)
        graph = (f"[0:v]{frame_filter(w * 2, h * 2, mode, fx)},"
                 f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},setsar=1[v]")
        args = ["-i", str(still)]
    ffmpeg.run([*args, "-filter_complex", graph, "-map", "[v]", "-frames:v", str(frames),
                "-r", str(fps), *X264, "-an", str(out)], desc=f"segment {shot['id']} {w}x{h}")
    return out


def card_segment(card_png: Path, seconds: float, size: dict[str, int], fps: int) -> Path:
    w, h = size["width"], size["height"]
    key = digest({"png": file_digest(card_png), "s": seconds, "w": w, "h": h, "fps": fps})
    out = DIR / f"{w}x{h}" / f"endcard_{key}.mp4"
    if out.exists():
        return out
    frames = int(round(seconds * fps))
    ffmpeg.run(["-loop", "1", "-framerate", str(fps), "-i", str(card_png), "-vf",
                f"scale={w}:{h},fade=t=in:st=0:d=0.6,setsar=1", "-frames:v", str(frames),
                "-r", str(fps), *X264, "-an", str(out)], desc="end card")
    return out


def concat(parts: list[Path], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    listing = out.with_suffix(".txt")
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    ffmpeg.run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)],
               desc="concat")
    return out


@dataclass(frozen=True)
class Overlay:
    """A PNG shown from `start` to `end` seconds with its top-left corner at (x, y)."""

    png: Path
    start: float
    end: float
    x: int = 0
    y: int = 0


def finish(base_args: list[str], audio: Path, overlays: list[Overlay],
           length: float, fps: int, out: Path, metadata: dict[str, str]) -> Path:
    """Overlay timed PNGs (subtitles, end card) on the base video and mux the final audio."""
    inputs = [*base_args, "-i", str(audio)]
    chain = []
    last = "0:v"
    for i, o in enumerate(overlays):
        inputs += ["-loop", "1", "-framerate", str(fps), "-t", str(length), "-i", str(o.png)]
        tag = f"o{i}"
        chain.append(f"[{last}][{i + 2}:v]overlay={o.x}:{o.y}:"
                     f"enable='between(t,{o.start},{o.end})'[{tag}]")
        last = tag
    graph = ";".join(chain) if chain else "[0:v]null[o]"
    vout = last if chain else "o"
    meta: list[str] = []
    for k, v in metadata.items():
        meta += ["-metadata", f"{k}={v}"]
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run([*inputs, "-filter_complex", graph, "-map", f"[{vout}]", "-map", "1:a",
                "-t", str(length), "-r", str(fps), *X264, "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", *meta, str(out)], desc=f"finish {out.name}")
    return out
