"""Stage: keyframes. Lock the look first, then generate every shot against it.

1. Golden style reference (style.reference_prompt) and one sheet per character.
2. One keyframe per shot, conditioned on the references of the characters in it
   plus the style reference (FLUX.2 klein reference images).
3. If the primary model fails permanently (e.g. API change), fall back to FLUX.1 schnell
   text-only and record that in runs.jsonl.

Cache key = hash(prompt, seed, model, size, hashes of the reference images), so editing one
shot's prompt regenerates only that shot, and editing a character regenerates only its shots.

Run:  uv run python -m pipeline.keyframes [--only s03] [--refs-only]
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path
from typing import Any

from PIL import Image

from pipeline import storyboard
from pipeline.common import (
    OUTPUTS,
    CallSpec,
    PermanentError,
    TransientError,
    atomic_write_bytes,
    call_logged,
    digest,
    file_digest,
    log_cache_hit,
    say,
)
from pipeline.providers import cloudflare

STAGE = "keyframes"
DIR = OUTPUTS / "keyframes"
REF_DIR = OUTPUTS / "references"
REF_SIZE = (1024, 768)
SCHNELL_STEPS = 4


def _to_png(data: bytes) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _reference_specs(sb: dict[str, Any]) -> list[dict[str, Any]]:
    """Reference images to build: the style frame, then one sheet per character."""
    style = sb["style"]
    specs = [{"id": "style", "seed": style["reference_seed"],
              "prompt": f"{style['reference_prompt'].strip()} {style['block'].strip()}"}]
    for c in sb.get("characters", []):
        specs.append({
            "id": f"char-{c['id']}",
            "seed": c["sheet_seed"],
            "prompt": ("Character reference sheet on a plain warm-grey background: the same person "
                       "shown full-body front view, three-quarter view and a head-and-shoulders "
                       f"close-up, consistent face, clothing and proportions. {c['description'].strip()} "
                       f"{style['block'].strip()}"),
        })
    return specs


def _ref_path(sb: dict[str, Any], spec: dict[str, Any]) -> Path:
    key = digest({"prompt": spec["prompt"], "seed": spec["seed"], "model": sb["models"]["image"],
                  "size": REF_SIZE})
    return REF_DIR / f"{spec['id']}_{key}.png"


def reference_paths(sb: dict[str, Any]) -> dict[str, Path]:
    return {spec["id"]: _ref_path(sb, spec) for spec in _reference_specs(sb)}


def _generate_image(sb: dict[str, Any], spec: CallSpec, out: Path, prompt: str, seed: int,
                    size: tuple[int, int], refs: list[Path]) -> Path:
    model = sb["models"]["image"]
    ref_bytes = [r.read_bytes() for r in refs]
    ref_px = sum(Image.open(r).size[0] * Image.open(r).size[1] for r in refs)

    def call() -> Path:
        data = cloudflare.flux2(prompt, model=model, width=size[0], height=size[1], seed=seed,
                                references=ref_bytes)
        return atomic_write_bytes(out, _to_png(data))

    neurons = cloudflare.estimate_neurons(model, size[0], size[1], 0, ref_px)
    return call_logged(spec, call, describe=lambda p: {
        "output": p, "neurons_est": neurons,
        "cost_usd": round(neurons * cloudflare.USD_PER_NEURON, 6)})


def _fallback_path(sb: dict[str, Any], item: str, prompt: str, seed: int) -> Path:
    key = digest({"prompt": prompt, "seed": seed, "model": sb["models"]["image_fallback"],
                  "steps": SCHNELL_STEPS})
    return DIR / f"{item}_{key}_fallback.png"


def _generate_fallback(sb: dict[str, Any], item: str, prompt: str, seed: int) -> Path:
    model = sb["models"]["image_fallback"]
    out = _fallback_path(sb, item, prompt, seed)
    spec = CallSpec(stage=STAGE, provider="cloudflare", model=model, item=item,
                    params={"steps": SCHNELL_STEPS, "fallback": True}, seed=seed,
                    cache_key=out.stem)
    if out.exists():
        log_cache_hit(spec, out)
        return out
    neurons = cloudflare.estimate_neurons(model, 1024, 1024, SCHNELL_STEPS)

    def call() -> Path:
        data = cloudflare.flux_schnell(prompt, model=model, steps=SCHNELL_STEPS, seed=seed)
        return atomic_write_bytes(out, _to_png(data))

    return call_logged(spec, call, describe=lambda p: {
        "output": p, "neurons_est": neurons,
        "cost_usd": round(neurons * cloudflare.USD_PER_NEURON, 6)})


def build_references(sb: dict[str, Any]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for ref in _reference_specs(sb):
        path = _ref_path(sb, ref)
        spec = CallSpec(stage="references", provider="cloudflare", model=sb["models"]["image"],
                        item=ref["id"], params={"size": REF_SIZE}, seed=ref["seed"],
                        cache_key=path.stem.rsplit("_", 1)[-1])
        if path.exists():
            log_cache_hit(spec, path)
        else:
            try:
                _generate_image(sb, spec, path, ref["prompt"], ref["seed"], REF_SIZE, [])
                say(f"  reference {ref['id']} -> {path.name}")
            except (PermanentError, TransientError) as exc:
                say(f"  ! reference {ref['id']} failed ({exc}); keyframes continue without it")
                continue
        out[ref["id"]] = path
    return out


def _shot_refs(shot: dict[str, Any], refs: dict[str, Path]) -> list[Path]:
    wanted = [f"char-{c}" for c in shot.get("characters", [])] + ["style"]
    present = [refs[k] for k in wanted if k in refs and refs[k].exists()]
    return present[: cloudflare.MAX_REFERENCES]


def shot_key(sb: dict[str, Any], shot: dict[str, Any], refs: dict[str, Path]) -> str:
    size = sb["render"]["keyframe"]
    return digest({
        "prompt": storyboard.image_prompt(sb, shot), "seed": shot["seed"],
        "model": sb["models"]["image"], "size": [size["width"], size["height"]],
        "refs": [file_digest(p) for p in _shot_refs(shot, refs) if p.exists()],
    })


def resolve(sb: dict[str, Any], shot: dict[str, Any]) -> Path | None:
    """The keyframe the next stages should use: primary if present, else the fallback."""
    refs = reference_paths(sb)
    primary = DIR / f"{shot['id']}_{shot_key(sb, shot, refs)}.png"
    if primary.exists():
        return primary
    fb = _fallback_path(sb, shot["id"], storyboard.image_prompt(sb, shot), shot["seed"])
    return fb if fb.exists() else None


def generate_shot(sb: dict[str, Any], shot: dict[str, Any], refs: dict[str, Path]) -> Path:
    size = sb["render"]["keyframe"]
    prompt = storyboard.image_prompt(sb, shot)
    key = shot_key(sb, shot, refs)
    out = DIR / f"{shot['id']}_{key}.png"
    used = _shot_refs(shot, refs)
    spec = CallSpec(stage=STAGE, provider="cloudflare", model=sb["models"]["image"],
                    item=shot["id"], seed=shot["seed"], cache_key=key,
                    params={"size": [size["width"], size["height"]],
                            "refs": [p.name for p in used], "prompt": prompt})
    if out.exists():
        log_cache_hit(spec, out)
        return out
    fb = _fallback_path(sb, shot["id"], prompt, shot["seed"])
    if fb.exists():
        log_cache_hit(spec, fb)
        return fb
    try:
        path = _generate_image(sb, spec, out, prompt, shot["seed"],
                               (size["width"], size["height"]), used)
    except (PermanentError, TransientError) as exc:
        say(f"  ! {shot['id']}: primary image model failed ({exc}); falling back to "
            f"{sb['models']['image_fallback']} without references")
        path = _generate_fallback(sb, shot["id"], prompt, shot["seed"])
    say(f"  keyframe {shot['id']} -> {path.name}")
    return path


def run(sb: dict[str, Any], only: set[str] | None = None, refs_only: bool = False) -> dict[str, Path]:
    say(f"[{STAGE}] {sb['models']['image']} (fallback {sb['models']['image_fallback']})")
    refs = build_references(sb)
    if refs_only:
        return refs
    out: dict[str, Path] = {}
    for shot in sb["shots"]:
        if only and shot["id"] not in only:
            continue
        out[shot["id"]] = generate_shot(sb, shot, refs)
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="comma-separated shot ids")
    ap.add_argument("--refs-only", action="store_true", help="build the reference sheet only")
    args = ap.parse_args(argv)
    sb = storyboard.load()
    run(sb, set(args.only.split(",")) if args.only else None, args.refs_only)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
