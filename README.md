# One Bag: a heritage short, made by a pipeline

A 60 to 90 second film about the night I first arrived in Addis Ababa from Ankober in 2019, narrated in Amharic with English subtitles and an original score. I did not edit it by hand. This repository is the small studio that makes it: one file, `storyboard.json`, is the contract, and six stages turn it into two finished films.

```
make film        # or: python -m pipeline film
```

That one command validates the storyboard, runs every stage, regenerates only what changed, writes `outputs/film_vertical.mp4` (9:16) and `outputs/film_horizontal.mp4` (16:9), and then measures the result against the brief.

## Status

Be clear about what is proven and what is not. Update this table as real runs happen.

| Part | Code written | Tested offline with mock providers | Run against the real model |
|---|---|---|---|
| Storyboard schema and checks | yes | yes | not applicable |
| Cache, run log, retries | yes | yes | not applicable |
| Script (subtitle translation) | yes | yes | not yet |
| Narration (Gemini TTS) | yes | yes | not yet |
| Narration listening check | yes | yes | not yet |
| Keyframes (FLUX on Workers AI) | yes | yes | not yet |
| Keyframe judge | yes | yes | not yet |
| Shots: Ken Burns (FFmpeg) | yes | yes, real FFmpeg | not applicable |
| Shots: Wan 2.2 on Kaggle | yes | export and ingest only | not yet |
| Music: ACE-Step on Kaggle | yes | export and ingest only | not yet |
| Assembly, ducking, loudness, both ratios | yes | yes, real FFmpeg | not applicable |
| Final-cut check | yes | yes | not applicable |

`runs.jsonl` holds one line per real model call. It does not exist until the first real call. Mock runs write to `outputs_mock/`, which is git-ignored and is never evidence.

## Run it

You need Python 3.10 or newer and FFmpeg 4.4 or newer (with libx264 and libass) on your PATH. Built and tested offline on Linux with Python 3.13 and FFmpeg 6.1. On Ubuntu or Debian: `sudo apt install ffmpeg python3-venv make`.

```
make setup                    # build .venv and install requirements.txt into it
make doctor                   # check FFmpeg, its filters, the packages and the keys on this machine
cp .env.example .env          # then fill in the three values
make validate                 # check storyboard.json
make smoke                    # call each provider once, log the latency
make radio                    # radio cut: narration + placeholder music on black
make film                     # everything
make review                   # one HTML page to look at and listen to every shot
```

Every `make` target uses the Python in `.venv`. To type a `python -m pipeline ...` command yourself, run `source .venv/bin/activate` once in that terminal.

No keys yet? `make mock-film` runs the whole pipeline offline with stand-in providers, and `make test` runs the tests. On Windows without `make`, the top of the `Makefile` shows how to build the environment by hand, and each target shows its `python -m pipeline ...` command.

Keys go in `.env`, which is git-ignored. Nothing in this repository contains a secret.

| Variable | Where it comes from |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio |
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | Cloudflare dashboard, a token with Workers AI permission |

## The stages

| # | Stage | Model | Where it runs | Reads | Writes |
|---|---|---|---|---|---|
| 1 | `script` | Gemini 3.8 Flash, only for a missing subtitle | Gemini API | `storyboard.json` | `outputs/script/` |
| 2 | `narration` | Gemini 3.8 Flash TTS, then a listening check | Gemini API | script | one WAV per shot |
| 3 | `keyframes` | FLUX.2 klein 4B, judged by Gemini 3.8 Flash | Cloudflare Workers AI | storyboard | reference sheets, candidates, the pick |
| 4 | `shots` | Wan 2.2 TI2V-5B, or Ken Burns | Kaggle GPU, or FFmpeg here | keyframes, narration timing | one clip per shot |
| 5 | `music` | ACE-Step 1.5, or a placeholder drone | Kaggle GPU, or FFmpeg here | storyboard | score candidates |
| 6 | `assemble` | none (FFmpeg) | here | everything above | both films, subtitles |

