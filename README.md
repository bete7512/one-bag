# One Bag: a heritage short, made by a pipeline

A 60 to 90 second film about the night I first arrived in Addis Ababa from Ankober in 2019, on my way to university, narrated in Amharic with English subtitles and an original score. I did not edit it by hand. This repository is the small studio that makes it: one file, `storyboard.json`, is the contract, and six stages turn it into two finished films.

```
make film        # or: python -m pipeline film
```

That one command validates the storyboard, runs every stage, regenerates only what changed, writes `outputs/film_vertical.mp4` (9:16) and `outputs/film_horizontal.mp4` (16:9), and then measures the result against the brief.

## Status

Be clear about what is proven and what is not. Last updated 26 November 2026, 02:37 East Africa Time.

| Part | Tested offline with mock providers | Run against the real model |
|---|---|---|
| Storyboard schema and checks | yes | not applicable |
| Cache, run log, retries, free-tier guard | yes | yes: the retries and the guard both met a real quota (F01, F09) |
| Script (subtitle translation) | yes | not yet: every line has a written subtitle |
| Narration (a voice of Addis AI, before it Gemini TTS) | yes | yes: ten lines, each spoken in a request of its own by the Addis AI voice `am-nahom` since 26 Nov (E26). The words are my own since that night (`DESIGN.md`). Before that a Gemini voice spoke them: a take that gave four clean lines (F04, E20), then lines that did not sound like one voice (F10, E25) |
| Narration listening check | yes | yes: all ten lines of the cut at or above the floor, the lowest at 0.93. Since 26 Nov the listener is Addis AI's speech-to-text model for Amharic, which also gives the time of each word (E27). Before it the text model listened, and gave 0.16 to lines that it wrote down in Latin letters (E21, E26). Either listener is a model: its score is a screen and not a verdict |
| Keyframes (FLUX.2 klein on Workers AI) | yes | yes: all ten shots, after a reference sheet that copied itself into the scenes (E19) and two shots that had to be redesigned (F05). On 26 Nov seven shots were drawn again from the words alone, with the colours of his clothes and backpack written into the description (E28). Since the night of 25 Nov the account is on a paid plan, and pictures beyond the free daily allowance are paid for (`COSTS.md`) |
| Keyframe judge | yes | yes, on three models (E15, E17) |
| Subtitle check | yes | yes: it found two mismatches in the first draft (E18). The ten current subtitles pass |
| Keyframe border check | yes | yes: it caught the white border on the first pictures (E16) |
| Shots: Ken Burns (FFmpeg) | yes, real FFmpeg | not applicable |
| Shots: Wan 2.2 on Kaggle | export, upload and ingest | yes: four clips of 3.4 s, 13 to 15 minutes each at about 13.5 GB of GPU memory (E08). Only the road shot uses its clip. The three other clips were made and rejected. The first job was killed after one clip (F07) |
| Music: ACE-Step on Kaggle | export, upload and ingest | yes: two sets of three candidates from two descriptions, each described by a listening model (F02, F06, E22). Candidate 2 of the second set is in the cut. The coding agent chose it from those descriptions, on my instruction to decide. I have not compared the six by ear yet |
| Assembly, ducking, loudness, both ratios | yes, real FFmpeg | yes: a rough cut of 86 s in both ratios, from the real narration and pictures. The mix was measured and rewritten twice (E12) |
| Final-cut check | yes | yes, on the rough cut of 26 Nov, 02:30: every measured check passes. Its one note says what a person still has to look at: three picked pictures that the judge scored under 3 (s03, s05, s06) |

`runs.jsonl` holds one line per attempt of a real model call: 745 at 02:33 on 26 Nov. Mock runs write to `outputs_mock/`, which is git-ignored and is never evidence.

**The film is not finished.** What exists is a rough cut on my machine: the voice of Addis AI, real pictures, a generated score, one shot with generated motion (the road) and a slow pan on the others. The words of the narration are my own since 26 Nov. Four things in the cut are the coding agent's choice and not yet confirmed by me: the English subtitles and which sentence goes on which picture, the score, the voice, and the pictures that were drawn on 26 Nov after a review of the cut (`DESIGN.md`). User test 1 has happened: three people heard the radio cut on 25 Nov, and what they wrote changed the lines of that cut (`DESIGN.md`). User test 2 has not happened. The rough cut is not committed: `.gitignore` keeps it out until the release, so that nothing unapproved is published by a push. It was committed once by mistake and taken out again (F08).

