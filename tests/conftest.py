import copy
import json
from pathlib import Path

import pytest

from pipeline import common

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def sb() -> dict:
    """A fresh deep copy of the committed storyboard."""
    return copy.deepcopy(json.loads((ROOT / "storyboard.json").read_text(encoding="utf-8")))


@pytest.fixture
def runs_log(tmp_path, monkeypatch) -> Path:
    """Redirect runs.jsonl to a temp file so tests never touch the real log."""
    log = tmp_path / "runs.jsonl"
    monkeypatch.setattr(common, "RUNS_LOG", log)
    return log


def read_log(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
