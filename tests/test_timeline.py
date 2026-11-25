from pipeline import timeline


def test_shot_extends_when_narration_runs_long(sb):
    lead, tail = sb["mix"]["narration_lead_s"], sb["mix"]["narration_tail_s"]
    first = sb["shots"][0]
    segs = timeline.build(sb, {first["id"]: 20.0})
    assert segs[0].duration == round(lead + 20.0 + tail, 3)
    assert segs[1].start == segs[0].end  # following shots shift


def test_shot_keeps_planned_length_when_narration_short(sb):
    segs = timeline.build(sb, {s["id"]: 1.0 for s in sb["shots"]})
    assert [s.duration for s in segs] == [s["duration_s"] for s in sb["shots"]]
    assert segs[0].narr_start == sb["mix"]["narration_lead_s"]


def test_film_length_includes_end_card(sb):
    segs = timeline.build(sb, {})
    planned = sum(s["duration_s"] for s in sb["shots"])
    assert timeline.film_length(segs, sb) == planned + sb["end_card"]["duration_s"]


def test_wrap_respects_width():
    lines = timeline.wrap("one two three four five six seven eight nine ten eleven", 15)
    assert all(len(line) <= 15 for line in lines)
    assert " ".join(lines) == "one two three four five six seven eight nine ten eleven"


def test_chunk_subtitle_max_two_lines():
    text = ("Coffee is just the excuse, she used to say. What matters is being together, "
            "every morning, before the work of the day begins in the fields.")
    for chunk in timeline.chunk_subtitle(text):
        lines = chunk.split("\n")
        assert len(lines) <= timeline.SUB_MAX_LINES
        assert all(len(line) <= timeline.SUB_MAX_CHARS for line in lines)


def test_subtitle_cues_stay_inside_their_shot(sb):
    segs = timeline.build(sb, {s["id"]: 3.0 for s in sb["shots"]})
    cues = timeline.subtitle_cues(sb, segs)
    assert cues
    for seg in segs:
        for c in cues:
            if seg.start <= c.start < seg.end:
                assert c.end <= seg.end + 1e-6
                assert c.start >= seg.narr_start - 1e-6


def test_srt_format():
    srt = timeline.to_srt([timeline.Cue(0.5, 2.25, "Hello\nworld"), timeline.Cue(61.0, 62.0, "x")])
    assert "1\n00:00:00,500 --> 00:00:02,250\nHello\nworld\n" in srt
    assert "2\n00:01:01,000 --> 00:01:02,000\nx\n" in srt


def test_last_music_window_runs_to_end(sb):
    segs = timeline.build(sb, {})
    windows = timeline.music_windows(sb, segs)
    assert windows[-1][2] == timeline.film_length(segs, sb)
    assert windows[0][1] == 0.0
