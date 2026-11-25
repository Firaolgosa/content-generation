# Design

> Written **before** generating anything of the real story. Sections marked **TODO** must
> come from real conversations. Do not fill them in from imagination.

## Audience and intent

- **Who watches:** TODO (e.g. "my cousins in the diaspora, 18–35, and my aunts in Addis")
- **Where they watch:** TODO (e.g. "on their phones, in the family WhatsApp group, sound on, vertical")
- **What they should feel or understand at the end:** TODO (one sentence)
- **How might we:** TODO ("How might we help ___ feel ___?")
- **Story in three to five sentences (one picture per beat):** TODO
- **Whose story it is, and how they took part:** TODO (link to the consent record in ETHICS.md)

## Constraints that shaped the design

- 60–90 s, vertical first (phone feeds); every keyframe is composed with the subject centred so
  one frame serves both 9:16 and 16:9.
- Amharic narration, about 130–200 words, measured from the TTS output rather than guessed.
- At most two characters, so identity drift stays manageable.
- GPU time is the binding constraint: Wan only on the 4–6 shots where motion matters, Ken
  Burns moves elsewhere (decided per shot in `shots[].video`).

## Shot list and reasons

Every shot carries a `reason` in `storyboard.json`. Summary table (regenerate once the
story is locked):

| Shot | Size | Reason |
|---|---|---|
| TODO | | |

## User test 1: the radio cut

- **Prototype:** `outputs/final/radio_cut.mp4` (narration plus placeholder bed on black,
  English subtitles). Run ID: TODO
- **Date, format:** TODO (in person / Slack / WhatsApp voice note)
- **People (at least 3, from the intended audience):** TODO (first names or roles, with permission)
- **What we asked:** "What is this about? What do you remember? Where did you lose interest?
  Which word or name sounded wrong?"

| Person | What they said (verbatim where possible) | Where they reacted |
|---|---|---|
| TODO | | |
| TODO | | |
| TODO | | |

**Insights and what changed in the storyboard** (link to the commit or diff):
- TODO: "insight" → "change to shots[x].narration / order / duration"

## User test 2: the near-final cut

- **Prototype:** `outputs/final/<title>_9x16.mp4`. Run ID: TODO
- **People (at least 3):** TODO

| Person | What they said | Where they reacted |
|---|---|---|
| TODO | | |
| TODO | | |
| TODO | | |

**Insights and what changed:**
- TODO

## Decisions log

| Decision | Options considered | Why this one |
|---|---|---|
| Narration voice | TODO (listen to 3 voices on one line) | |
| Score candidate | see EXPERIMENTS.md | |
