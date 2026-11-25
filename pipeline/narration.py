"""Stage: narration. One WAV per shot via Gemini TTS, cached by (text, model, voice, style).

Run:  uv run python -m pipeline.narration [--only s03,s04]
"""

from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path
from typing import Any

from pipeline import storyboard
from pipeline.common import (
    OUTPUTS,
    CallSpec,
    atomic_write_bytes,
    call_logged,
    digest,
    log_cache_hit,
    say,
)
from pipeline.providers import gemini

STAGE = "narration"
DIR = OUTPUTS / "narration"


def cache_key(sb: dict[str, Any], shot: dict[str, Any]) -> str:
    v = sb["voice"]
    return digest({"text": shot["narration"].strip(), "model": sb["models"]["tts"],
                   "voice": v["voice"], "style": v["style"]})


def path_for(sb: dict[str, Any], shot: dict[str, Any]) -> Path | None:
    if not shot["narration"].strip():
        return None
    return DIR / f"{shot['id']}_{cache_key(sb, shot)}.wav"


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def durations(sb: dict[str, Any]) -> dict[str, float]:
    """Narration length per shot id, from cached WAVs. Missing files raise."""
    out: dict[str, float] = {}
    for shot in sb["shots"]:
        p = path_for(sb, shot)
        if p is None:
            continue
        if not p.exists():
            raise FileNotFoundError(f"narration for {shot['id']} missing; run the narration stage")
        out[shot["id"]] = wav_seconds(p)
    return out


def generate_one(sb: dict[str, Any], shot: dict[str, Any]) -> Path | None:
    out = path_for(sb, shot)
    if out is None:
        return None
    v = sb["voice"]
    spec = CallSpec(stage=STAGE, provider="gemini", model=sb["models"]["tts"], item=shot["id"],
                    params={"voice": v["voice"], "style": v["style"], "chars": len(shot["narration"])},
                    cache_key=cache_key(sb, shot))
    if out.exists():
        log_cache_hit(spec, out)
        return out

    def call() -> Path:
        wav = gemini.tts(shot["narration"].strip(), model=sb["models"]["tts"],
                         voice=v["voice"], style=v["style"])
        return atomic_write_bytes(out, wav)

    call_logged(spec, call, describe=lambda p: {"output": p, "audio_s": round(wav_seconds(p), 3),
                                                 "cost_usd": 0.0})
    say(f"  narration {shot['id']}: {wav_seconds(out):.1f}s")
    return out


def run(sb: dict[str, Any], only: set[str] | None = None) -> dict[str, Path]:
    say(f"[{STAGE}] {sb['models']['tts']} voice={sb['voice']['voice']}")
    results: dict[str, Path] = {}
    for shot in sb["shots"]:
        if only and shot["id"] not in only:
            continue
        p = generate_one(sb, shot)
        if p:
            results[shot["id"]] = p
    return results


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="comma-separated shot ids")
    args = ap.parse_args(argv)
    sb = storyboard.load()
    run(sb, set(args.only.split(",")) if args.only else None)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
