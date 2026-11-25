# One Bag: a heritage short, made by a pipeline

A 60 to 90 second film about the night I first arrived in Addis Ababa from Ankober in 2019, narrated in Amharic with English subtitles and an original score. I did not edit it by hand. This repository is the small studio that makes it: one file, `storyboard.json`, is the contract, and six stages turn it into two finished films.

```
make film        # or: python -m pipeline film
```

That one command validates the storyboard, runs every stage, regenerates only what changed, writes `outputs/film_vertical.mp4` (9:16) and `outputs/film_horizontal.mp4` (16:9), and then measures the result against the brief.

## Status

Be clear about what is proven and what is not. Last updated 25 November 2026, 20:40 East Africa Time.

| Part | Tested offline with mock providers | Run against the real model |
|---|---|---|
| Storyboard schema and checks | yes | not applicable |
| Cache, run log, retries, free-tier guard | yes | yes: the retries and the guard both met a real quota (F01) |
| Script (subtitle translation) | yes | not yet: every line has a written subtitle |
| Narration (Gemini TTS) | yes | yes: eight lines. One request for all of them gave four clean lines, the other four were spoken alone (F04, E20) |
| Narration listening check | yes | yes: all eight lines at or above the floor, once the question named the language (E21) |
| Keyframes (FLUX.2 klein on Workers AI) | yes | yes: all nine shots, after a reference sheet that copied itself into the scenes (E19) and two shots that had to be redesigned (F05) |
| Keyframe judge | yes | yes, on three models (E15, E17) |
| Subtitle check | yes | yes: it found two mismatches in the first draft (E18). The eight current subtitles pass |
| Keyframe border check | yes | yes: it caught the white border on the first pictures (E16) |
| Shots: Ken Burns (FFmpeg) | yes, real FFmpeg | not applicable |
| Shots: Wan 2.2 on Kaggle | export, upload and ingest | sent for two shots, no clip back yet |
| Music: ACE-Step on Kaggle | export, upload and ingest | yes: three candidates on the third run (F02), each described by a listening model. None is chosen yet |
| Assembly, ducking, loudness, both ratios | yes, real FFmpeg | yes: a first rough cut of 80 s in both ratios, from the real narration and pictures |
| Final-cut check | yes | yes, on that rough cut: every measured check passes, with two notes (placeholder score, no generated motion yet) |

`runs.jsonl` holds one line per attempt of a real model call, 351 so far. Mock runs write to `outputs_mock/`, which is git-ignored and is never evidence.

**The film is not finished.** What exists is a rough cut on the author's machine: real voice, real pictures, a placeholder score, a slow pan on every shot. The narration lines are not confirmed by the author yet, no score is chosen, and neither of the two user tests has happened. The rough cut is not in the repository, so that nothing unapproved is published by a push.

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
| `GEMINI_API_KEY` | Google AI Studio | speech, and the checks |
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | Cloudflare dashboard, a token with Workers AI permission | pictures |
| `KAGGLE_API_TOKEN` | kaggle.com/settings/api, "Generate New Token" | running the GPU jobs from the command line. Optional: they can be run by hand |
| `ANTHROPIC_API_KEY` | platform.claude.com, a key with credit | the picture judge and the subtitle check, while `models.judge` names a Claude model. Optional: remove that line from the storyboard and both run on the free Gemini model |

## The stages

| # | Stage | Model | Where it runs | Reads | Writes |
|---|---|---|---|---|---|
| 1 | `script` | Gemini 3.5 Flash-Lite for a missing subtitle, Claude Opus 5.5 to check a written one | Gemini API, Claude API | `storyboard.json` | `outputs/script/` |
| 2 | `narration` | Gemini 3.8 Flash TTS, then a listening check by Gemini 3.5 Flash-Lite | Gemini API | script | one WAV per shot |
| 3 | `keyframes` | FLUX.2 klein 4B, then a border check and a judge (Claude Opus 5.5) | Cloudflare Workers AI, Claude API | storyboard | reference sheets, candidates, the pick |
| 4 | `shots` | Wan 2.2 TI2V-5B, or Ken Burns | Kaggle GPU, or FFmpeg here | keyframes, narration timing | one clip per shot |
| 5 | `music` | ACE-Step 1.5, or a placeholder drone | Kaggle GPU, or FFmpeg here | storyboard | score candidates |
| 6 | `assemble` | none (FFmpeg) | here | everything above | both films, subtitles |

The model ids are in `storyboard.json` under `models`. They changed twice on the first day. The checks started on Gemini 3.8 Flash and moved to Flash-Lite when it proved overloaded (F01 and E15). The picture judge then moved to Claude Opus 5.5, the one model here that is paid for, after it named faults the others had scored as perfect (E17).

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

What is kept decides what a change costs. The model's own answers are stored untouched: every picture in `outputs/keyframes/original/`, every narration take in `outputs/narration/takes/`. What the film uses is cut from those by FFmpeg. So a new crop or a new way of cutting a take calls no model.

## What makes it more than the floor

- **A consent gate in code.** A shot that shows a real person is not generated until that person's consent is a dated row in `ETHICS.md` and marked in the storyboard. `make release` also refuses drafts and unconfirmed lines.
- **Quality gates that measure.** Every keyframe candidate is measured for a paper border and scored by a vision model that is asked what is wrong with it, and the best full-frame one is kept, with a human override. Each written subtitle is checked against its Amharic line by a model that translates the line literally. Each narration line is transcribed back and compared with the script. The finished films are measured: length, both ratios, loudness, true peak, subtitle line length, the AI end card. A gate that cannot reach its model never stops a run: the picture is still made, and the next run asks again.
- **A guard for the free tiers.** The limits that apply to this project are in `pricing.json`, and the run log is the counter. A request that would go over a daily limit is not sent, and `make plan` says how many speech requests are left today. The speech tier allows ten requests a day, so the narration is spoken in one request and cut into lines here.
- **The cost of every call.** Each line of `runs.jsonl` carries `cost_usd`, the list price of that call, from prices copied off the providers' pages with the date. For the free tiers it says what the same work costs without them. For Claude, the one paid model, it is what was paid.
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

Model outputs are kept in `outputs/`, because they cost quota or GPU time and are the evidence: the original pictures, narration, ingested Wan clips, score candidates, the two finished films, and every `manifest.json` and `index.json`. Files that FFmpeg rebuilds from those without calling a model (keyframes cut from their originals, scene files, the mix, Ken Burns clips, the placeholder drone) are git-ignored.

## What it costs

Money: speech, pictures, the light checks and the GPU run on free tiers. The picture judge and the subtitle check run on Claude Opus 5.5, which is paid for: 1.88 USD on the first day. The limits that shape the work are quota and GPU time: ten speech requests a day, about 96 pictures a day, 30 GPU hours a week. `make costs` reads `runs.jsonl` and writes the measured table into `COSTS.md`, with the list price of every call and what was really paid.

## How this was built

The stage scripts and the first storyboard were drafted by an AI coding agent (Claude) from my story and the challenge brief, in an offline sandbox against mock providers. The Status table says which parts have since run against real models. The story is mine, and so are the decisions that follow from the user tests. Lines in the storyboard marked `"confirmed": false` are still drafts. The film ends with a card that says it was made with AI.