## Run it

You need Python 3.10 or newer and FFmpeg 4.4 or newer (with libx264 and libass) on your PATH. Built and tested offline on Linux with Python 3.13 and FFmpeg 6.1. On Ubuntu or Debian: `sudo apt install ffmpeg python3-venv make`.

```
make setup                    # build .venv and install requirements.txt into it
make doctor                   # check FFmpeg, its filters, the packages and the keys on this machine
cp .env.example .env          # then fill in the values
make validate                 # check storyboard.json
make smoke                    # call each provider once, log the latency
make plan                     # what the next run would build, and why. Calls no model
make radio                    # radio cut: narration + placeholder music on black
make film                     # everything
make review                   # one HTML page to look at and listen to every shot
make costs                    # measured latency and list price per stage, into COSTS.md
make site                     # the film's public page, built from this repository into site/
make desk                     # a local page for the author: confirm lines, pick pictures, choose the score
```

Every `make` target uses the Python in `.venv`. To type a `python -m pipeline ...` command yourself, run `source .venv/bin/activate` once in that terminal.

No keys yet? `make mock-film` runs the whole pipeline offline with stand-in providers, and `make test` runs the tests. On Windows without `make`, the top of the `Makefile` shows how to build the environment by hand, and each target shows its `python -m pipeline ...` command.

Keys go in `.env`, which is git-ignored. Nothing in this repository contains a secret.

| Variable | Where it comes from | Needed for |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio | the listening check and the light checks. Speech too, while `models.tts` names a Gemini model |
| `ADDIS_API_KEY` | addisassistant.com, after signing up | speech, while `models.tts` names an Addis AI model (`addis-voices-2`, as now), the listening check, while `models.listener` names one (`addis-scribe`, as now), and `python -m pipeline voices` |
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | Cloudflare dashboard, a token with Workers AI permission | pictures |
| `KAGGLE_API_TOKEN` | kaggle.com/settings/api, "Generate New Token" | running the GPU jobs from the command line. Optional: they can be run by hand |
| `ANTHROPIC_API_KEY` | platform.claude.com, a key with credit | the picture judge and the subtitle check, while `models.judge` names a Claude model. Optional: remove that line from the storyboard and both run on the free Gemini model |

## The stages

| # | Stage | Model | Where it runs | Reads | Writes |
|---|---|---|---|---|---|
| 1 | `script` | Gemini 3.5 Flash-Lite for a missing subtitle, Claude Opus 5.5 to check a written one | Gemini API, Claude API | `storyboard.json` | `outputs/script/` |
| 2 | `narration` | Addis Voices 2 (`addis-voices-2`) with the voice `am-nahom`. Gemini 3.8 Flash TTS is the other speech model the stage can call. Then a listening check by a model: `models.listener` when the storyboard names one, else `models.text` | Addis AI API, Gemini API | script | one WAV per narrated shot |
| 3 | `keyframes` | FLUX.2 klein 4B, then a border check and a judge (Claude Opus 5.5) | Cloudflare Workers AI, Claude API | storyboard | reference sheets, candidates, the pick |
| 4 | `shots` | Wan 2.2 TI2V-5B, or Ken Burns | Kaggle GPU, or FFmpeg here | keyframes, narration timing | one clip per shot |
| 5 | `music` | ACE-Step 1.5, or a placeholder drone | Kaggle GPU, or FFmpeg here | storyboard | score candidates |
| 6 | `assemble` | none (FFmpeg) | here | everything above | both films, subtitles |

The model ids are in `storyboard.json` under `models`, and they changed as the work went on. The checks started on Gemini 3.8 Flash and moved to Flash-Lite when it proved overloaded (F01 and E15). The picture judge then moved to Claude Opus 5.5, which is paid for, after it named faults the others had scored as perfect (E17). On 26 Nov the speech moved from Gemini 3.8 Flash TTS to a voice of Addis AI, a provider built for Ethiopian languages (F10 and E26). `python -m pipeline voices` lists its voices for the narration language.

The two GPU models do not run on my laptop. The pipeline writes a job folder, and `python -m pipeline kaggle run shots` uploads it to Kaggle, runs it on a free GPU, waits, downloads the result and puts the clips into the cache with the seconds the GPU measured. Until then every shot falls back to a pan and zoom over its keyframe, so a full film always assembles. The same job can be run by hand in a notebook. See `kaggle/README.md`.

