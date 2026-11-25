"""Stage: script. Draft a storyboard from a plain-language story brief with Gemini.

Writes storyboard.draft.json (never overwrites storyboard.json). The draft is validated
against the schema; validation errors are fed back to the model for up to 3 attempts.
Technical sections (models, render, mix) are copied from the current storyboard so the
model only writes the story. Review the draft, then copy it over storyboard.json yourself.

Run:  uv run python -m pipeline.script story/brief.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pipeline import storyboard
from pipeline.common import ROOT, SCHEMA, STORYBOARD, CallSpec, call_logged, say, write_json
from pipeline.providers import gemini

DRAFT = ROOT / "storyboard.draft.json"
MAX_ROUNDS = 3
KEEP = ("version", "models", "render", "mix", "voice", "end_card")

INSTRUCTIONS = """You are a documentary short-film writer and storyboard artist.
Write a storyboard for a 60-90 second vertical-first heritage short film, as JSON that
validates against the JSON Schema below. Rules:
- 8 to 12 shots, about 6-8 seconds each. One idea and one gentle movement per shot.
- Vary shot sizes: open with a wide establishing shot; use close-ups for feeling.
- Every shot has a one-sentence `reason` saying why it exists.
- `narration` is in {language_name}, written for the ear: short sentences, concrete images,
  no tongue-twisters. Total narration 130-200 words across all shots.
- `subtitle` is a faithful, natural English translation of that shot's narration.
- `image_prompt` describes subject, place and composition with the subject centred
  (we crop 9:16 and 16:9 from one frame). No text, signs or writing in the image.
- `motion_prompt` describes only motion and camera (the image already holds the subject).
- Prefer `video: "wan"` for the 4-6 shots where motion matters most, `kenburns` for the rest.
- Do not name living artists. Describe qualities (warm, grainy, hand-painted) instead.
- Keep characters to at most two, each with a fixed physical description.
- Mark `real_person: true` for anyone real; leave `consent_ref` for the human to fill.
- Set "status": "draft".
Return only the JSON object.

Keep these sections exactly as given:
{keep}

JSON Schema:
{schema}

Story brief from the filmmaker:
{brief}
"""

LANGUAGE_NAMES = {"am": "Amharic", "om": "Afaan Oromo", "ti": "Tigrinya", "so": "Somali",
                  "en": "English"}


def _prompt(brief: str, current: dict[str, Any], feedback: list[str]) -> str:
    keep = {k: current[k] for k in KEEP if k in current}
    text = INSTRUCTIONS.format(
        language_name=LANGUAGE_NAMES.get(current.get("language", "am"), current.get("language")),
        keep=json.dumps(keep, ensure_ascii=False, indent=1),
        schema=SCHEMA.read_text(encoding="utf-8"), brief=brief.strip())
    if feedback:
        text += "\n\nYour previous draft failed validation. Fix exactly these problems:\n- "
        text += "\n- ".join(feedback)
    return text


def draft(brief_path: Path) -> Path:
    current = json.loads(STORYBOARD.read_text(encoding="utf-8"))
    brief = brief_path.read_text(encoding="utf-8")
    model = current["models"]["text"]
    feedback: list[str] = []
    for round_no in range(1, MAX_ROUNDS + 1):
        spec = CallSpec(stage="script", provider="gemini", model=model, item=f"draft#{round_no}",
                        params={"brief_chars": len(brief), "feedback": len(feedback)})
        prompt = _prompt(brief, current, feedback)
        raw = call_logged(spec, lambda p=prompt: gemini.generate_text(p, model=model, json_mode=True),
                          describe=lambda r: {"response_chars": len(r)})
        try:
            sb = json.loads(raw)
        except json.JSONDecodeError as exc:
            feedback = [f"response was not valid JSON: {exc}"]
            continue
        for k in KEEP:  # enforce the technical sections regardless of what the model wrote
            if k in current:
                sb[k] = current[k]
        write_json(DRAFT, sb)
        feedback = storyboard.validate(sb)
        if not feedback:
            say(f"  draft valid after {round_no} round(s) -> {DRAFT.name}")
            return DRAFT
        say(f"  round {round_no}: {len(feedback)} problem(s); asking for a fix")
    say(f"  ! draft still has problems (see below); saved to {DRAFT.name} for hand editing")
    for f in feedback:
        say(f"    - {f}")
    return DRAFT


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brief", type=Path, help="plain-text story brief (e.g. story/brief.md)")
    args = ap.parse_args(argv)
    draft(args.brief)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
