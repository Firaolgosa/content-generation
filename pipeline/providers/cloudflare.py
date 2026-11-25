"""Cloudflare Workers AI image models (FLUX).

- flux-1-schnell: JSON body {prompt, steps}; no reference images.
- flux-2-klein-*: multipart/form-data; supports reference images (input_image_0..3).
  Field names for klein are not in the published schema; they follow the flux-2 examples
  and are confirmed by `make smoke` (see FAILURES.md if that changes).

Both return JSON {"result": {"image": <base64>}}.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from pipeline.common import PermanentError, TransientError, http_error_is_transient, require_env

API = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
TIMEOUT_S = 120.0
MAX_REFERENCES = 4

# Neuron prices from developers.cloudflare.com/workers-ai/models (read 2026-11-25).
# Free allowance: 10,000 neurons/day; list price $0.011 per 1,000 neurons.
USD_PER_NEURON = 0.011 / 1000
TILE_PX = 512 * 512
NEURONS = {
    "@cf/black-forest-labs/flux-1-schnell": {"out_tile": 4.80, "step": 9.60, "in_tile": 0.0},
    "@cf/black-forest-labs/flux-2-klein-4b": {"out_tile": 26.05, "step": 0.0, "in_tile": 5.37},
}


def estimate_neurons(model: str, width: int, height: int, steps: int, ref_pixels: int = 0) -> float:
    """List-price neuron estimate for one image (used for COSTS.md, not billing)."""
    p = NEURONS.get(model)
    if p is None:
        return 0.0
    out_tiles = -(-width * height // TILE_PX)
    in_tiles = -(-ref_pixels // TILE_PX) if ref_pixels else 0
    return round(out_tiles * p["out_tile"] + steps * p["step"] + in_tiles * p["in_tile"], 2)


def _url(model: str) -> tuple[str, dict[str, str]]:
    env = require_env("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN")
    url = API.format(account=env["CLOUDFLARE_ACCOUNT_ID"], model=model)
    return url, {"Authorization": f"Bearer {env['CLOUDFLARE_API_TOKEN']}"}


def _parse(resp: httpx.Response) -> bytes:
    if resp.status_code != 200:
        msg = f"cloudflare {resp.status_code}: {resp.text[:300]}"
        if http_error_is_transient(resp.status_code):
            raise TransientError(msg)
        raise PermanentError(msg)
    body = resp.json()
    result = body.get("result") if isinstance(body, dict) else None
    image = (result or {}).get("image") if isinstance(result, dict) else None
    if not image:
        raise TransientError(f"cloudflare: no image in response: {str(body)[:200]}")
    return base64.b64decode(image)


def _post(url: str, headers: dict[str, str], **kwargs: Any) -> httpx.Response:
    try:
        return httpx.post(url, headers=headers, timeout=TIMEOUT_S, **kwargs)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise TransientError(f"cloudflare network: {exc}") from exc


def flux_schnell(prompt: str, *, model: str, steps: int = 4, seed: int | None = None) -> bytes:
    """Text-to-image, JSON API. Returns image bytes (JPEG).

    Note: Cloudflare's flux-1-schnell schema rejects `seed` (400 code 5006), so `seed`
    is accepted for call-site compatibility but omitted from the request payload.
    """
    _ = seed
    url, headers = _url(model)
    payload: dict[str, Any] = {"prompt": prompt[:2048], "steps": steps}
    return _parse(_post(url, headers, json=payload))


def flux2(prompt: str, *, model: str, width: int, height: int, seed: int | None = None,
          references: list[bytes] | None = None, steps: int | None = None) -> bytes:
    """Text(+reference images)-to-image, multipart API. Returns image bytes."""
    url, headers = _url(model)
    fields: list[tuple[str, tuple[str | None, Any, str] | tuple[None, str]]] = [
        ("prompt", (None, prompt[:2048])),
        ("width", (None, str(width))),
        ("height", (None, str(height))),
    ]
    if seed is not None:
        fields.append(("seed", (None, str(seed))))
    if steps is not None:
        fields.append(("steps", (None, str(steps))))
    for i, ref in enumerate((references or [])[:MAX_REFERENCES]):
        fields.append((f"input_image_{i}", (f"ref{i}.png", ref, "image/png")))
    return _parse(_post(url, headers, files=fields))
