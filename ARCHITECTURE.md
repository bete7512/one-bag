# Architecture

## The shape

```mermaid
flowchart LR
    SB[storyboard.json<br/>validated by schema/] --> S1[1 script]
    S1 --> S2[2 narration<br/>one take, cut into lines, listening check]
    SB --> S3[3 keyframes<br/>reference sheet, candidates, border check, judge]
    S2 --> S4[4 shots<br/>Ken Burns here, Wan 2.2 on Kaggle]
    S3 --> S4
    SB --> S5[5 music<br/>placeholder here, ACE-Step on Kaggle]
    S2 --> S6[6 assemble<br/>FFmpeg]
    S4 --> S6
    S5 --> S6
    S6 --> F[film_vertical.mp4<br/>film_horizontal.mp4]
    F --> QC[final-cut check]
```

One file is the contract. Every stage reads `storyboard.json`, does one job, and writes its outputs plus an index of what it made. No stage calls another stage's code, and no prompt, seed or model name is hidden in code: they are all in the storyboard, so a run can be reproduced and explained from one file.

## Contracts between stages

| Stage | Reads | Writes |
|---|---|---|
| script | storyboard | `outputs/script/index.<lang>.json`: the line and subtitle of every narrated shot |
| narration | script index | `outputs/narration/<shot>__<key>.wav`, the takes they were cut from in `takes/`, `index.<lang>.json` with seconds and the listening score |
| keyframes | storyboard, `ETHICS.md` | the model's pictures in `outputs/keyframes/original/`, keyframes cut from them, `index.json` with the border count, the scores and the pick |
| shots | keyframes index, narration index | `outputs/shots/<shot>_<backend>__<key>.mp4`, `index.<lang>.json`, a GPU job folder |
| music | storyboard | `outputs/music/*.wav`, `index.json`, a GPU job folder |
| assemble | all indexes | scene files, the mix, both films, `subtitles.<lang>.srt`, `index.film.<lang>.json` |

Before anything runs, `storyboard.json` is validated twice: against `schema/storyboard.schema.json`, then by checks a schema cannot express (unknown character ids, a pick that points past the candidates, a consent marked recorded with no dated row in `ETHICS.md`). An invalid storyboard stops the run before any model is called.

## Caching: only what changed is regenerated

A stage is a list of units. A unit is one thing to produce plus a **fingerprint**: a dictionary of every input that can change the output. Examples:

| Unit | Fingerprint |
|---|---|
| narration line | text, language, voice, style, model |
| keyframe candidate | full prompt, seed, model, size, keys of the reference sheets |
| Ken Burns clip | keyframe key, camera move, number of frames, size |
| scene (one shot, one export) | clip key, export size, subtitle cues, frames |
| final film | keys of all scenes in order, key of the mix |

`run_units` in `pipeline/core.py` hashes the fingerprint. If a file with that hash exists it is a hit and nothing runs. Otherwise the unit is built, written under a temporary name, renamed into place, and recorded in the stage's `manifest.json` together with its fingerprint. Because the old fingerprint is kept, a miss can say which input changed: `MISS (changed: text)`.

Keys flow downstream. A scene's fingerprint holds its clip's key, and the clip's fingerprint holds its keyframe's key. So a new keyframe prompt regenerates that keyframe, that clip and that scene, and nothing else. Old files are kept, so going back to an earlier prompt is a hit.

`python -m pipeline plan` runs the same code with building switched off. It calls no model and prints what the next run would do.

### What the model sent is kept as it came

Two stages keep the model's answer untouched and cut what the film needs from it with FFmpeg:

- **Pictures.** Each answer of the image model is stored in `outputs/keyframes/original/` under a hash of what was sent to the model. The keyframe is cut from that file: scaled to the master size, with `format.edge_trim` taken off each side. The model is called only when no original exists, so a change to the cut costs nothing.
- **Narration.** The lines missing from the cache are spoken in one request, a take, kept in `outputs/narration/takes/`. Each line carries a `<long pause>` tag at its end, and the take is cut at its longest pauses into one file per line. When those pauses do not stand out, each phrase of the take is transcribed and matched to the script, and a line is kept only where both methods put its two ends in the same place. Any other line is spoken again in a request of its own: nothing is guessed. The first real take needed this for four of its eight lines (F04 in `FAILURES.md`). The per-line files keep their own fingerprints, so everything downstream is unchanged, and a single changed line is spoken alone.

The reason for the take is a limit, not taste: the free speech tier allows ten requests a day. A request per line would spend eight of them on one pass. The first pass cost five.

## The run log

`runs.jsonl` gets one line for every attempt of every real model call, failed attempts too. Fields on every line:

