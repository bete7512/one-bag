# Runbook: from first key to public post

The order matters more than the speed. Each step ends with something you can play or read. Deadline: Thursday 26 November, 23:59 East Africa Time.

## 0. Before any key (30 minutes)

- [ ] On Ubuntu or Debian: `sudo apt install ffmpeg python3-venv make`. Another Linux: install the same three things with its package manager.
- [ ] `make setup`, then `make doctor`. Setup builds a private Python environment in `.venv`. Doctor checks FFmpeg, the filters it needs, the Python packages and the keys.
- [ ] In every new terminal, run `source .venv/bin/activate` before you type a `python -m pipeline ...` command. The `make` commands do not need it.
- [ ] `make test`. Everything should pass offline.
- [ ] `make mock-film` and open `outputs_mock/film_vertical.mp4`. Colour cards and beeps: this is only to see the machine work.
- [ ] Read `storyboard.json` top to bottom. It is the film. Then `pipeline/core.py` (the cache and the run log) and one stage, for example `pipeline/narration.py`. The interview will ask why it is shaped this way.

## 1. Make the words yours (30 minutes)

- [ ] Rewrite `audience` and `intent` in the storyboard and in `DESIGN.md`, and remove the word DRAFT.
- [ ] Rewrite every Amharic line in your own words.
- [ ] The year: a listener hears "2019" in Amharic as the Ethiopian year, which is this year. Say the Ethiopian year in words (2011 before 12 September 2019, 2012 after) and keep 2019 in the English subtitle.
- [ ] Fix or remove the guesses that are left: "in the morning" (shots s07 and s09), "to the university", "I could not sleep", and the landscape on the road out of Ankober (s02). The bus, the early evening and the near dark at Autobus Tera are confirmed.
- [ ] For each shot you have checked, set `"review": {"confirmed": true}`.
- [ ] Message your friend. When he answers, fill the `consent-friend` row in `ETHICS.md` with the date and set his `consent.status` to `"recorded"`. Do the same for `consent-author`.
- [ ] `make validate`

## 2. Keys and a smoke test (30 minutes)

- [ ] Gemini API key from Google AI Studio. Cloudflare account, a Workers AI token, the account id. Put all three in `.env`.
- [ ] `make smoke`. Three calls, three lines in `runs.jsonl`. If one fails, the error says why: write it in `FAILURES.md` before fixing it.
- [ ] Note the limits you see in `COSTS.md`. If a provider answers HTTP 429 often, set `HERITAGE_PAUSE_S=5` in `.env`: the pipeline then waits five seconds after every call.

## 3. Radio cut and user test 1 (1 to 2 hours, mostly waiting for people)

- [ ] `make radio` and listen to `outputs/radio_cut.mp4` yourself, on a phone speaker.
- [ ] Check the listening scores it printed. A low score is a line to listen to twice.
- [ ] Send it to at least three people from your audience. Ask the four questions in `DESIGN.md`. Write down what they say in their words.
- [ ] Change the storyboard because of it, and log the change in `DESIGN.md`. Commit.

Checkpoint 1: the radio cut plays, and `DESIGN.md` has the first test.

## 4. Pictures (1 to 2 hours)

- [ ] `python -m pipeline stage keyframes`, then `make review` and open `outputs/review.html`. Look at every candidate and its judge score. Check hands and faces.
- [ ] Is the young man the same person across shots? If not: improve his `description`, try `keyframe.pick`, or change a seed. Log each try in `EXPERIMENTS.md` (E05, E06, E07).
- [ ] Limit: three attempts per shot, then move on.
- [ ] `make film`. You now have a rough cut with Ken Burns motion and the placeholder score.

## 5. GPU work on Kaggle (start early: it runs while you do other things)

- [ ] Verify your Kaggle account by phone. Follow `kaggle/README.md`.
- [ ] Music first: it is quick. Upload `outputs/music/kaggle_job.zip`, run `acestep_music.py`, download `results.zip`, then `python -m pipeline ingest music results.zip`.
- [ ] Listen to the three candidates under the narration at low volume. Set `music.chosen` and `music.chosen_reason`. Log it (E11).
- [ ] Then video: upload `outputs/shots/kaggle_job.zip`, run `wan22_i2v.py`. Expect the first run to teach you something (E08, failure B5). Ingest what comes back with `python -m pipeline ingest shots results.zip`.
- [ ] If Wan does not fit or the queue eats the day: stop after three attempts. The Ken Burns film is a complete film.

Checkpoint 2: a rough cut with a picture for every shot and the chosen score.

## 6. Final cut and user test 2 (1 to 2 hours)

- [ ] `make film`, then watch both files on a phone and with headphones.
- [ ] Show it to at least three people. Ask the questions in `DESIGN.md`. Log what they say and what you change.
- [ ] `make release`. It refuses drafts, pending consent and a failed final-cut check. Fix what it names.
- [ ] `make costs`

## 7. Go beyond (pick one, and measure it)

One experiment that changes your mind is worth more than five features. Two that fit in an hour:

- [ ] `python -m pipeline langtest`: the same four lines in Amharic, Tigrinya, Somali and Afaan Oromo. Get one native listener per language if you can. Write up where it fails (E14).
- [ ] `python -m pipeline blindtest pack motion --labels kenburns,wan --a <still clip> --b <wan clip>` with five people (E10).

## 8. Write, record, post

- [ ] Update the status table in `README.md`. Finish `COSTS.md`, `EXPERIMENTS.md`, `FAILURES.md` from your notes.
- [ ] Write the report from `REPORT_OUTLINE.md`. Yours, in your words.
- [ ] Record the walkthrough from `WALKTHROUGH.md`, five minutes at most.
- [ ] Post the film with the platform's AI label on. Write the post yourself: the story, why it matters to you, one thing you learned.
- [ ] Check that every link opens without a login. Submit both assignments.

## If you are short of time

Cut in this order: frontier comparison, Wan clips, a second ceiling experiment. Never cut: consent, the two user tests, the end card, the run log.