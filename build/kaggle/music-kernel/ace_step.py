"""Kaggle kernel: ACE-Step 1.5 score candidates for every job in jobs.json.

Pushed by `pipeline/kaggle_jobs.py push music`. Installs ACE-Step 1.5 with uv (the
documented path), then runs the jobs through its Python API (acestep.inference.generate_music)
with the turbo DiT. Instrumental only: no vocals under narration. Writes
<cue>_<key>_c<i>.wav to /kaggle/working plus kernel_runs.jsonl.
"""

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

START = time.time()
OUT = Path("/kaggle/working")
LOG = OUT / "kernel_runs.jsonl"
REPO = Path("/tmp/ACE-Step-1.5")


def log(record: dict) -> None:
    record = {"ts": datetime.now(UTC).isoformat(timespec="seconds"), "stage": "music", **record}
    with LOG.open("a") as fh:
        fh.write(json.dumps(record) + "\n")
    print(json.dumps(record), flush=True)


def sh(cmd: list[str], **kw) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


jobs_file = next(Path("/kaggle/input").rglob("jobs.json"))

t0 = time.time()
sh([sys.executable, "-m", "pip", "install", "-q", "uv"])
if not REPO.exists():
    sh(["git", "clone", "--depth", "1", "https://github.com/ACE-Step/ACE-Step-1.5.git", str(REPO)])
sh(["uv", "sync"], cwd=REPO)
subprocess.run(["uv", "run", "acestep-download"], cwd=REPO, check=False)  # best effort
log({"item": "install", "status": "ok", "latency_s": round(time.time() - t0, 1)})

RUNNER = r'''
import json, shutil, sys, time
from datetime import UTC, datetime
from pathlib import Path
from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

jobs = json.loads(Path(sys.argv[1]).read_text())["jobs"]
out, repo, log_path = Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])

def log(r):
    r = {"ts": datetime.now(UTC).isoformat(timespec="seconds"), "stage": "music", **r}
    with log_path.open("a") as fh:
        fh.write(json.dumps(r) + "\n")
    print(json.dumps(r), flush=True)

t = time.time()
dit = AceStepHandler()
msg, ok = dit.initialize_service(project_root=str(repo), config_path="acestep-v15-turbo",
                                 device="cuda", offload_to_cpu=True)
log({"item": "model_load", "status": "ok" if ok else "failed", "detail": str(msg)[:300],
     "latency_s": round(time.time() - t, 1)})
llm = LLMHandler()  # not initialised: thinking/CoT off keeps the caption exactly as written

for job in jobs:
    t = time.time()
    try:
        params = GenerationParams(
            caption=job["caption"], lyrics="[Instrumental]", instrumental=True,
            bpm=job["bpm"], keyscale=job["keyscale"], timesignature="4",
            duration=float(job["duration"]), inference_steps=8, seed=job["seed"],
            guidance_scale=1.0, shift=3.0, thinking=False,
            use_cot_metas=False, use_cot_caption=False, use_cot_language=False)
        config = GenerationConfig(batch_size=1, audio_format="wav",
                                  use_random_seed=False, seeds=[job["seed"]])
        res = generate_music(dit, llm, params, config, save_dir=str(out / "_raw"))
        if not res.success:
            raise RuntimeError(res.error)
        shutil.copy2(res.audios[0]["path"], out / job["output"])
        secs = round(time.time() - t, 1)
        log({"item": f'{job["cue_id"]}#c{job["candidate"]}', "cache_key": job["key"],
             "model": job["model"], "status": "ok", "seed": job["seed"], "latency_s": secs,
             "gpu_s": secs, "params": {k: job[k] for k in ("bpm", "keyscale", "duration")},
             "output": "outputs/music/" + job["output"]})
    except Exception as exc:
        log({"item": f'{job["cue_id"]}#c{job["candidate"]}', "cache_key": job["key"],
             "status": "failed", "latency_s": round(time.time() - t, 1),
             "error": f"{type(exc).__name__}: {exc}"[:500]})
shutil.rmtree(out / "_raw", ignore_errors=True)
'''
(REPO / "heritage_runner.py").write_text(RUNNER)
proc = subprocess.run(["uv", "run", "python", "heritage_runner.py", str(jobs_file), str(OUT),
                       str(REPO), str(LOG)], cwd=REPO, env={**os.environ}, check=False)
log({"item": "kernel_total", "status": "ok" if proc.returncode == 0 else "failed",
     "latency_s": round(time.time() - START, 1), "gpu_s": round(time.time() - START, 1)})