| Field | Meaning |
|---|---|
| `ts`, `run_id` | when, and which run of the pipeline |
| `stage`, `unit` | which stage, and which unit of work (`s04`, `s07_c2_judge`, `take`) |
| `provider`, `model` | who was called |
| `params`, `seed` | what was asked: sizes, voice, style, hashes of the prompt text. `seed` is null where the provider has none |
| `attempt`, `status` | 1 to 4, `ok` or `error`. An error line has `http_status` and the provider's message |
| `latency_s` | measured around the request |
| `cost_usd` | the list price of the call, 0 for a failed attempt, null when the price or the usage is not known. For the models on a free tier it is what the call would have cost. For Claude, which has none, it is what was paid. The first 35 lines of the log, up to 11:18 UTC on 25 Nov, were written before this field existed and do not have it: the log is never rewritten |

A successful line also carries what its price depends on: token counts for text, seconds of audio for speech, and for GPU work the minutes and the peak memory that the job measured itself. Prices and their sources are in `pricing.json`, and the arithmetic is in `pipeline/pricing.py`.

## Failure handling

| What can go wrong | What the pipeline does |
|---|---|
| A server error, a network error or a timeout | Up to four attempts, with waits of 10, 30 and 90 seconds, or the provider's `Retry-After` when given. Every attempt is one line in `runs.jsonl`. The first waits were 2, 4 and 8 seconds, which an overloaded model outlasted (F01). |
| A free-tier limit | The limits that apply to this project are in `pricing.json`, and the run log is the counter. Before each request the day's use is read: over a daily limit the request is not sent and the message says when the allowance resets, and a per-minute limit is waited out. |
| A rejected request (HTTP 400, 401, 403, 404) | No retry. The error names the likely cause (wrong model id, bad key, no access). |
| A check cannot reach its model | The picture judge, the subtitle check and the listening check only measure, so they are optional units: the stage goes on without the result, the final-cut check lists what is missing, and the next run tries again. |
| A provider changes its response shape | Responses are parsed tolerantly: the audio or image is searched for in the JSON, not read from one fixed path. |
| A stopped run | Files are written under a temporary name and renamed when complete, so a half-written file is never used. The next run continues from the cache. |
| A picture comes back with a paper border | Each candidate's four sides are measured for bare paper. The pick prefers the candidate with the fewest, and the final-cut check lists a pick that still has a border. |
| A take cannot be cut into its lines with certainty | The lines that the pauses and the words agree on are kept. Each other line is spoken again alone. The take is kept, so a better way of cutting costs no speech request. |
| The GPU job fails or has not run yet | The shot falls back to a pan and zoom over its keyframe. The index marks it `kenburns_fallback` and the final-cut check lists it. |
| One clip fails on the GPU | The job script catches it, records the error and the peak memory, and goes on to the next clip. `results.json` is rewritten after every clip. |
| A generated clip is shorter than its shot | It is slowed by at most 25%. The rest of the shot is a slow push in over the clip's last frame, so the picture never freezes under the voice. The final-cut check lists the shots and the seconds. |
| A real person's consent is missing | The keyframe is not generated. The shot gets a plain card so the cut still assembles, and the final-cut check fails. |
| The image model ignores or rejects a seed | The call is repeated without it and the log line says `seed_applied: false`. |

## Providers

Request shapes were taken from each provider's documentation on 25 Nov 2026. They live in `pipeline/providers.py`.

| Job | Call |
|---|---|
| Speech | `POST https://generativelanguage.googleapis.com/v1beta/interactions`, model `gemini-3.8-flash-tts`, style given as a `speech_metadata` annotation, a prebuilt voice. A take sends each line as its own content item. Returns WAV, 24 kHz mono. No seed parameter is documented, so speech is logged with `seed: null`. |
| Text, vision, listening | `POST .../v1beta/models/gemini-3.5-flash-lite:generateContent`, with images or audio as inline parts. |
| Picture judge, subtitle check | `claude-opus-5-5` through the Anthropic SDK, with a JSON schema for the answer. Used while `models.judge` names it. It takes pictures and text, not audio, so the listening check stays on Gemini. |
| Images | `POST https://api.cloudflare.com/client/v4/accounts/<id>/ai/run/@cf/black-forest-labs/flux-2-klein-4b` as a multipart form (prompt, width, height, up to four reference images under 512 px). `flux-1-schnell` takes JSON instead, and the client handles both. |
| Video | Wan 2.2 TI2V-5B through Diffusers in `kaggle/wan22_i2v.py`, run on Kaggle by `pipeline/kagglerun.py`. |
| Music | ACE-Step 1.5 through its Python API in `kaggle/acestep_music.py`, run the same way. |

