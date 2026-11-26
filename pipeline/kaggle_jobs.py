"""Run the GPU stages (Wan 2.2 clips, ACE-Step music) as Kaggle kernels, from the command line.

  push   <wan|music>   upload inputs (private dataset) + kernel; Kaggle starts it on a GPU
  status <wan|music>   print the kernel status
  pull   <wan|music>   download outputs into outputs/wan or outputs/music and merge the
                       kernel's own log lines (latency, GPU seconds) into runs.jsonl
  wait   <wan|music>   poll until the kernel finishes, then pull

The kernel reads jobs.json written by the shots/music stage, so it only renders clips whose
cache keys are missing locally. Credentials: KAGGLE_USERNAME / KAGGLE_KEY in .env.

Run:  uv run python -m pipeline.kaggle_jobs push wan
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from pipeline import keyframes, music, shots, storyboard
from pipeline.common import ROOT, log_event, rel, require_env, say, write_json

BUILD = ROOT / "build" / "kaggle"
POLL_S = 60
MAX_WAIT_S = 12 * 3600

KINDS: dict[str, dict[str, Any]] = {
    "wan": {"script": ROOT / "kaggle" / "wan_i2v.py", "kernel": "heritage-wan-i2v",
            "dataset": "heritage-wan-inputs", "jobs": shots.JOBS, "dest": shots.WAN_DIR,
            "ext": ".mp4"},
    "music": {"script": ROOT / "kaggle" / "ace_step.py", "kernel": "heritage-ace-step",
              "dataset": "heritage-music-inputs", "jobs": music.JOBS, "dest": music.DIR,
              "ext": ".wav"},
}


def _kaggle(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    exe = shutil.which("kaggle") or str(Path(sys.executable).parent / "kaggle")
    creds = require_env("KAGGLE_USERNAME", "KAGGLE_KEY")
    env = {**os.environ, **creds}
    if creds["KAGGLE_KEY"].startswith("KGAT_") and "KAGGLE_API_TOKEN" not in env:
        env["KAGGLE_API_TOKEN"] = creds["KAGGLE_KEY"]
    proc = subprocess.run([exe, *args], capture_output=True, text=True, env=env, check=False)
    if check and proc.returncode != 0:
        raise SystemExit(f"kaggle {' '.join(args)} failed:\n{proc.stdout}\n{proc.stderr}")
    return proc


def _user() -> str:
    return require_env("KAGGLE_USERNAME")["KAGGLE_USERNAME"]


def _jobs(kind: str) -> list[dict[str, Any]]:
    sb = storyboard.load()
    jobs = shots.run(sb) if kind == "wan" else music.run(sb)
    return jobs


def _push_dataset(kind: str, jobs: list[dict[str, Any]]) -> str:
    cfg = KINDS[kind]
    ds_dir = BUILD / f"{kind}-dataset"
    shutil.rmtree(ds_dir, ignore_errors=True)
    ds_dir.mkdir(parents=True)
    write_json(ds_dir / "jobs.json", {"jobs": jobs})
    if kind == "wan":
        for job in jobs:
            shutil.copy2(keyframes.DIR / job["keyframe"], ds_dir / job["keyframe"])
    ds_id = f"{_user()}/{cfg['dataset']}"
    write_json(ds_dir / "dataset-metadata.json",
               {"title": cfg["dataset"], "id": ds_id, "licenses": [{"name": "CC0-1.0"}]})
    exists = _kaggle("datasets", "status", ds_id, check=False).returncode == 0
    if exists:
        _kaggle("datasets", "version", "-p", str(ds_dir), "-m", f"{len(jobs)} jobs", "-r", "zip")
    else:
        _kaggle("datasets", "create", "-p", str(ds_dir), "-r", "zip")
    for _ in range(30):  # wait until the new version is processed
        st = _kaggle("datasets", "status", ds_id, check=False).stdout.strip().lower()
        if "ready" in st:
            break
        time.sleep(10)
    say(f"  dataset {ds_id}: {len(jobs)} job(s)")
    return ds_id


def push(kind: str) -> None:
    jobs = _jobs(kind)
    if not jobs:
        say(f"  nothing to render for {kind}: every output is already cached")
        return
    cfg = KINDS[kind]
    ds_id = _push_dataset(kind, jobs)
    k_dir = BUILD / f"{kind}-kernel"
    shutil.rmtree(k_dir, ignore_errors=True)
    k_dir.mkdir(parents=True)
    shutil.copy2(cfg["script"], k_dir / cfg["script"].name)
    write_json(k_dir / "kernel-metadata.json", {
        "id": f"{_user()}/{cfg['kernel']}", "title": cfg["kernel"],
        "code_file": cfg["script"].name, "language": "python", "kernel_type": "script",
        "is_private": True, "enable_gpu": True, "enable_internet": True,
        "dataset_sources": [ds_id], "competition_sources": [], "kernel_sources": [],
    })
    _kaggle("kernels", "push", "-p", str(k_dir), "--accelerator", "NvidiaTeslaT4")
    log_event({"stage": "shots" if kind == "wan" else "music", "item": "kaggle_push",
               "provider": "kaggle", "status": "submitted", "jobs": len(jobs),
               "kernel": f"{_user()}/{cfg['kernel']}"})
    say(f"  pushed kernel {_user()}/{cfg['kernel']} with {len(jobs)} job(s); "
        f"`make kaggle-{kind}-wait` to collect")


def status(kind: str) -> str:
    out = _kaggle("kernels", "status", f"{_user()}/{KINDS[kind]['kernel']}").stdout.strip()
    say(f"  {out}")
    return out


def pull(kind: str) -> int:
    cfg = KINDS[kind]
    out_dir = BUILD / f"{kind}-output"
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    _kaggle("kernels", "output", f"{_user()}/{cfg['kernel']}", "-p", str(out_dir))
    dest: Path = cfg["dest"]
    dest.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in out_dir.rglob(f"*{cfg['ext']}"):
        shutil.copy2(f, dest / f.name)
        moved += 1
    log_file = next(out_dir.rglob("kernel_runs.jsonl"), None)
    if log_file:
        for line in log_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                log_event({**json.loads(line), "provider": "kaggle", "merged_from": "kernel"})
    say(f"  pulled {moved} file(s) into {rel(dest)}")
    return moved


def wait(kind: str) -> None:
    started = time.time()
    while time.time() - started < MAX_WAIT_S:
        st = status(kind).lower()
        if "complete" in st:
            pull(kind)
            return
        if "error" in st or "cancel" in st:
            say("  kernel failed; pulling whatever it saved (see its log on kaggle.com)")
            pull(kind)
            raise SystemExit(1)
        time.sleep(POLL_S)
    raise SystemExit("timed out waiting for the kernel")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["push", "status", "pull", "wait"])
    ap.add_argument("kind", choices=list(KINDS))
    args = ap.parse_args(argv)
    {"push": push, "status": status, "pull": pull, "wait": wait}[args.action](args.kind)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
