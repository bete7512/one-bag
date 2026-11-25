# Plan: from first real call to submission

This is the hand-over plan for the film "One Bag". Bete and Claude Code work through it together.

**How to use it.** Bete starts a Claude Code session with: `Read PLAN.md, follow its rules, and continue from the first unchecked step.` Claude Code does one step, ticks its boxes, reports, and stops. `RUNBOOK.md` has the same order with more detail. Where they differ, this file wins.

**Deadline:** Thursday 26 November 2026, 23:59 East Africa Time. Wednesday: steps 1 to 7. Thursday: steps 8 to 10.

## Where things stand (25 November)

- The pipeline is built and passes its tests offline, with stand-in providers only.
- No real model has been called. The code for real calls was written from the provider docs, so expect the first calls to fail in small ways.
- The two Kaggle scripts have never run on a GPU.
- The storyboard is a draft: the Amharic lines, `audience` and `intent` are not Bete's words yet, and no consent is recorded.

## Rules for any AI agent working here

1. **Never invent evidence.** `runs.jsonl`, `EXPERIMENTS.md`, `FAILURES.md`, `COSTS.md` and the user-test tables in `DESIGN.md` hold only what really happened. No estimates, no example rows. An empty cell is correct until there is a real result.
2. **Mock is never evidence.** `--mock` and `outputs_mock/` test the plumbing. Never copy mock output into `outputs/` or present a mock run as real.
3. **Consent belongs to Bete.** Never set a `consent.status` to `"recorded"`, never write a date in the consent table of `ETHICS.md`, never set `real_person` to false, never work around the consent gate. A real person shown without a consent record scores the film zero.
4. **The words belong to Bete.** Do not write the Amharic narration, `audience`, `intent`, the report's conclusions or the public post. Point out problems and offer options when asked. Never set `"confirmed": true`: that is his sign-off.
5. **Keys stay in `.env`.** Never print, log, echo or commit a key or token. Before any commit, check `git status`: no `.env`, no `outputs_mock/`. Commit and push only when Bete asks.
6. **Never weaken a check to get a green run:** the consent gate, strict mode, the final-cut check, the cache tests. One exception: the request-shape tests pin what the provider docs said. When the real API differs, change the code and that test together and log it.
7. **Log a failure when it happens.** Stop, show Bete the exact error, and add an entry to `FAILURES.md` (the template is in that file).
8. **One change at a time.** Before a run that calls a model, run `make plan` and say what will be rebuilt. Ask first when a change rebuilds many shots (the style, a character, the image model).
9. **Three attempts per shot or per job,** then move on and write down why.
10. **Answer Bete in short, plain sentences.**

## How the pipeline works, in short

- `storyboard.json` is the contract: every shot, its reason, prompts, seeds, narration and the model ids. The schema in `schema/` checks it before every run.
- Six stages in `pipeline/`: `script`, `narration`, `keyframes`, `shots`, `music`, `assemble`. `core.py` holds the cache, the run log and the retries. `providers.py` holds every real API call.
- Each unit of work is cached under a hash of its inputs. Change one thing and only what depends on it is rebuilt.
- Every real call attempt adds one line to `runs.jsonl`.
- Speech, text and the picture judge run on the Gemini API. Pictures run on Cloudflare Workers AI. Video (Wan 2.2) and music (ACE-Step) run on Kaggle, by hand in the browser.
- Until a Wan clip comes back, a shot uses a pan and zoom over its picture, so a full film always assembles.

| Command | What it does |
|---|---|
| `make doctor` | checks the machine and which keys are set |
| `make test` | all offline tests |
| `make smoke` | one tiny real call per provider |
| `make validate` | checks the storyboard and lists what is still a draft |
| `make plan` | what would be rebuilt and why, no model call |
| `make radio` | narration over placeholder music: `outputs/radio_cut.mp4` |
| `make film` | everything: `outputs/film_vertical.mp4`, `outputs/film_horizontal.mp4` |
| `make review` | `outputs/review.html`: every shot, line, candidate and clip on one page |
| `make release` | like `film`, but refuses drafts, pending consent and a failed final-cut check |
| `make costs` | the measured table from `runs.jsonl` into `COSTS.md` |

To type a `python -m pipeline ...` command, first run `source .venv/bin/activate`.

## When a real call fails

