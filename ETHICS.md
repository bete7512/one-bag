# Ethics: consent, licences, labelling

The film is about real people. One rule can zero the film: a real person shown or voiced without a consent record here. So the rule is enforced in code as well as written down.

## Consent

Each real person in `storyboard.json` has a `consent.record` id that points at a row below. The pipeline generates a picture of that person only when the storyboard says `"status": "recorded"` **and** the row has a date. Until then the shot gets a plain card and the final-cut check fails. To record a consent: fill in the row, then change the status in the storyboard.

| ID | Person | What appears in the film | How consent was given | Date (YYYY-MM-DD) |
|---|---|---|---|---|
| consent-author | The author (me) | An AI-drawn character standing for me in 2019 and today. My words in the narration. No real photo. No recording or clone of my voice. | My own statement, given in writing in the working session with the coding agent, before any picture of the character was generated. | 2026-11-25 |
| consent-friend | The friend who was waiting for me at Lamberet | An AI-drawn character standing for him, seen from behind only. He does not speak. No real photo, no voice. | In writing: he answered "yes" to my message that described the film and how he is shown in it. Screenshot kept privately, not in this repository. | 2026-11-25 |

Notes on the friend's consent:

- What he was told before he answered: that the film is about the night I first arrived in Addis Ababa, that it is made with AI, that one scene shows an AI-drawn young man seen from behind who stands for him, that his photo, voice and name are not in it, and that I post the film publicly.
- His name is not used in the film or anywhere in this repository, so there was nothing to agree to about it.
- If he had said no, shot s06 would have been redrawn without him and the change logged in `DESIGN.md`. The pipeline held the shot back until his answer was recorded.
- **He is in one shot, as he was told.** On the evening of 25 November, after I told the story in full, a rewritten storyboard had him in three shots (s04, s06 and s08). That was more than the one scene he had agreed to. It was changed back the same evening, before any picture left my machine: he is drawn in s06 only, with the brokers. At Lamberet and in the ticket queue the frame holds me alone, and the voice says he was there.

Words in a real person's mouth: only mine. The narration is first person and I approve every line. A line marked `"confirmed": false` in the storyboard has not been approved yet, and `make release` refuses to build while one remains.

## Voice

The narrator is a prebuilt text-to-speech voice (`voice.name` in the storyboard). No voice is cloned. If that ever changes, the person's recorded consent comes first.

## Licences

Checked means the licence or terms page was opened on that date and the words quoted were on it. Rows marked "agent" were read by the coding agent, which opened each page and copied the quote. I still have to read them myself.

| What | Used for | Licence or terms, in the page's own words | Source | Checked on |
|---|---|---|---|---|
| FLUX.2 klein 4B (weights) | keyframes | Apache 2.0. "Open weights available for commercial use under the Apache 2.0 license." | huggingface.co/black-forest-labs/FLUX.2-klein-4B | 2026-11-25 (agent) |
| FLUX.2 klein 4B on Cloudflare Workers AI | keyframes | The model page links to Black Forest Labs' terms of service. They claim no ownership of the pictures. They forbid passing a picture off as made by a person: you may not "create, use or distribute Output in a fraudulent or misleading way, including, for instance, by representing that the Output is entirely human-generated". | developers.cloudflare.com/workers-ai/models/flux-2-klein-4b and bfl.ai/legal/terms-of-service | 2026-11-25 (agent) |
| FLUX.1 schnell (fallback, not used so far) | keyframes | Apache 2.0. "Released under the apache-2.0 licence, the model can be used for personal, scientific, and commercial purposes." | huggingface.co/black-forest-labs/FLUX.1-schnell | 2026-11-25 (agent) |
| ACE-Step 1.5 (code) | score | MIT, in the LICENSE file. The README asks users to "clearly disclose AI involvement". | github.com/ace-step/ACE-Step-1.5 | 2026-11-25 (agent) |
| ACE-Step 1.5 (model and its music) | score | MIT. "You can strictly use the generated music for commercial purposes." | huggingface.co/ACE-Step/Ace-Step1.5 | 2026-11-25 (agent) |
| Wan 2.2 TI2V-5B | moving shots | Apache 2.0. "We claim no rights over the your generated contents, granting you the freedom to use them while ensuring that your usage complies with the provisions of this license." | huggingface.co/Wan-AI/Wan2.2-TI2V-5B and the -Diffusers card | 2026-11-25 (agent) |
| Gemini API, unpaid tier: `gemini-3.8-flash-tts`, `gemini-3.5-flash-lite`, `gemini-3.8-flash` | narration, listening check, first judge | Gemini API Additional Terms of Service. "Google won't claim ownership over that content." On the unpaid tier, what is sent and what comes back is used to improve Google's products, and "human reviewers may read, annotate, and process your API input and output". See Private data below. | aistudio.google.com/docs/terms and aistudio.google.com/docs/pricing | 2026-11-25 (agent) |
| Claude API: `claude-opus-5-5` | picture judge, subtitle check | Anthropic Commercial Terms of Service. "Customer (a) retains all rights to its Inputs, and (b) owns its Outputs." and "Anthropic may not train models on Customer Content from Services." | anthropic.com/legal/commercial-terms | 2026-11-25 (agent) |
| Kaggle | the GPU for the score and the moving shots | Kaggle Terms: "You will only use the Services for your own internal, personal, non-commercial use". This film is a personal project and earns nothing. The page did not load as text for the agent, which read the words in the page's source: I check it in a browser before I rely on it. | kaggle.com/terms | 2026-11-25 (agent, from the page source) |
| FFmpeg | assembly | LGPL/GPL tool. It places no licence on the film. | ffmpeg.org | |
| Subtitle font | subtitles, end card | A system font (Arial or the system's substitute) | | |

Two things in these terms shaped the film. Both Black Forest Labs and Google forbid presenting generated content as made only by a person, and ACE-Step asks for disclosure: the end card and the platform's AI label do that. And the unpaid Gemini tier may keep and read what it is sent, which decides what goes into a prompt.

## Private data

What leaves my machine, and to whom:

- **The narration lines** go to the Gemini API on its unpaid tier, to be spoken and then listened to. They are my own story in my own words. Under the terms above Google may use them to improve its products and a human reviewer may read them. The lines hold no person's name. The only names in them are places: Ankober, Debre Birhan, Lamberet, Autobus Tera. The same lines, with their subtitles, go to the Claude API for the subtitle check.
- **The picture prompts** go to Cloudflare Workers AI. They describe a young man with a backpack and public places. Cloudflare's page for the model lists zero data retention. The pictures that come back go to the Claude API to be judged. Anthropic's terms say it does not train on them.
- **The score's description** goes to Kaggle in a private dataset, and the three candidates were sent to the unpaid Gemini tier to be described. For the moving shots the chosen pictures go to Kaggle the same way.
- **Nothing else.** No family name, phone number, address or real photo is sent to any model. My friend's name is not in the storyboard or anywhere in this repository.

## Labelling

- The film ends with a card: "Made with AI", for three seconds, in both exports. The final-cut check fails without it.
- When I post, the platform's AI label is switched on.
- The untouched files that come back from the image model are kept in `outputs/keyframes/original/`, so any provenance metadata in them is not thrown away. The final MP4 is re-encoded by FFmpeg, so metadata inside those images does not travel into it: the end card and the platform label carry the disclosure. I do not remove any watermark.
- The look is described by its qualities (painted, grainy, warm). No living artist is named in any prompt.
