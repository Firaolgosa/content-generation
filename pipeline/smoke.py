"""Smoke test: call every provider once, log latency to runs.jsonl, print what works.

Run:  uv run python -m pipeline.smoke [--skip cloudflare,kaggle]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from collections.abc import Callable

from PIL import Image

from pipeline.common import OUTPUTS, STORYBOARD, CallSpec, atomic_write_bytes, call_logged, say

DIR = OUTPUTS / "smoke"
AMHARIC_SAMPLE = "ሰላም። ይህ የድምፅ ሙከራ ነው።"  # "Hello. This is a voice test."


def _models() -> dict[str, str]:
    return json.loads(STORYBOARD.read_text(encoding="utf-8"))["models"]


def check_gemini_text(m: dict[str, str]) -> str:
    from pipeline.providers import gemini
    return gemini.generate_text("Reply with the single word OK.", model=m["text"]).strip()[:40]


def check_gemini_tts(m: dict[str, str]) -> str:
    from pipeline.providers import gemini
    wav = gemini.tts(AMHARIC_SAMPLE, model=m["tts"], voice="Sulafat", style="warm, unhurried")
    p = atomic_write_bytes(DIR / "tts_amharic.wav", wav)
    return f"{len(wav) // 1024} KB -> {p.name}"


def check_flux2(m: dict[str, str]) -> str:
    from pipeline.providers import cloudflare
    img = cloudflare.flux2("A clay coffee pot (jebena) on a woven mat, soft window light.",
                           model=m["image"], width=512, height=512, seed=7)
    atomic_write_bytes(DIR / "flux2_text.png", img)
    size = Image.open(io.BytesIO(img)).size
    # second call proves the reference-image field works
    ref = cloudflare.flux2("The same coffee pot, seen from above.", model=m["image"],
                           width=512, height=512, seed=7, references=[img])
    atomic_write_bytes(DIR / "flux2_ref.png", ref)
    return f"text->image {size}, reference->image ok"


def check_schnell(m: dict[str, str]) -> str:
    from pipeline.providers import cloudflare
    img = cloudflare.flux_schnell("A clay coffee pot on a woven mat.", model=m["image_fallback"],
                                  steps=4, seed=7)
    atomic_write_bytes(DIR / "schnell.png", img)
    return f"{Image.open(io.BytesIO(img)).size}"


def check_kaggle(_m: dict[str, str]) -> str:
    from pipeline.kaggle_jobs import _kaggle
    out = _kaggle("kernels", "list", "--mine", "--page-size", "3").stdout
    return f"auth ok ({len(out.splitlines())} lines)"


CHECKS: dict[str, tuple[str, str, Callable[[dict[str, str]], str]]] = {
    "gemini_text": ("gemini", "text", check_gemini_text),
    "gemini_tts": ("gemini", "tts", check_gemini_tts),
    "cloudflare_flux2": ("cloudflare", "image", check_flux2),
    "cloudflare_schnell": ("cloudflare", "image_fallback", check_schnell),
    "kaggle": ("kaggle", "", check_kaggle),
}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip", default="", help="comma-separated providers to skip")
    args = ap.parse_args(argv)
    skip = set(filter(None, args.skip.split(",")))
    m = _models()
    results: list[tuple[str, bool, str]] = []
    for name, (provider, model_key, fn) in CHECKS.items():
        if provider in skip or name in skip:
            continue
        spec = CallSpec(stage="smoke", provider=provider, model=m.get(model_key, provider),
                        item=name)
        try:
            detail = call_logged(spec, lambda fn=fn: fn(m), attempts=2,
                                 describe=lambda d: {"detail": d})
            results.append((name, True, detail))
        except BaseException as exc:  # noqa: BLE001 - report every provider, keep going
            if isinstance(exc, KeyboardInterrupt):
                raise
            results.append((name, False, str(exc)[:200]))
    say("\nsmoke test:")
    for name, ok, detail in results:
        say(f"  {'OK  ' if ok else 'FAIL'} {name:20s} {detail}")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