1. Read the last lines of `runs.jsonl`: `status`, `http_status`, `error`.
2. Repeat only that call with `make smoke`.
3. Compare the request built in `pipeline/providers.py` with the provider's current API page. Likely causes: a model id that does not exist (404), a wrong field in the request (400), a key or permission problem (401, 403), a rate limit (429: set `HERITAGE_PAUSE_S=5` in `.env`).
4. Fix `providers.py`, or the model id under `models` in the storyboard. Run `make test-fast`. Try again.
5. Write the `FAILURES.md` entry. Entry B2 in that file explains why the speech call looks the way it does.

## The steps

### Step 1. Check the machine
- [ ] **Agent:** `make setup` if `.venv` is missing, then `make doctor` and `make test`.
- Done when: doctor says `ready` and every test passes.

### Step 2. First real calls
- [ ] **Bete:** the Gemini key and the two Cloudflare values are in `.env`.
- [ ] **Agent:** `make smoke`. If a call fails, follow "When a real call fails".
- [ ] **Agent:** write the limits and latencies you saw into `COSTS.md`.
- Done when: `text`, `speech` and `image` all print `ok`.

### Step 3. The words and the consent
This step is Bete's. The agent only checks.
- [ ] **Bete:** rewrite every Amharic line in `storyboard.json` in his own words.
- [ ] **Bete:** the year in shot s01. In Amharic, "2019" is heard as the Ethiopian year, which is this year. Say the Ethiopian year in words: 2011 if he travelled before 12 September 2019, 2012 if after. The English subtitle keeps 2019.
- [ ] **Bete:** keep or change three guesses: "in the morning" (s07, s09), "to the university" (s07), "I could not sleep" (s08). Describe the real road out of Ankober for s02.
- [ ] **Bete:** write `audience` and `intent` in the storyboard and in `DESIGN.md`, and remove the word DRAFT. One suggestion from planning, his to take or leave: young people about to leave a small town for university or work in a big city.
- [ ] **Bete:** consent. Fill the two rows in `ETHICS.md` (how it was given, the date), then set those people's `consent.status` to `"recorded"`. His friend's reply stays private, outside the repository. Only shot s06 waits for the friend.
- [ ] **Bete:** set `"confirmed": true` on each shot he has checked.
- [ ] **Agent:** after his edits, `make validate` and list the warnings that are left. If a line changed, offer an English subtitle for it and let him approve it.
- Done when: `make validate` shows no warning that Bete did not choose to leave.

### Step 4. Radio cut and user test 1
- [ ] **Agent:** `make radio`. Report each line's listening score, and what the model heard for any line under `qa.roundtrip_min`.
- [ ] **Bete:** listen on a phone speaker. Fix what sounds wrong (see "What can be iterated").
- [ ] **Bete:** send `outputs/radio_cut.mp4` to at least three people from the audience, ask the four questions in `DESIGN.md`, and write their answers there in their words.
- [ ] **Bete:** change the storyboard because of what they said, and log the change in `DESIGN.md`.
- Done when: user test 1 is written down.

### Step 5. Pictures
- [ ] **Agent:** `python -m pipeline stage keyframes`, then `make review`.
- [ ] **Bete:** open `outputs/review.html` and look at every candidate: hands, faces, any writing in the picture, and whether the young man is the same person in every shot.
- [ ] **Agent:** change what he names, one shot at a time. Log each try that teaches something in `EXPERIMENTS.md`.
- Done when: every shot has a picture he accepts, or a note saying why not.

### Step 6. Rough cut
- [ ] **Agent:** `make film`. Report the final-cut check.
- [ ] **Bete:** watch both films on a phone.

### Step 7. GPU jobs on Kaggle
Start early: they run in the background. The steps on Kaggle are in `kaggle/README.md`.
- [ ] **Bete:** Kaggle account verified by phone.
- [ ] **Bete:** music first. Upload `outputs/music/kaggle_job.zip`, run it, download `results.zip`.
- [ ] **Agent:** `python -m pipeline ingest music results.zip`. If the job failed, read the notebook log Bete pastes, fix `kaggle/acestep_music.py`, log it.
- [ ] **Bete:** listen to the candidates under the voice. Set `music.chosen` and `music.chosen_reason`.
- [ ] **Both:** the same for video, with `outputs/shots/kaggle_job.zip` and `kaggle/wan22_i2v.py`. Out of memory: lower `video.num_frames` first, then `video.max_area`. After three attempts the shot keeps its pan and zoom.
- If the music job cannot be made to run, stop and tell Bete: the placeholder is not a score, and `make release` will refuse.

