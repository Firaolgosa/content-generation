import pytest

from pipeline import common
from pipeline.common import CallSpec, PermanentError, TransientError, call_logged, digest
from tests.conftest import read_log

SPEC = CallSpec(stage="test", provider="fake", model="m1", item="s01", params={"a": 1}, seed=7,
                cache_key="abc")


def test_digest_ignores_key_order_and_changes_with_content():
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})
    assert digest({"a": 1}) != digest({"a": 2})
    assert len(digest("x")) == common.DIGEST_LEN


def test_file_digest_tracks_bytes(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"one")
    first = common.file_digest(p)
    p.write_bytes(b"two")
    assert common.file_digest(p) != first


def test_atomic_write_leaves_no_temp_files(tmp_path):
    out = common.atomic_write_bytes(tmp_path / "sub" / "x.bin", b"data")
    assert out.read_bytes() == b"data"
    assert [p.name for p in out.parent.iterdir()] == ["x.bin"]


def test_call_logged_success_writes_one_ok_line(runs_log):
    result = call_logged(SPEC, lambda: 42, describe=lambda r: {"value": r})
    assert result == 42
    (line,) = read_log(runs_log)
    assert line["status"] == "ok"
    assert line["model"] == "m1" and line["seed"] == 7 and line["params"] == {"a": 1}
    assert line["value"] == 42 and line["attempt"] == 1
    assert "latency_s" in line and "run_id" in line


def test_call_logged_retries_transient_then_succeeds(runs_log):
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("429 quota")
        return "ok"

    sleeps: list[float] = []
    assert call_logged(SPEC, flaky, sleep=sleeps.append, base_delay_s=1) == "ok"
    statuses = [r["status"] for r in read_log(runs_log)]
    assert statuses == ["retry", "retry", "ok"]
    assert sleeps == [1, 2]  # exponential backoff


def test_call_logged_gives_up_after_attempts(runs_log):
    def always():
        raise TransientError("503")

    with pytest.raises(TransientError):
        call_logged(SPEC, always, attempts=2, sleep=lambda _: None)
    assert [r["status"] for r in read_log(runs_log)] == ["retry", "failed"]


def test_call_logged_does_not_retry_permanent(runs_log):
    def bad():
        raise PermanentError("400 bad request")

    with pytest.raises(PermanentError):
        call_logged(SPEC, bad, sleep=lambda _: pytest.fail("should not sleep"))
    (line,) = read_log(runs_log)
    assert line["status"] == "failed" and "400" in line["error"]


def test_cache_hit_is_logged_with_zero_cost(runs_log, tmp_path):
    common.log_cache_hit(SPEC, tmp_path / "x.png")
    (line,) = read_log(runs_log)
    assert line["status"] == "cache_hit" and line["cost_usd"] == 0.0


def test_http_transient_classification():
    assert common.http_error_is_transient(429)
    assert common.http_error_is_transient(503)
    assert not common.http_error_is_transient(400)
    assert not common.http_error_is_transient(401)


def test_require_env_names_missing(monkeypatch):
    monkeypatch.delenv("HERITAGE_TEST_MISSING", raising=False)
    with pytest.raises(SystemExit, match="HERITAGE_TEST_MISSING"):
        common.require_env("HERITAGE_TEST_MISSING")
