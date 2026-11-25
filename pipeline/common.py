"""Shared plumbing: paths, secrets, content hashing, the runs.jsonl log and retries.

Every model call in the pipeline goes through `call_logged`, so every attempt
(success, transient failure, final failure, cache hit) leaves one line in runs.jsonl.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STORYBOARD = ROOT / "storyboard.json"
SCHEMA = ROOT / "schema" / "storyboard.schema.json"
RUNS_LOG = ROOT / "runs.jsonl"
OUTPUTS = ROOT / "outputs"
ETHICS = ROOT / "ETHICS.md"
FONTS = ROOT / "assets" / "fonts"

DIGEST_LEN = 12
DEFAULT_ATTEMPTS = 3
DEFAULT_BASE_DELAY_S = 4.0
MAX_DELAY_S = 60.0



# --------------------------------------------------------------------------- env


def load_env() -> None:
    """Load .env (git-ignored) into the process environment, without overriding real env vars."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependency is declared
        return
    load_dotenv(ROOT / ".env", override=False)


def require_env(*names: str) -> dict[str, str]:
    """Return the named env vars or exit with a clear message naming what is missing."""
    load_env()
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise SystemExit(
            f"Missing environment variable(s): {', '.join(missing)}. "
            "Copy .env.example to .env and fill them in."
        )
    return {n: os.environ[n] for n in names}


# ----------------------------------------------------------------------- hashing


def digest(obj: Any) -> str:
    """Stable short hash of any JSON-serialisable value (dict key order does not matter)."""
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:DIGEST_LEN]


def file_digest(path: Path) -> str:
    """Short hash of a file's bytes. Used so downstream cache keys change when inputs change."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:DIGEST_LEN]


def atomic_write_bytes(path: Path, data: bytes) -> Path:
    """Write via a temp file and rename, so a crash never leaves a half-written cache entry."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:6]}.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return path


def write_json(path: Path, obj: Any) -> Path:
    text = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    return atomic_write_bytes(path, text.encode("utf-8"))


# ----------------------------------------------------------------------- run log


def _new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:4]


RUN_ID = os.environ.get("HERITAGE_RUN_ID") or _new_run_id()
os.environ.setdefault("HERITAGE_RUN_ID", RUN_ID)  # child processes share the run id


def log_event(record: dict[str, Any], log_path: Path | None = None) -> dict[str, Any]:
    """Append one JSON line to runs.jsonl and return the full record."""
    full = {"ts": datetime.now(UTC).isoformat(timespec="milliseconds"), "run_id": RUN_ID, **record}
    target = log_path or RUNS_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(full, ensure_ascii=False, default=str) + "\n")
    return full


def say(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ------------------------------------------------------------------------ retries


class TransientError(Exception):
    """Raised by providers for failures worth retrying (429, 5xx, timeouts)."""


class PermanentError(Exception):
    """Raised by providers for failures that will not improve on retry (400, auth, schema)."""


@dataclass(frozen=True)
class CallSpec:
    """What is being called, recorded verbatim in runs.jsonl."""

    stage: str
    provider: str
    model: str
    item: str  # shot id, cue id, "reference", ...
    params: dict[str, Any] = field(default_factory=dict)
    seed: int | None = None
    cache_key: str | None = None


def log_cache_hit(spec: CallSpec, output: Path) -> None:
    log_event(
        {
            "stage": spec.stage,
            "item": spec.item,
            "provider": spec.provider,
            "model": spec.model,
            "status": "cache_hit",
            "cache_key": spec.cache_key,
            "seed": spec.seed,
            "latency_s": 0.0,
            "cost_usd": 0.0,
            "output": rel(output),
        }
    )


def rel(path: Path | str | None) -> str | None:
    if path is None:
        return None
    p = Path(path)
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def call_logged[T](
    spec: CallSpec,
    fn: Callable[[], T],
    *,
    describe: Callable[[T], dict[str, Any]] | None = None,
    attempts: int = DEFAULT_ATTEMPTS,
    base_delay_s: float = DEFAULT_BASE_DELAY_S,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Run `fn` with retries on TransientError, logging every attempt to runs.jsonl.

    `describe(result)` may add fields to the success line (output path, cost_usd, audio length...).
    PermanentError and unknown exceptions are logged and re-raised immediately.
    """
    for attempt in range(1, attempts + 1):
        started = time.perf_counter()
        base = {
            "stage": spec.stage,
            "item": spec.item,
            "provider": spec.provider,
            "model": spec.model,
            "params": spec.params,
            "seed": spec.seed,
            "cache_key": spec.cache_key,
            "attempt": attempt,
        }
        try:
            result = fn()
        except TransientError as exc:
            latency = round(time.perf_counter() - started, 3)
            final = attempt == attempts
            log_event({**base, "status": "failed" if final else "retry", "latency_s": latency,
                       "error": str(exc)[:500]})
            if final:
                raise
            delay = min(base_delay_s * (2 ** (attempt - 1)), MAX_DELAY_S)
            say(f"  ! {spec.stage}/{spec.item}: {exc} -- retry {attempt}/{attempts - 1} in {delay:.0f}s")
            sleep(delay)
            continue
        except Exception as exc:
            latency = round(time.perf_counter() - started, 3)
            log_event({**base, "status": "failed", "latency_s": latency,
                       "error": f"{type(exc).__name__}: {exc}"[:500]})
            raise
        latency = round(time.perf_counter() - started, 3)
        extra = describe(result) if describe else {}
        if "output" in extra:
            extra = {**extra, "output": rel(extra["output"])}
        log_event({**base, "status": "ok", "latency_s": latency, **extra})
        return result
    raise RuntimeError("unreachable")  # pragma: no cover


def http_error_is_transient(status_code: int) -> bool:
    return status_code == 429 or status_code == 408 or 500 <= status_code < 600