## Sound

1. Each narration line is placed on the timeline at its shot's start plus a short lead-in. Picture follows the voice: a shot lasts as long as its line needs and never less than its `min_duration_s`.
2. Voice and score are first brought to known levels (voice -16 LUFS, score -24 LUFS), so the balance is a decision and not a repair. Each narration line is levelled on its own: lines that come from different speech requests differed by 4 dB in the first mix.
3. The score is ducked under the voice with FFmpeg's `sidechaincompress` (threshold 0.02, ratio 6, attack 300 ms, release 1500 ms). Both of its inputs are cut into blocks of 1024 samples first: with blocks of different sizes a FLAC score came out 1.3 s short.
4. The mix is brought toward -14 LUFS with one fixed gain. It is measured with FFmpeg's EBU R128 meter. If the gain it needs would push a peak over -1.7 dBTP, the peaks in the way are limited once (`alimiter`, 5 ms attack, 50 ms release), the mix is measured again, and the gain is as large as the peaks then allow. The index of the mix records the gain and the limiter's ceiling. The first real cut lands at -15.0 LUFS and -1.5 dBTP after the AAC encoder.

The brief suggests `loudnorm` in two passes for this step, and the pipeline used it at first. Measuring the mix (E12 in `EXPERIMENTS.md`) showed three things that were wrong: the voice track clipped before the loudness pass, a FLAC score lost the end of its fade, and `loudnorm` did not apply the fixed gain it was asked for. With a voice as peaky as this one it switches to riding the gain up and down, without saying so, which moves the balance that steps 2 and 3 have just set. So the last step is done in the open. Two prices are paid for that: the film is one LU quieter than the platforms' reference, because limiting harder to win it back made the encoded peaks overshoot, and the limiter delays the sound by about 5 ms.

## Picture

One encoded scene file per shot per export, subtitles burned in, all with the same encoder settings. The scenes are joined with the concat demuxer and `-c copy`, and the sound is added with `-c:v copy`. Nothing is encoded twice, and changing one shot re-encodes one scene per export.

A shot lasts as long as its narration, and a generated clip lasts a few seconds. A clip that is too short is slowed by at most 25%, and what is still missing is a slow push in over its last frame, made in the same filter as the clip so nothing changes where the two meet.

The two exports cut the square picture on different sides: the wide film loses height and the tall film loses width. So a shot says where its subject sits with `keyframe.focus_x` (0 left, 1 right) and `keyframe.focus_y` (0 top, 1 bottom), each as one number for every export or as one number per export: `{"vertical": 0.3, "horizontal": 0.5}`. The crop keeps that part, an export that is not named keeps the middle, and a changed anchor re-encodes that one scene.

Subtitles are English, at most two lines of 40 characters, timed in proportion to their length, and placed above the area that phone apps cover with buttons.

## One hard decision: two aspect ratios from one GPU budget

The brief wants 9:16 and 16:9. Generating every shot twice would double the image calls and, worse, the GPU time, which is the scarce thing here.

Options I considered:

| Option | Cost | Result |
|---|---|---|
| Generate each shot in both shapes | 2x GPU time | Best framing, not affordable |
| Vertical master, horizontal with blurred bars | 1x | Good vertical, weak horizontal |
| Horizontal master, crop for vertical | 1x | Vertical loses two thirds of the frame |
| **Square master, crop both ways** | 1x | Each export keeps 56% of the frame, full-bleed in both |

I chose the square master (1024 x 1024). Every keyframe prompt puts the subject in the centre, and the style block says so, which is what makes a centre crop safe from side to side. From top to bottom it was not: the wide film keeps the middle band of the square, and a standing figure lost its head there. So a shot can say where its subject sits (`keyframe.focus_y`, 0 for the top, 1 for the bottom), and the crop keeps that part. The rule is in code, not in my head: when a crop would lose more than 45% of a clip it is placed over a blurred copy of itself instead. With square clips that rule never fires, but it protects the film if a clip comes back in another shape.

The price is sharpness: the vertical export enlarges a 576-pixel-wide crop to 1080. A painted, grainy look hides that better than a photographic one would, which is one reason for the style. Whether viewers notice is an open question, and it is on the experiment list.

## What is not here

- No web service and no database. Files and hashes are enough at this size.
- No GPU on this machine and no paid GPU. The two GPU jobs go to Kaggle through its command line tool and come back as files.
- No scheduler and no queue. The stages run in order in one process, and the only waiting is for Kaggle.
- No voice cloning. The narrator is a prebuilt voice.