## Changing one shot

Every unit of work (one narration line, one keyframe, one scene) is cached under a hash of its inputs. Change one thing and only what depends on it is rebuilt:

```
# edit one narration line of shot s04 in storyboard.json, then:
python -m pipeline plan     # shows what will be rebuilt and which input changed. Calls no model.
python -m pipeline film
```

```
[script]    s04_subtitle_check MISS (changed: text)
[narration] s04                MISS (changed: text)
[narration] s04_listen         MISS (changed: audio, text)
[assemble]  mix                MISS (changed: lines)
[assemble]  vertical_s04       MISS (changed: cues)
[assemble]  horizontal_s04     MISS (changed: cues)
[assemble]  film_vertical      MISS (changed: mix, scenes)
[assemble]  film_horizontal    MISS (changed: mix, scenes)
```

Everything else prints `HIT`. In the offline test this is asserted: one changed line makes exactly three model calls (check its subtitle, speak it, listen to it), and one changed keyframe prompt regenerates only that shot.

What is kept decides what a change costs. The model's own answers are stored untouched: every picture in `outputs/keyframes/original/`, every narration line as it was spoken in `outputs/narration/`. What the film uses is cut from those by FFmpeg. So a new crop or a shorter pause inside a line calls no model.

## What makes it more than the floor

- **A consent gate in code.** A shot that shows a real person is not generated until that person's consent is a dated row in `ETHICS.md` and marked in the storyboard. `make release` also refuses drafts and unconfirmed lines.
- **Quality gates that measure.** Every keyframe candidate is measured for a paper border and scored by a vision model that is asked what is wrong with it, and the best full-frame one is kept, with a human override. Each written subtitle is checked against its Amharic line by a model that translates the line literally. Each narration line is transcribed back and compared with the script. The finished films are measured: length, both ratios, loudness, true peak, subtitle line length, the AI end card. A gate that cannot reach its model never stops a run: the picture is still made, and the next run asks again.
- **A guard for the free tiers.** The limits that apply to this project are in `pricing.json`, and the run log is the counter. A request that would go over a free daily limit is not sent, and for a speech model with a daily limit `make plan` says how many requests are left today. The first narration was built around such a limit, ten speech requests a day on the Gemini free tier: the lines were spoken in one request and cut apart here, and a line was kept from that take only where two ways of cutting agreed (E20). That way is still in the code for the Gemini speech model, and it is switched off: each line is now spoken in a request of its own (F10). For the pictures the account now pays for what goes over the free daily allowance, and the run says when that starts.
- **Two speech providers.** `models.tts` names the speech model. An id that starts with `addis-` goes to Addis AI, any other to the Gemini API. `python -m pipeline voices` lists the Addis AI voices for the narration language.
- **The cost of every call.** Each line of `runs.jsonl` carries `cost_usd`, the list price of that call, from prices copied off the providers' pages with the date. For a free tier or a credit it says what the same work costs without it. For Claude it is what was paid. `COSTS.md` says what is paid in all.
- **GPU jobs from the command line.** `python -m pipeline kaggle run music` uploads the job, runs it on Kaggle, and brings the result back with the seconds and the peak memory the GPU measured.
- **A review sheet.** `make review` writes `outputs/review.html`: each shot's reason, words, audio, candidates with their scores, and clip, side by side.
- **A language test.** `python -m pipeline langtest` speaks the film's first lines in Amharic, Tigrinya, Somali and Afaan Oromo and scores each by listening back, with a rating sheet for a native speaker.
- **A blind A/B tool.** `python -m pipeline blindtest` packs pairs under neutral names and scores the votes with a sign test.
- **A tool for others.** `python -m pipeline init my-film` starts a new film with a blank storyboard, and `python -m pipeline.mcp_server` exposes the pipeline to a coding agent over MCP.
- **A desk for the author.** `make desk` opens a local page at http://127.0.0.1:8765 where the author does his part by clicking: confirm each line, edit the narration, subtitles, audience and intent, pick a keyframe candidate, choose the score. Each change is checked like any storyboard and written into `storyboard.json` without reformatting it, and the page shows what the next run would rebuild. It runs no stage, calls no model and cannot change consent.
- **A page for the film.** `make site` builds one static page from the storyboard, the kept model outputs, the run log and the two journals: the film, every shot with its picture, line and reason, what it took, what broke. A workflow publishes it with GitHub Pages on every push. Before the film exists the page says so.
- **Tests on every push.** A second workflow builds the environment from a clean clone and runs the whole suite, which includes the full pipeline with mock providers: the one command, proven on a machine that has never seen the project.

