# Ethics: consent, licences, labelling

## Consent records

The pipeline enforces this file. Any character or voice in `storyboard.json` with
`"real_person": true` needs a `consent_ref` that matches an anchor here, such as
`<a id="consent-grandmother"></a>`. Otherwise `make validate` fails and nothing is generated.

Record consent **before** generating anything of a real person.

<!-- Template: copy one block per real person shown or voiced.

### <Name or role> <a id="consent-NAME"></a>
- **Who:** name, relationship to me
- **What they agreed to:** their likeness depicted (illustrated / photoreal?), their story
  told, their voice replicated (yes/no), the exact narration words (attached / read to them)
- **Where it will appear:** public post on <platform>, family group, assignment submission
- **How consent was given:** in person / voice note / message, on <date>; evidence kept at <where>
- **They can withdraw:** yes, by telling me; I will take the film down
-->

_This film depicts a true family story from Bekoji (1950 E.C.) using stylized painterly illustrations and a prebuilt Gemini TTS voice (`Sulafat`). No real person's face, photograph, likeness, or cloned voice is used (`"real_person": false` for all characters and voice). Private full names are omitted from all prompts sent to free-tier APIs._

## Licences of models and outputs

| Use | Model / tool | Licence / terms | Notes |
|---|---|---|---|
| Script, translation | Gemini 3.8 Flash (Gemini API, free tier) | Gemini API Additional Terms | Free-tier prompts may be used to improve Google's products, so private family details stay out of prompts |
| Narration | Gemini 3.8 Flash TTS (Gemini API, free tier) | Gemini API Additional Terms | Prebuilt voice only, so no voice cloning unless consent is recorded above |
| Keyframes | FLUX.2 klein 4B on Cloudflare Workers AI | Apache 2.0 (model); Cloudflare and BFL terms of service | Cloudflare lists it as zero data retention. The 9B variant is non-commercial and is **not** used |
| Keyframes (fallback) | FLUX.1 schnell on Cloudflare Workers AI | Apache 2.0 | |
| Moving shots | Wan 2.2 TI2V-5B (open weights, Kaggle) | Apache 2.0 | Wan claims no rights over outputs |
| Score | ACE-Step 1.5 turbo (open weights, Kaggle) | MIT (code); outputs usable commercially per the brief | TODO: confirm the weights licence on the Hugging Face model card |
| Assembly | FFmpeg | LGPL/GPL (tool, not distributed) | |
| Fonts | Noto Sans, Noto Sans Ethiopic | SIL OFL 1.1 | Bundled in `assets/fonts/` |

## Labelling plan

- **In the film:** a 3-second end card in Amharic and English says it was made with AI and
  names the models.
- **In the file:** MP4 metadata `comment` says "Made with AI" and lists every model. No
  watermark or provenance metadata from upstream models is stripped.
- **On the platform:** the platform's AI-content disclosure is switched on when posting
  (YouTube "altered or synthetic content", TikTok "AI-generated", Meta "AI info").
- **Style:** prompts describe qualities (warm, painterly, grainy) and never name living artists.
