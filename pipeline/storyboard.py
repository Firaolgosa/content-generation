"""Load and validate storyboard.json: JSON Schema first, then rules a schema cannot express.

Run directly:  uv run python -m pipeline.storyboard [path]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from pipeline.common import ETHICS, SCHEMA, STORYBOARD, say

TARGET_MIN_S = 60.0
TARGET_MAX_S = 90.0
# Rough speaking rate used only for a pre-TTS duration warning (Amharic is denser per char).
CHARS_PER_SECOND_ESTIMATE = 12.0


class StoryboardError(ValueError):
    """The storyboard violates the schema or a cross-field rule. Message lists every problem."""


def _schema_errors(sb: dict[str, Any]) -> list[str]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(sb), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]


def _consent_anchors(ethics_path: Path) -> set[str]:
    """Anchors are declared in ETHICS.md as `<a id="consent-xyz"></a>` or `{#consent-xyz}`."""
    if not ethics_path.exists():
        return set()
    text = ethics_path.read_text(encoding="utf-8")
    return set(re.findall(r'id="([\w-]+)"', text)) | set(re.findall(r"\{#([\w-]+)\}", text))


def _semantic_errors(sb: dict[str, Any], ethics_path: Path) -> list[str]:
    errs: list[str] = []
    shot_ids = [s["id"] for s in sb["shots"]]
    dupes = {i for i in shot_ids if shot_ids.count(i) > 1}
    if dupes:
        errs.append(f"shots: duplicate ids {sorted(dupes)}")

    char_ids = {c["id"] for c in sb.get("characters", [])}
    for shot in sb["shots"]:
        for cid in shot.get("characters", []):
            if cid not in char_ids:
                errs.append(f"shots/{shot['id']}: unknown character '{cid}'")
        if shot["narration"].strip() and not shot["subtitle"].strip():
            errs.append(f"shots/{shot['id']}: narration has no English subtitle")

    order = {sid: i for i, sid in enumerate(shot_ids)}
    for cue in sb["music"]["cues"]:
        a, b = order.get(cue["from_shot"]), order.get(cue["to_shot"])
        if a is None or b is None:
            errs.append(f"music/{cue['id']}: from_shot/to_shot must be existing shot ids")
        elif a > b:
            errs.append(f"music/{cue['id']}: from_shot comes after to_shot")
        chosen = cue.get("chosen")
        if chosen is not None and chosen >= cue["candidates"]:
            errs.append(f"music/{cue['id']}: chosen={chosen} but only {cue['candidates']} candidates")

    nf = sb["render"]["wan"]["num_frames"]
    if (nf - 1) % 4:
        errs.append(f"render/wan/num_frames: {nf} is not 4k+1 (try {nf - (nf - 1) % 4})")

    # Consent gate: a real person shown or voiced needs an anchor in ETHICS.md.
    anchors = _consent_anchors(ethics_path)
    people = [(f"characters/{c['id']}", c) for c in sb.get("characters", [])]
    people.append(("voice", sb["voice"]))
    for where, entry in people:
        if not entry.get("real_person"):
            continue
        ref = entry.get("consent_ref")
        if not ref:
            errs.append(f"{where}: real_person=true requires consent_ref")
        elif ref not in anchors:
            errs.append(f"{where}: consent_ref '{ref}' not found in {ethics_path.name} "
                        "-- record consent before generating anything of this person")
    return errs


def validate(sb: dict[str, Any], ethics_path: Path = ETHICS) -> list[str]:
    """Return a list of human-readable problems; empty means valid."""
    errs = _schema_errors(sb)
    if errs:  # semantic checks assume the shape is right
        return errs
    return _semantic_errors(sb, ethics_path)


def warnings(sb: dict[str, Any]) -> list[str]:
    """Non-fatal advice (duration outside target, long lines)."""
    out: list[str] = []
    planned = sum(s["duration_s"] for s in sb["shots"]) + sb["end_card"]["duration_s"]
    if not TARGET_MIN_S <= planned <= TARGET_MAX_S:
        out.append(f"planned length {planned:.0f}s is outside {TARGET_MIN_S:.0f}-{TARGET_MAX_S:.0f}s")
    for s in sb["shots"]:
        est = len(s["narration"]) / CHARS_PER_SECOND_ESTIMATE
        if est > s["duration_s"]:
            out.append(f"shots/{s['id']}: narration (~{est:.1f}s) may outrun the shot "
                       f"({s['duration_s']}s); the shot will be extended")
    if sb.get("status") == "placeholder":
        out.append("status=placeholder: this is pipeline test content, not the real story")
    return out


def load(path: Path = STORYBOARD, ethics_path: Path = ETHICS) -> dict[str, Any]:
    """Load and validate; raise StoryboardError listing every problem."""
    try:
        sb = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StoryboardError(f"{path.name} is not valid JSON: {exc}") from exc
    errs = validate(sb, ethics_path)
    if errs:
        raise StoryboardError(f"{path.name} failed validation:\n  - " + "\n  - ".join(errs))
    return sb


# ------------------------------------------------------------------- prompt helpers


def characters_for(sb: dict[str, Any], shot: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {c["id"]: c for c in sb.get("characters", [])}
    return [by_id[c] for c in shot.get("characters", [])]


def image_prompt(sb: dict[str, Any], shot: dict[str, Any]) -> str:
    """Shot prompt + verbatim character descriptions + the fixed style block (in that order)."""
    parts = [shot["image_prompt"].strip()]
    parts += [c["description"].strip() for c in characters_for(sb, shot)]
    parts.append(sb["style"]["block"].strip())
    return " ".join(p if p.endswith(".") else p + "." for p in parts)


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else STORYBOARD
    try:
        sb = load(path)
    except StoryboardError as exc:
        say(f"INVALID  {exc}")
        return 1
    for w in warnings(sb):
        say(f"warning  {w}")
    total = sum(s["duration_s"] for s in sb["shots"])
    say(f"OK  {path.name}: {len(sb['shots'])} shots, ~{total:.0f}s planned + end card, "
        f"{len(sb['music']['cues'])} music cue(s), language={sb['language']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
