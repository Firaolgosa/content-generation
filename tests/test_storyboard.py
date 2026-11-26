from pipeline import storyboard


def test_committed_storyboard_is_valid(sb, tmp_path):
    assert storyboard.validate(sb, tmp_path / "ETHICS.md") == []


def test_schema_rejects_too_few_shots(sb, tmp_path):
    sb["shots"] = sb["shots"][:7]
    errs = storyboard.validate(sb, tmp_path / "none.md")
    assert any("shots" in e for e in errs)


def test_schema_rejects_unknown_field(sb, tmp_path):
    sb["shots"][0]["colour"] = "blue"
    assert storyboard.validate(sb, tmp_path / "none.md")


def test_unknown_character_reference(sb, tmp_path):
    sb["shots"][0]["characters"] = ["ghost"]
    errs = storyboard.validate(sb, tmp_path / "none.md")
    assert any("unknown character 'ghost'" in e for e in errs)


def test_duplicate_shot_ids(sb, tmp_path):
    sb["shots"][1]["id"] = sb["shots"][0]["id"]
    assert any("duplicate" in e for e in storyboard.validate(sb, tmp_path / "none.md"))


def test_wan_frames_must_be_4k_plus_1(sb, tmp_path):
    sb["render"]["wan"]["num_frames"] = 120
    assert any("4k+1" in e for e in storyboard.validate(sb, tmp_path / "none.md"))


def test_music_cue_order_and_chosen_range(sb, tmp_path):
    cue = sb["music"]["cues"][0]
    cue["from_shot"], cue["to_shot"] = cue["to_shot"], cue["from_shot"]
    cue["chosen"] = cue["candidates"]
    errs = storyboard.validate(sb, tmp_path / "none.md")
    assert any("comes after" in e for e in errs)
    assert any("candidates" in e for e in errs)


def test_narration_needs_subtitle(sb, tmp_path):
    sb["shots"][0]["subtitle"] = ""
    assert any("subtitle" in e for e in storyboard.validate(sb, tmp_path / "none.md"))


def test_consent_gate_blocks_real_person_without_record(sb, tmp_path):
    sb["characters"][0]["real_person"] = True
    errs = storyboard.validate(sb, tmp_path / "none.md")
    assert any("consent_ref" in e for e in errs)  # schema: consent_ref required

    sb["characters"][0]["consent_ref"] = "consent-grandmother"
    errs = storyboard.validate(sb, tmp_path / "none.md")
    assert any("not found" in e for e in errs)  # semantic: anchor must exist


def test_consent_gate_passes_with_anchor(sb, tmp_path):
    ethics = tmp_path / "ETHICS.md"
    ethics.write_text('## Grandmother <a id="consent-grandmother"></a>\nConsent recorded.\n')
    sb["characters"][0].update(real_person=True, consent_ref="consent-grandmother")
    sb["voice"].update(real_person=True, consent_ref="consent-grandmother")
    assert storyboard.validate(sb, ethics) == []


def test_image_prompt_appends_character_and_style(sb):
    shot = next(s for s in sb["shots"] if s.get("characters"))
    prompt = storyboard.image_prompt(sb, shot)
    assert prompt.startswith(shot["image_prompt"].strip())
    assert sb["characters"][0]["description"] in prompt
    assert prompt.rstrip(".").endswith(sb["style"]["block"].rstrip("."))


def test_warnings_flag_placeholder_and_length(sb):
    sb["status"] = "placeholder"
    sb["shots"][0]["duration_s"] = 15
    for s in sb["shots"]:
        s["duration_s"] = 15
    w = storyboard.warnings(sb)
    assert any("placeholder" in x for x in w)
    assert any("outside" in x for x in w)


def test_load_reports_invalid_json(tmp_path):
    bad = tmp_path / "sb.json"
    bad.write_text("{nope")
    try:
        storyboard.load(bad, tmp_path / "e.md")
    except storyboard.StoryboardError as exc:
        assert "not valid JSON" in str(exc)
    else:
        raise AssertionError("expected StoryboardError")