## Files

```
storyboard.json      the contract: shots, reasons, prompts, seeds, narration, music cues
schema/              JSON Schema for the storyboard, validated before every run
pipeline/            one module per stage, plus core (cache, run log, retries) and providers
kaggle/              the two GPU job scripts and how to run them
tests/               offline tests, including a full mock film
experiments/         scripts for the experiments that are not a plain pipeline run
.github/workflows/   the tests and the public page, run by GitHub on every push
runs.jsonl           one line per real model call (created by the first one)
outputs/             generated images, audio and video, kept for inspection
pricing.json         list prices and free-tier limits per model, each with its source and the date it was read
DESIGN.md            audience, intent, a reason for every shot, the two user tests
ARCHITECTURE.md      stages, contracts, caching, failure handling, one hard decision
EXPERIMENTS.md       hypothesis, change, result
FAILURES.md          what broke, what was tried, what fixed it
COSTS.md             measured latency and GPU minutes per stage, list-price equivalent
ETHICS.md            consent records, licences, labelling plan
```

## What is committed

Model outputs are kept in `outputs/`, because they cost quota or GPU time and are the evidence: the original pictures, the narration lines, ingested Wan clips, score candidates, and the `manifest.json` and index files of the five stages that call a model or a GPU. Files that FFmpeg rebuilds from those without calling a model (keyframes cut from their originals, scene files, the mix, Ken Burns clips, the placeholder drone) are git-ignored.

The two films are not committed yet. They will be committed with the release, when the lines are confirmed and the cut is final, and not before. Until then `.gitignore` keeps `outputs/film_*.mp4`, `outputs/radio_cut.mp4`, `outputs/qc_report.json` and `outputs/assemble/` out of the repository, because a push publishes them on the public page. A rough cut was committed once by mistake and taken out again. That commit stays in the history (F08 in `FAILURES.md`).

To check this yourself: clone the repository into an empty folder, add no key, run `make setup` and then `python -m pipeline film`. Nothing may be added to `runs.jsonl`. On 25 November this rebuilt the cut of that evening in 1 minute 49 seconds: 42 cache hits on model outputs, 53 units rebuilt by FFmpeg, no call to any model (E23 in `EXPERIMENTS.md`). No later run of this check is recorded: it has to be repeated on the release commit. What is reproduced is the cut from the kept answers of the models. Asking the models again gives other pictures and another voice.

## What it costs

Money, by the run log as it stood on 26 November at 02:33:

- The picture judge and the subtitle check run on Claude Opus 5.5, which is paid for every call: 4.17 USD so far.
- The pictures run on Cloudflare Workers AI. Since the night of 25 Nov the account is on the Workers Paid plan: 5 USD a month, plus what goes over the free daily allowance, 0.06 USD so far.
- The narration voice and the listening check of Addis AI run on a sign-up credit of 3.17 USD (500 ETB). Nothing is paid, and 0.17 USD of the credit is used at list price.
- The light checks (Gemini) and the GPU (Kaggle) run on free tiers.

The limits that shape the work are quota and GPU time: ten speech requests a day on the Gemini free tier, about 96 free pictures a day, 30 GPU hours a week. `make costs` reads `runs.jsonl` and writes the measured table into `COSTS.md`, with the list price of every call. `COSTS.md` also says what was really paid, and that a second free Gemini key was put in during the night of 25 to 26 Nov (F09).

## How this was built

The stage scripts and the first storyboard were drafted by an AI coding agent (Claude) from my story and the challenge brief, in an offline sandbox against mock providers. The Status table says which parts have since run against real models. The story is mine. After user test 1 I gave the listeners' comments to the coding agent and told it to decide the changes itself: the rewritten lines, the choice of score and the choice of voice are its work, and I have not confirmed them yet (`DESIGN.md`, and E22 and E26 in `EXPERIMENTS.md`). Lines in the storyboard marked `"confirmed": false` are still drafts. The film ends with a card that says it was made with AI.