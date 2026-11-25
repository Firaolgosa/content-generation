"""Pure timing logic: shot lengths cut to the voice, subtitle cues, music windows.

Professionals cut picture to the narration, so a shot lasts
max(planned duration, lead + narration + tail).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SUB_MAX_CHARS = 42  # per line
SUB_MAX_LINES = 2
SUB_MIN_CUE_S = 1.2


@dataclass(frozen=True)
class Segment:
    shot_id: str
    start: float
    duration: float
    narr_start: float  # absolute time the narration line begins
    narr_dur: float  # 0 when the shot has no narration

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str  # may contain one "\n"


def build(sb: dict[str, Any], narr_durations: dict[str, float]) -> list[Segment]:
    lead = sb["mix"]["narration_lead_s"]
    tail = sb["mix"]["narration_tail_s"]
    t = 0.0
    out: list[Segment] = []
    for shot in sb["shots"]:
        nd = narr_durations.get(shot["id"], 0.0)
        dur = max(shot["duration_s"], lead + nd + tail) if nd > 0 else shot["duration_s"]
        dur = round(dur, 3)
        out.append(Segment(shot["id"], round(t, 3), dur, round(t + lead, 3), nd))
        t += dur
    return out


def film_length(segments: list[Segment], sb: dict[str, Any]) -> float:
    return round((segments[-1].end if segments else 0.0) + sb["end_card"]["duration_s"], 3)


def wrap(text: str, width: int = SUB_MAX_CHARS) -> list[str]:
    """Greedy word wrap; a single over-long word stays on its own line."""
    lines: list[str] = []
    cur = ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    if cur:
        lines.append(cur)
    return lines


def chunk_subtitle(text: str) -> list[str]:
    """Split into cues of at most two wrapped lines, preferring sentence boundaries."""
    sentences = [s for s in re.split(r"(?<=[.!?;])\s+", text.strip()) if s]
    chunks: list[str] = []
    for sentence in sentences:
        lines = wrap(sentence)
        for i in range(0, len(lines), SUB_MAX_LINES):
            chunks.append("\n".join(lines[i : i + SUB_MAX_LINES]))
    # merge tiny neighbours when they still fit in two lines
    merged: list[str] = []
    for c in chunks:
        if merged:
            candidate = wrap(merged[-1].replace("\n", " ") + " " + c.replace("\n", " "))
            if len(candidate) <= SUB_MAX_LINES:
                merged[-1] = "\n".join(candidate)
                continue
        merged.append(c)
    return merged


def subtitle_cues(sb: dict[str, Any], segments: list[Segment]) -> list[Cue]:
    """Spread each shot's English subtitle over its narration, proportional to characters."""
    by_id = {s["id"]: s for s in sb["shots"]}
    cues: list[Cue] = []
    for seg in segments:
        text = by_id[seg.shot_id]["subtitle"].strip()
        if not text:
            continue
        span = seg.narr_dur if seg.narr_dur > 0 else max(seg.duration - 0.5, SUB_MIN_CUE_S)
        chunks = chunk_subtitle(text)
        total_chars = sum(len(c) for c in chunks) or 1
        t = seg.narr_start if seg.narr_dur > 0 else seg.start + 0.25
        for c in chunks:
            d = max(span * len(c) / total_chars, SUB_MIN_CUE_S)
            end = min(t + d, seg.end)
            cues.append(Cue(round(t, 3), round(end, 3), c))
            t = end
    return cues


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: list[Cue]) -> str:
    blocks = [f"{i}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n{c.text}\n"
              for i, c in enumerate(cues, 1)]
    return "\n".join(blocks)


def music_windows(sb: dict[str, Any], segments: list[Segment]) -> list[tuple[dict, float, float]]:
    """(cue, start, end) for each music cue; the last cue runs through the end card."""
    by_id = {s.shot_id: s for s in segments}
    length = film_length(segments, sb)
    cues = sb["music"]["cues"]
    out = []
    for i, cue in enumerate(cues):
        start = by_id[cue["from_shot"]].start
        end = by_id[cue["to_shot"]].end
        if i == len(cues) - 1:
            end = length
        out.append((cue, start, round(end, 3)))
    return out