### Step 8. Final cut and user test 2
- [ ] **Agent:** `make film`.
- [ ] **Bete:** show it to at least three people, ask the questions in `DESIGN.md`, write down what they say and what he changes.
- [ ] **Agent:** `make release`. Fix what it names, never by weakening the check. Then `make costs`.
- Done when: `make release` passes.

### Step 9. One thing beyond the brief (optional, about an hour)
- [ ] `python -m pipeline langtest`: the same lines in Amharic, Tigrinya, Somali and Afaan Oromo (experiment E14), or
- [ ] `python -m pipeline blindtest pack motion --labels kenburns,wan --a <still clip> --b <wan clip>`: pan and zoom against a Wan clip with five people (E10).

### Step 10. Documents, walkthrough, post
- [ ] **Agent:** from `runs.jsonl` and Bete's notes only: the README status table, `EXPERIMENTS.md`, `FAILURES.md`, `COSTS.md`. Prices in `pricing.json` come only from the providers' pricing pages, with the date they were read.
- [ ] **Bete:** the report, from `REPORT_OUTLINE.md`, in his words.
- [ ] **Bete:** the walkthrough video, from `WALKTHROUGH.md`: five minutes at most, one shot regenerated live.
- [ ] **Bete:** the public post with the platform's AI label on, written by him.
- [ ] **Bete:** check that every link opens without a login, then submit both assignments.

## What can be iterated

Each one is a field in `storyboard.json`. Change one field, run `make plan`, then `make film`.

| To change | Field | What is rebuilt | Judge it by | Experiment |
|---|---|---|---|---|
| How a line sounds | `shots[].narration.am` | that line: 2 Gemini calls | Bete's ear, the listening score | E03 |
| The voice | `voice.name`, `voice.style` | every line | three listeners | E01, E02 |
| One picture | `keyframe.prompt`, `keyframe.seed` | that shot's candidates and judge calls | `outputs/review.html` | |
| Which candidate is used | `keyframe.pick` (1 or 2) | no model call | his eye | |
| More candidates per shot | `qa.keyframe_candidates` | one more picture and judge call per shot | how often the extra one wins | E07 |
| The young man changes between shots | `characters[].description`, `reference_prompt` | his reference sheet and every shot with him: ask first | viewers asked "same person?" | E05 |
| The whole look | `style.block` | every picture: ask first | his eye | |
| The image model | `models.image` | every picture: ask first | judge scores, side by side | E06 |
| Camera move over a still | `motion.camera` | that shot's clip, no model call | his eye | |
| Real motion | `motion.backend`, `motion.prompt` | a Kaggle job for that shot | blind A/B | E09, E10 |
| The score | `music.caption`, `music.seeds`, `music.chosen` | a Kaggle job | listening under the voice | E11 |
| Music too loud or too quiet | `music.gain_db` | the mix only | phone speaker and headphones | E12 |
| A shot too short or too long | `shots[].min_duration_s` | that scene only | watching | |
| Subtitle text or position | `shots[].narration.en`, `exports[].subtitle_margin_v` | the scenes only | reading on a phone | |

About ten real entries are expected in `EXPERIMENTS.md`. Its plan lists E01 to E14, with the hypothesis written before the run.

## Instructions that work, and ones to refuse

These work, because each names one thing and a way to check it:

- "Step 2."
- "Shot s04: the station looks empty. Change only the keyframe prompt so the crowd is denser. Show me the diff and the plan before you run it."
- "Line s05 scored low. Show me what the model heard next to what I wrote."
- "Run experiment E02 on line s03 with three voices from the provider's list. Put the files where I can listen and write the entry without a result."
- "The image call returned 400. Find the cause, fix it, log it."

Refuse these, or ask back:

- "Fill in the experiments." Only from real runs.
- "Mark consent as recorded." Only Bete edits that.
- "Write my Amharic lines" or "write my post." His words.
- "Make the film better." Ask which shot, and what is wrong with it.

## If time is short

Cut in this order: the frontier comparison, Wan clips, a second ceiling experiment. Never cut: consent, the two user tests, the end card, the run log.