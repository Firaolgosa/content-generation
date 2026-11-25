"""Minimal FFmpeg/ffprobe wrappers. FFmpeg is deterministic, which is why assembly is pure code."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

STDERR_TAIL = 1500


class FFmpegError(RuntimeError):
    pass


def require() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise SystemExit(f"{tool} not found. Install FFmpeg (macOS: brew install ffmpeg; "
                             "Ubuntu: apt install ffmpeg).")


def run(args: list[str], *, desc: str) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise FFmpegError(f"ffmpeg failed ({desc}):\n{proc.stderr[-STDERR_TAIL:]}")


def run_capture(args: list[str], *, desc: str) -> str:
    """Run ffmpeg and return stderr (used by loudnorm measurement pass)."""
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise FFmpegError(f"ffmpeg failed ({desc}):\n{proc.stderr[-STDERR_TAIL:]}")
    return proc.stderr


def duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise FFmpegError(f"ffprobe failed on {path}: {proc.stderr[-300:]}")
    return float(json.loads(proc.stdout)["format"]["duration"])


def parse_loudnorm_json(stderr: str) -> dict[str, str]:
    """Extract the JSON block loudnorm prints with print_format=json."""
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start < 0 or end < start:
        raise FFmpegError("loudnorm produced no measurement JSON")
    return json.loads(stderr[start : end + 1])
