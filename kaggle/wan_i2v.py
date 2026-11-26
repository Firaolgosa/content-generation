"""Kaggle kernel: Wan 2.2 TI2V-5B image-to-video for every job in jobs.json.

Pushed by `pipeline/kaggle_jobs.py push wan`. Reads the attached dataset (jobs.json +
keyframes), writes <shot>_<key>.mp4 to /kaggle/working plus kernel_runs.jsonl with latency
and GPU seconds per clip. Each clip is saved as soon as it finishes, and a time budget stops
new jobs before the session limit, so a timeout never loses finished work.

T4 notes: Turing has no native bf16, so the transformer runs in fp16 there (VAE in fp32 as
the model card recommends). Black/NaN frames are detected and logged, not silently kept.
"""

import json
import os
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

START = time.time()
BUDGET_S = 8 * 3600
OUT = Path("/kaggle/working")
LOG = OUT / "kernel_runs.jsonl"
BLACK_THRESHOLD = 0.02

subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "git+https://github.com/huggingface/diffusers",
                "transformers>=4.49", "accelerate", "ftfy", "sentencepiece",
                "imageio", "imageio-ffmpeg"], check=True)

import numpy as np  # noqa: E402
import torch  # noqa: E402
from diffusers import AutoencoderKLWan, WanImageToVideoPipeline  # noqa: E402
from diffusers.utils import export_to_video  # noqa: E402
from PIL import Image, ImageOps  # noqa: E402


def log(record: dict) -> None:
    record = {"ts": datetime.now(UTC).isoformat(timespec="seconds"), "stage": "shots", **record}
    with LOG.open("a") as fh:
        fh.write(json.dumps(record) + "\n")
    print(json.dumps(record), flush=True)


jobs_file = next(Path("/kaggle/input").rglob("jobs.json"))
jobs = json.loads(jobs_file.read_text())["jobs"]
in_dir = jobs_file.parent
device_name = torch.cuda.get_device_name(0)
major, _ = torch.cuda.get_device_capability(0)
dtype = torch.bfloat16 if major >= 8 else torch.float16
model_id = jobs[0]["model"] if jobs else "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
print(f"{len(jobs)} jobs on {device_name} ({torch.cuda.device_count()} GPU), dtype={dtype}")

t_load = time.time()
vae = AutoencoderKLWan.from_pretrained(model_id, subfolder="vae", torch_dtype=torch.float32)
pipe = WanImageToVideoPipeline.from_pretrained(model_id, vae=vae, torch_dtype=dtype)
pipe.enable_sequential_cpu_offload()
if hasattr(pipe.vae, "enable_tiling"):
    pipe.vae.enable_tiling()
if hasattr(pipe.vae, "enable_slicing"):
    pipe.vae.enable_slicing()
log({"item": "model_load", "model": model_id, "status": "ok", "device": device_name,
     "dtype": str(dtype), "latency_s": round(time.time() - t_load, 1)})

for job in jobs:
    if time.time() - START > BUDGET_S:
        log({"item": job["shot_id"], "cache_key": job["key"], "status": "skipped_budget"})
        continue
    t0 = time.time()
    try:
        w, h = job["width"], job["height"]
        image = ImageOps.fit(Image.open(in_dir / job["keyframe"]).convert("RGB"), (w, h),
                             Image.Resampling.LANCZOS)
        gen = torch.Generator("cpu").manual_seed(job["seed"])
        frames = pipe(image=image, prompt=job["prompt"], negative_prompt=job["negative"] or None,
                      height=h, width=w, num_frames=job["num_frames"],
                      num_inference_steps=job["steps"], guidance_scale=job["guidance"],
                      generator=gen).frames[0]
        mid = np.asarray(frames[len(frames) // 2], dtype=np.float32)
        if mid.max() > 1.5:
            mid = mid / 255.0
        if not np.isfinite(mid).all() or mid.max() < BLACK_THRESHOLD:
            raise RuntimeError(f"black or NaN frames (dtype={dtype}); try fewer frames or bf16 GPU")
        export_to_video(frames, str(OUT / job["output"]), fps=job["fps"])
        secs = round(time.time() - t0, 1)
        log({"item": job["shot_id"], "cache_key": job["key"], "model": model_id, "status": "ok",
             "seed": job["seed"], "latency_s": secs, "gpu_s": secs, "device": device_name,
             "params": {k: job[k] for k in ("width", "height", "num_frames", "steps", "guidance")},
             "output": f"outputs/wan/{job['output']}"})
    except Exception as exc:  # keep going: one bad shot must not cost the others
        log({"item": job["shot_id"], "cache_key": job["key"], "model": model_id,
             "status": "failed", "latency_s": round(time.time() - t0, 1),
             "error": f"{type(exc).__name__}: {exc}"[:500]})
        traceback.print_exc()
        torch.cuda.empty_cache()

log({"item": "kernel_total", "status": "ok", "latency_s": round(time.time() - START, 1),
     "gpu_s": round(time.time() - START, 1), "device": device_name})
