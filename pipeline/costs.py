"""Summarise runs.jsonl into the measurement table for COSTS.md.

Per stage: model calls (ok / retried / failed), cache hits, total and median latency, GPU
minutes, and a list-price-equivalent cost. Writes between the markers in COSTS.md.

Run:  uv run python -m pipeline.costs
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from pipeline.common import ROOT, RUNS_LOG

COSTS_MD = ROOT / "COSTS.md"
BEGIN, END = "<!-- costs:begin -->", "<!-- costs:end -->"
# List-price equivalent for a Kaggle T4 hour: GCP on-demand NVIDIA T4, us-central1 (~$0.35/h).
T4_USD_PER_HOUR = 0.35
STAGE_ORDER = ["smoke", "script", "narration", "references", "keyframes", "shots", "music",
               "assemble", "pipeline"]


def load(path: Path = RUNS_LOG) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def summarise(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_stage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_stage[r.get("stage", "?")].append(r)
    out = []
    for stage in sorted(by_stage, key=lambda s: (STAGE_ORDER.index(s) if s in STAGE_ORDER else 99, s)):
        rs = by_stage[stage]
        ok = [r for r in rs if r.get("status") == "ok"]
        lat = [r["latency_s"] for r in ok if isinstance(r.get("latency_s"), int | float)]
        gpu_s = sum(r.get("gpu_s", 0) or 0 for r in rs if r.get("item") != "kernel_total")
        cost = sum(r.get("cost_usd", 0) or 0 for r in rs) + gpu_s / 3600 * T4_USD_PER_HOUR
        out.append({
            "stage": stage,
            "ok": len(ok),
            "retry": sum(r.get("status") == "retry" for r in rs),
            "failed": sum(r.get("status") == "failed" for r in rs),
            "cache_hits": sum(r.get("status") == "cache_hit" for r in rs),
            "latency_total_s": round(sum(lat), 1),
            "latency_median_s": round(statistics.median(lat), 2) if lat else 0.0,
            "gpu_min": round(gpu_s / 60, 1),
            "list_usd": round(cost, 4),
        })
    return out


def to_markdown(summary: list[dict[str, Any]]) -> str:
    head = ("| stage | ok | retries | failed | cache hits | latency total (s) | median (s) "
            "| GPU min | list-price equiv. (USD) |\n|---|---|---|---|---|---|---|---|---|\n")
    body = "".join(
        f"| {s['stage']} | {s['ok']} | {s['retry']} | {s['failed']} | {s['cache_hits']} "
        f"| {s['latency_total_s']} | {s['latency_median_s']} | {s['gpu_min']} | {s['list_usd']} |\n"
        for s in summary)
    total = sum(s["list_usd"] for s in summary)
    return head + body + f"\nTotal list-price equivalent: **${total:.4f}** (actual spend: $0, free tiers).\n"


def write(md_path: Path = COSTS_MD) -> str:
    table = to_markdown(summarise(load()))
    if md_path.exists() and BEGIN in md_path.read_text(encoding="utf-8"):
        text = md_path.read_text(encoding="utf-8")
        pre, rest = text.split(BEGIN, 1)
        post = rest.split(END, 1)[1] if END in rest else ""
        md_path.write_text(f"{pre}{BEGIN}\n{table}{END}{post}", encoding="utf-8")
    return table


def main(argv: list[str]) -> int:  # noqa: ARG001
    print(write())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