The two GPU models do not run on my laptop. The pipeline writes a job bundle (`outputs/shots/kaggle_job.zip`), a Kaggle notebook runs it, and `python -m pipeline ingest shots results.zip` brings the clips back into the cache with the latency the GPU measured. Until then every shot falls back to a pan and zoom over its keyframe, so a full film always assembles. See `kaggle/README.md`.

## Changing one shot

Every unit of work (one narration line, one keyframe, one scene) is cached under a hash of its inputs. Change one thing and only what depends on it is rebuilt:

```
# edit one narration line of shot s04 in storyboard.json, then:
python -m pipeline plan     # shows what will be rebuilt and which input changed. Calls no model.
python -m pipeline film
```

```
[narration] s04            MISS (changed: text)
[narration] s04_listen     MISS (changed: audio, text)
[assemble]  mix            MISS (changed: lines)
[assemble]  vertical_s04   MISS (changed: cues)
[assemble]  horizontal_s04 MISS (changed: cues)
[assemble]  film_vertical  MISS (changed: mix, scenes)
```

Everything else prints `HIT`. In the offline test this is asserted: one changed line makes exactly two model calls (speak it, listen to it), and one changed keyframe prompt regenerates only that shot.

## What makes it more than the floor

- **A consent gate in code.** A shot that shows a real person is not generated until that person's consent is a dated row in `ETHICS.md` and marked in the storyboard. `make release` also refuses drafts and unconfirmed lines.
- **Quality gates that measure.** Keyframe candidates are scored by a vision model and the best is kept, with a human override. Each narration line is transcribed back and compared with the script. The finished films are measured: length, both ratios, loudness, true peak, subtitle line length, the AI end card.
- **A review sheet.** `make review` writes `outputs/review.html`: each shot's reason, words, audio, candidates with their scores, and clip, side by side.
- **A language test.** `python -m pipeline langtest` speaks the film's first lines in Amharic, Tigrinya, Somali and Afaan Oromo and scores each by listening back, with a rating sheet for a native speaker.
- **A blind A/B tool.** `python -m pipeline blindtest` packs pairs under neutral names and scores the votes with a sign test.
- **A tool for others.** `python -m pipeline init my-film` starts a new film with a blank storyboard, and `python -m pipeline.mcp_server` exposes the pipeline to a coding agent over MCP.

## Files

```
storyboard.json      the contract: shots, reasons, prompts, seeds, narration, music cues
schema/              JSON Schema for the storyboard, validated before every run
pipeline/            one module per stage, plus core (cache, run log, retries) and providers
kaggle/              the two GPU job scripts and how to run them
tests/               offline tests, including a full mock film
runs.jsonl           one line per real model call (created by the first one)
outputs/             generated images, audio and video, kept for inspection
pricing.json         list prices for COSTS.md, to be filled from the providers' pages
DESIGN.md            audience, intent, a reason for every shot, the two user tests
ARCHITECTURE.md      stages, contracts, caching, failure handling, one hard decision
EXPERIMENTS.md       hypothesis, change, result
FAILURES.md          what broke, what was tried, what fixed it
COSTS.md             measured latency and GPU minutes per stage, list-price equivalent
ETHICS.md            consent records, licences, labelling plan
RUNBOOK.md           the order of work from first key to public post
```

## What is committed

Model outputs are kept in `outputs/`, because they cost quota or GPU time and are the evidence: keyframes, narration, ingested Wan clips, score candidates, the two finished films, and every `manifest.json` and `index.json`. Files that FFmpeg rebuilds from those without calling a model (scene files, the mix, Ken Burns clips) are git-ignored.

## What it costs

Money: nothing, on the free tiers. The limits are quota and GPU time. `make costs` reads `runs.jsonl` and writes the measured table into `COSTS.md`.

## How this was built

The stage scripts and the first storyboard were drafted by an AI coding agent (Claude) from my story and the challenge brief, in an offline sandbox against mock providers. The Status table says which parts have since run against real models. The story is mine, and so are the decisions that follow from the user tests. Lines in the storyboard marked `"confirmed": false` are still drafts. The film ends with a card that says it was made with AI.