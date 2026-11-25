"""Audio: narration track, music bed, ducking and loudness. Pure FFmpeg, cached by input hashes.

Order follows post-production practice: build the voice track, build the music bed, bring
each to a similar loudness, duck the music under the voice (sidechaincompress), then a
two-pass loudnorm to the delivery target (about -14 LUFS, true peak -1 dB).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline import ffmpeg, music, narration
from pipeline.common import OUTPUTS, digest, file_digest, log_event, rel, say
from pipeline.timeline import Segment, film_length, music_windows

DIR = OUTPUTS / "assembly" / "audio"
SR = 48_000
PRE_LUFS = -16  # level both stems before mixing
FADE_IN_S = 1.5
FADE_OUT_S = 2.5
STEREO = f"aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo"


def _cached(out: Path, desc: str, args: list[str]) -> Path:
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run([*args, str(out)], desc=desc)
    return out


def narration_track(sb: dict[str, Any], segments: list[Segment]) -> Path:
    length = film_length(segments, sb)
    by_id = {s["id"]: s for s in sb["shots"]}
    placed = [(narration.path_for(sb, by_id[seg.shot_id]), seg.narr_start)
              for seg in segments if seg.narr_dur > 0]
    key = digest({"lines": [(file_digest(p), t) for p, t in placed], "len": length})
    out = DIR / f"narration_{key}.wav"
    if not placed:
        return _cached(out, "silent narration",
                       ["-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo", "-t", str(length)])
    inputs: list[str] = []
    chains = []
    for i, (p, t) in enumerate(placed):
        inputs += ["-i", str(p)]
        ms = int(round(t * 1000))
        chains.append(f"[{i}:a]{STEREO},adelay=delays={ms}:all=1[n{i}]")
    mix = "".join(f"[n{i}]" for i in range(len(placed)))
    graph = ";".join(chains) + (
        f";{mix}amix=inputs={len(placed)}:normalize=0:dropout_transition=0,"
        f"apad=whole_dur={length},atrim=0:{length},loudnorm=I={PRE_LUFS}:TP=-2:LRA=11,"
        f"aresample={SR}[out]")
    return _cached(out, "narration track",
                   [*inputs, "-filter_complex", graph, "-map", "[out]", "-c:a", "pcm_s16le"])


def placeholder_bed(seconds: float) -> Path:
    """A quiet, deterministic temp track: a soft open-fifth drone with slow tremolo."""
    secs = round(seconds + 1, 1)
    out = DIR / f"placeholder_bed_{digest({'s': secs, 'v': 2})}.wav"
    tones = [110.0, 164.81, 220.0, 277.18]
    inputs: list[str] = []
    for f in tones:
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={f}:sample_rate={SR}:duration={secs}"]
    mix = "".join(f"[{i}:a]" for i in range(len(tones)))
    graph = (f"{mix}amix=inputs={len(tones)}:normalize=1,tremolo=f=0.15:d=0.5,"
             f"lowpass=f=900,volume=0.6,{STEREO}[out]")
    return _cached(out, "placeholder bed",
                   [*inputs, "-filter_complex", graph, "-map", "[out]", "-c:a", "pcm_s16le"])


def music_track(sb: dict[str, Any], segments: list[Segment], force_placeholder: bool = False
                ) -> tuple[Path, list[dict[str, Any]]]:
    """Place each cue in its window with fades; returns the bed and which source each cue used."""
    length = film_length(segments, sb)
    windows = music_windows(sb, segments)
    sources = []
    paths: list[Path] = []
    for cue, start, end in windows:
        chosen = None if force_placeholder else music.chosen_path(sb, cue)
        src = chosen or placeholder_bed(end - start)
        paths.append(src)
        sources.append({"cue": cue["id"], "source": src.name, "placeholder": chosen is None,
                        "start": start, "end": end})
    key = digest({"src": [(file_digest(p), s["start"], s["end"]) for p, s in zip(paths, sources,
                                                                                    strict=True)],
                  "gain": sb["mix"]["music_gain_db"], "len": length})
    out = DIR / f"music_{key}.wav"
    inputs: list[str] = []
    chains = []
    for i, ((_cue, start, end), src) in enumerate(zip(windows, paths, strict=True)):
        inputs += ["-i", str(src)]
        w = round(end - start, 3)
        ms = int(round(start * 1000))
        chains.append(
            f"[{i}:a]{STEREO},atrim=0:{w},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={FADE_IN_S},afade=t=out:st={max(w - FADE_OUT_S, 0)}:d={FADE_OUT_S},"
            f"adelay=delays={ms}:all=1[m{i}]")
    mix = "".join(f"[m{i}]" for i in range(len(windows)))
    graph = ";".join(chains) + (
        f";{mix}amix=inputs={len(windows)}:normalize=0:dropout_transition=0,"
        f"apad=whole_dur={length},atrim=0:{length},loudnorm=I={PRE_LUFS}:TP=-2:LRA=11,"
        f"aresample={SR},volume={sb['mix']['music_gain_db']}dB[out]")
    _cached(out, "music bed", [*inputs, "-filter_complex", graph, "-map", "[out]",
                               "-c:a", "pcm_s16le"])
    return out, sources


def final_mix(sb: dict[str, Any], narr: Path, bed: Path) -> Path:
    """Duck the bed under the voice, then two-pass loudnorm to the delivery target."""
    d, ln = sb["mix"]["duck"], sb["mix"]["loudness"]
    key = digest({"n": file_digest(narr), "m": file_digest(bed), "duck": d, "loud": ln})
    out = DIR / f"final_{key}.wav"
    if out.exists():
        return out
    pre = (f"[0:a]asplit=2[sc][voice];[1:a][sc]sidechaincompress=threshold={d['threshold']}:"
           f"ratio={d['ratio']}:attack={d['attack_ms']}:release={d['release_ms']}[duck];"
           f"[duck][voice]amix=inputs=2:normalize=0[mix]")
    target = f"I={ln['integrated_lufs']}:TP={ln['true_peak_db']}:LRA={ln['lra']}"
    measure = ffmpeg.run_capture(
        ["-i", str(narr), "-i", str(bed), "-filter_complex",
         f"{pre};[mix]loudnorm={target}:print_format=json[out]", "-map", "[out]", "-f", "null", "-"],
        desc="loudnorm measure")
    m = ffmpeg.parse_loudnorm_json(measure)
    apply = (f"{pre};[mix]loudnorm={target}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
             f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
             f"offset={m['target_offset']}:linear=true,aresample={SR}[out]")
    _cached(out, "final mix", ["-i", str(narr), "-i", str(bed), "-filter_complex", apply,
                               "-map", "[out]", "-c:a", "pcm_s16le"])
    log_event({"stage": "assemble", "item": "audio_mix", "provider": "ffmpeg", "status": "ok",
               "measured_input_lufs": m["input_i"], "measured_input_tp": m["input_tp"],
               "target": ln, "output": rel(out)})
    say(f"  audio: input {m['input_i']} LUFS -> {ln['integrated_lufs']} LUFS")
    return out
