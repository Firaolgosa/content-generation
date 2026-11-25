"""Pure helpers of the stages: cache keys, bucketing, filters, cost estimates."""

import io
import wave

from pipeline import costs, music, narration, video
from pipeline.providers import cloudflare, gemini


def test_narration_key_changes_only_with_its_inputs(sb):
    a, b = sb["shots"][0], sb["shots"][1]
    key_a, key_b = narration.cache_key(sb, a), narration.cache_key(sb, b)
    a["narration"] += " ።"
    assert narration.cache_key(sb, a) != key_a
    assert narration.cache_key(sb, b) == key_b  # other shots unaffected
    sb["voice"]["voice"] = "Kore"
    assert narration.cache_key(sb, b) != key_b  # voice change invalidates all


def test_empty_narration_has_no_path(sb):
    sb["shots"][0]["narration"] = "  "
    assert narration.path_for(sb, sb["shots"][0]) is None


def test_music_duration_is_bucketed_and_ignores_narration(sb):
    cue = sb["music"]["cues"][0]
    d = music.requested_duration(sb, cue)
    assert d % music.BUCKET_S == 0
    planned = sum(s["duration_s"] for s in sb["shots"]) + sb["end_card"]["duration_s"]
    assert d >= planned + music.HEADROOM_S
    key = music.cue_key(sb, cue)
    sb["shots"][0]["narration"] = "changed"
    assert music.cue_key(sb, cue) == key


def test_music_candidates_have_distinct_paths(sb):
    cue = sb["music"]["cues"][0]
    paths = {music.candidate_path(sb, cue, i) for i in range(cue["candidates"])}
    assert len(paths) == cue["candidates"]


def test_kenburns_expressions_cover_every_camera():
    for cam in ("static", "push_in", "pull_out", "pan_left", "pan_right", "tilt_up", "tilt_down"):
        z, x, y = video.kenburns_expr(cam, 120)
        assert "on/119" in z + x + y  # every move is eased over the shot's frames


def test_frame_filter_modes():
    crop = video.frame_filter(1080, 1920, "crop", 0.3)
    assert "crop=1080:1920" in crop and "*0.3" in crop
    blur = video.frame_filter(1080, 1920, "fit_blur", 0.5)
    assert "boxblur" in blur and "overlay" in blur


def test_cloudflare_neuron_estimate():
    n = cloudflare.estimate_neurons("@cf/black-forest-labs/flux-2-klein-4b", 1024, 1024, 0)
    assert n == round(4 * 26.05, 2)
    s = cloudflare.estimate_neurons("@cf/black-forest-labs/flux-1-schnell", 1024, 1024, 4)
    assert s == round(4 * 4.80 + 4 * 9.60, 2)
    assert cloudflare.estimate_neurons("unknown", 512, 512, 4) == 0.0


def test_ensure_wav_wraps_raw_pcm():
    raw = b"\x00\x01" * 2400
    wav = gemini.ensure_wav(raw)
    with wave.open(io.BytesIO(wav)) as w:
        assert w.getframerate() == gemini.TTS_SAMPLE_RATE and w.getnframes() == 2400
    assert gemini.ensure_wav(wav) == wav


def test_costs_summary():
    rows = [
        {"stage": "keyframes", "status": "ok", "latency_s": 2.0, "cost_usd": 0.001},
        {"stage": "keyframes", "status": "retry", "latency_s": 1.0},
        {"stage": "keyframes", "status": "cache_hit", "latency_s": 0.0},
        {"stage": "shots", "status": "ok", "latency_s": 600.0, "gpu_s": 600.0},
    ]
    summary = {s["stage"]: s for s in costs.summarise(rows)}
    assert summary["keyframes"]["ok"] == 1 and summary["keyframes"]["retry"] == 1
    assert summary["keyframes"]["cache_hits"] == 1
    assert summary["shots"]["gpu_min"] == 10.0
    assert summary["shots"]["list_usd"] == round(600 / 3600 * costs.T4_USD_PER_HOUR, 4)
    assert "| keyframes |" in costs.to_markdown(costs.summarise(rows))
