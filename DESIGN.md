# Design

> Written **before** generating anything of the real story. Sections marked **TODO** must
> come from real conversations. Do not fill them in from imagination.

## Audience and intent

- **Who watches:** My family (parents, aunts, uncles, and cousins), watching on their phones.
- **Where they watch:** In our family group chat (WhatsApp/Telegram), sound on, vertical (9:16).
- **What they should feel or understand at the end:** Warmth, pride, and a vivid connection to how their parents' and grandparents' story began in Bekoji in 1950 E.C.
- **How might we:** How might we help my family feel the serendipity and warmth of the night our grandparents met in Bekoji?
- **Story in three to five sentences (one picture per beat):** In 1950 E.C. in Bekoji, my grandfather and his friend were travelling to see another girl when night fell late. They stopped at a house along the way to ask for shelter for the night. Inside by the hearth, my grandfather met my grandmother for the first time. By morning, he chose her over his original journey—and our family's story began.
- **Whose story it is, and how they took part:** A true family story about my maternal/paternal grandparents. No real faces, likenesses, or voices are used (`real_person: false`, documented in [ETHICS.md](ETHICS.md)).

## Constraints that shaped the design

- 60–90 s, vertical first (phone feeds); every keyframe is composed with the subject centred so
  one frame serves both 9:16 and 16:9.
- Amharic narration, about 130–200 words, measured from the TTS output rather than guessed.
- At most two main characters (`grandfather`, `grandmother`), so identity drift stays manageable.
- GPU time is the binding constraint: Wan only on the 4 shots where motion matters (`s02`, `s04`, `s05`, `s07`), Ken Burns moves elsewhere (decided per shot in `shots[].video`).

## Shot list and reasons

Every shot carries a `reason` in `storyboard.json`.

| Shot | Size | Reason |
|---|---|---|
| `s01` | `extreme_wide` | Establishing shot: sets the year (1950 E.C.) and cold highland town of Bekoji at dusk. |
| `s02` | `wide` | Shows the original journey—the grandfather and his friend walking to see another girl. |
| `s03` | `medium` | Nightfall forces the turn in the story: seeking shelter at a warm, lit home. |
| `s04` | `medium_close` | Establishes the warmth and traditional hospitality inside the grandmother's home. |
| `s05` | `close_up` | The turning point: grandfather sees the grandmother for the first time by firelight. |
| `s06` | `close_up` | Focuses on her grace and warmth, explaining emotionally why he changed his mind. |
| `s07` | `medium` | Dawn in Bekoji: visually marks his quiet decision to choose her instead of continuing. |
| `s08` | `wide` | Time compression: two figures walking together across Bekoji's sunlit hills. |
| `s09` | `medium_close` | Closing motif: two coffee cups (sini) steaming by a window—legacy and family warmth. |

## User test 1: the radio cut

- **Prototype:** `outputs/final/radio_cut.mp4` (narration plus placeholder bed on black,
  English subtitles). Run ID: `20261125T125406Z-2802` (75.0s, -14 LUFS)
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

- **Prototype:** `outputs/final/the-night-in-bekoji_9x16.mp4`. Run ID: TODO
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
| Narration voice | `Sulafat` (warm, unhurried) | Tested in smoke test on Amharic; clear and natural cadence. |
| Score candidate | see `EXPERIMENTS.md` | |
