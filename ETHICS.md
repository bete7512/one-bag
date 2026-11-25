# Ethics: consent, licences, labelling

The film is about real people. One rule can zero the film: a real person shown or voiced without a consent record here. So the rule is enforced in code as well as written down.

## Consent

Each real person in `storyboard.json` has a `consent.record` id that points at a row below. The pipeline generates a picture of that person only when the storyboard says `"status": "recorded"` **and** the row has a date. Until then the shot gets a plain card and the final-cut check fails. To record a consent: fill in the row, then change the status in the storyboard.

| ID | Person | What appears in the film | How consent was given | Date (YYYY-MM-DD) |
|---|---|---|---|---|
| consent-author | The author (me) | An AI-drawn character standing for me in 2019 and today. My words in the narration. No real photo. No recording or clone of my voice. | To fill in: my own statement | |
| consent-friend | The friend who took me to Autobus Tera | An AI-drawn character standing for him, seen from behind only. He does not speak. No real photo, no voice. | To fill in: message, which app. Screenshot kept privately, not in this repository. | |

Notes to fill in when the rows are dated:

- What I asked my friend, in my own words:
- Whether he agreed to his name being used (it is not used in the film as drafted):
- If he had said no: the shot would be redrawn without him (s06), and that change would be logged in `DESIGN.md`.

Words in a real person's mouth: only mine. The narration is first person and I approve every line. A line marked `"confirmed": false` in the storyboard has not been approved yet, and `make release` refuses to build while one remains.

## Voice

The narrator is a prebuilt text-to-speech voice (`voice.name` in the storyboard). No voice is cloned. If that ever changes, the person's recorded consent comes first.

## Licences

Checked means the licence or terms page was read on that date. Rows marked "agent" were read by the coding agent while building, and I still have to read them myself. Empty means not checked yet.

| What | Used for | Licence or terms | Source | Checked on |
|---|---|---|---|---|
| Wan 2.2 TI2V-5B | moving shots | Apache 2.0 | model card, huggingface.co/Wan-AI/Wan2.2-TI2V-5B | 2026-11-25 (agent) |
| ACE-Step 1.5 (code) | score | MIT | github.com/ACE-Step/ACE-Step-1.5 | 2026-11-25 (agent) |
| ACE-Step 1.5 (model and outputs) | score | The challenge brief says MIT, outputs usable commercially. To confirm on the model card. | model card | |
| FLUX.2 klein 4B | keyframes | The challenge brief says Apache 2.0. Cloudflare's model page points to Black Forest Labs' terms. To confirm. | developers.cloudflare.com/workers-ai/models/flux-2-klein-4b | |
| FLUX.1 schnell (fallback) | keyframes | To confirm | Cloudflare model page | |
| Gemini 3.8 Flash and Flash TTS | subtitles, judge, listening check, narration | Gemini API terms. To confirm: what the free tier may do with the content sent to it. | ai.google.dev | |
| FFmpeg | assembly | LGPL/GPL tool. It places no licence on the film. | ffmpeg.org | |
| Subtitle font | subtitles, end card | A system font (Arial or the system's substitute) | | |

## Private data

Free endpoints may use what is sent to them to improve their models. So prompts describe a generic young man, a bag and places that are public. No family names, phone numbers, addresses or real photos are sent to any model. The friend's name is not in the storyboard.

## Labelling

- The film ends with a card: "Made with AI", for three seconds, in both exports. The final-cut check fails without it.
- When I post, the platform's AI label is switched on.
- The untouched files that come back from the image model are kept in `outputs/keyframes/original/`, so any provenance metadata in them is not thrown away. The final MP4 is re-encoded by FFmpeg, so metadata inside those images does not travel into it: the end card and the platform label carry the disclosure. I do not remove any watermark.
- The look is described by its qualities (painted, grainy, warm). No living artist is named in any prompt.
