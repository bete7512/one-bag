# Experiments

One entry per experiment: a hypothesis, the one thing changed, how it is measured, the result, the decision. Change one thing at a time and keep the seed fixed, or the result cannot be read.

**Status on 25 Nov 2026, 21:45: E12 and E15 to E23 have been run. E01 to E11, E13 and E14 have not.** Each hypothesis is written down before its run on purpose, so the result cannot bend it. A result is filled in only from a real run, with the evidence it points to (`runs.jsonl` lines, a listening sheet, a blind-test result).

## Plan

| ID | Hypothesis | The one thing changed | Measured by | Result | Decision |
|---|---|---|---|---|---|
| E01 | A style instruction ("calm, warm, unhurried") makes Amharic narration sound more natural than none. | `voice.style` for line s09 only | 3 listeners rate both takes 1 to 5; listening-check score | | |
| E02 | Voices differ in how they say Ankober, Lamberet and Autobus Tera. | `voice.name`, three voices, the lines that hold those names (s01, s04, s06) | Native-speaker rating; which names are said wrongly | | |
| E03 | Writing the year in words avoids a misread "2019". | Digits against words in line s01, once the year is in it | Listening-check transcript; one native listener | | |
| E04 | The listening check agrees with a human ear often enough to be a useful screen. | Nothing: compare its score with human ratings on all 8 lines | Rank agreement between score and rating | | |
| E05 | A reference sheet keeps the young man recognisably the same person across shots. | Keyframes with and without `reference_prompt`, same seeds | Judge `character_match`; 3 viewers answer "same person?" | | |
| E06 | FLUX.2 klein follows the prompt better than FLUX.1 schnell at the same seed. | `models.image`, shots s01, s04, s08 | Judge scores; my own side-by-side | | |
| E07 | Two candidates per shot are enough: a third rarely wins. | `qa.keyframe_candidates` 2 against 3 | How often candidate 3 is picked; image quota used | | |
| E08 | Wan 2.2 fits a 16 GB T4 at 480x832 with 81 frames, and not at 720p. | `video.max_area` and `video.num_frames` | Peak memory and latency per clip from the job results | | |
| E09 | A motion-only prompt gives a steadier clip than one that describes the subject again. | `motion.prompt` for s03, same keyframe and seed | Side-by-side; flicker and drift noted | | |
| E10 | Viewers prefer a Wan clip to a pan over the still for the same shot. | `motion.backend` for the shots that have a Wan clip | Blind A/B with at least five people (`blindtest`) | | |
| E11 | A longer, more specific music caption gives a score that leaves more room for the voice. | `music.caption` short against long, same seeds | Listening under the narration at low volume; my choice and why | | |
| E12 | The brief's ducking settings are right for this voice and score. | Ratio 6 against 3 in the sidechain compressor | Planned: listening on a phone speaker and on headphones. Done: measured, because nobody was there to listen that evening | At ratio 6 the voice stands 18.4 dB over the score, at ratio 3 16.7 dB. Measuring it found three faults in the mix that listening had not. | Ratio 6 stays. The mix was rewritten twice. |
| E13 | Enlarging a square crop for the vertical film is not noticed in a painted style. | Vertical from a square master against a vertical keyframe, one shot | Blind A/B | | |
| E14 | The speech model handles Tigrinya and Somali, and fails on Afaan Oromo, which is not on its supported list. | Language of the same four lines (`langtest`) | Listening-check score and a native speaker's rating per language | | |
| E15 | The lighter text model does the checking calls in seconds, where `gemini-3.8-flash` needs minutes on the free tier, and gives the same verdicts. Added on 25 Nov after failure F01. | `models.text`: `gemini-3.5-flash-lite` against `gemini-3.8-flash`, same pictures, same judge prompt | Latency and failed attempts per call in `runs.jsonl`; the two sets of judge scores side by side | Half right. 1.8 to 9.8 s a call against 104 and 144 s, and 15 of 15 judge calls answered against 2 of 6. But it gave 5.0 to pictures the other model gave 4.0, and 5.0 to pictures with a white frame. | Kept for the checks, because it answers. Its scores no longer decide alone: see the log. |
| E16 | One sentence in the style block ("the painting fills the whole frame") removes the white paper border that five of the first six pictures came back with. Added on 25 Nov after the first real pictures. | One sentence added to `style.block`, same prompts and seeds | Edges that are bare paper, counted by the border check, on the same six candidates | Bordered candidates went from 5 of 6 to 2 of 6. A thin ragged edge stayed on the picks. | Sentence kept. The frame is now guaranteed by the border check and an edge trim, not by wording. |
| E17 | A judge asked to find what is wrong (yes or no questions, a list of what must be visible) tells pictures apart that the 1 to 5 judge scored the same. A stronger model does it better than the light one: it flags a border on the pictures the border check counts as bordered. Added on 25 Nov after E15. | Two steps, one change each: the question (same model, `gemini-3.5-flash-lite`), then the model (`claude-opus-5-5`, same question) | On the same 12 pictures: how many of the 7 measured borders each judge flags, how many different totals it gives, seconds and list price per call | The question did most of it: the light model went from 0 borders flagged to 8. The stronger model then flagged all 9 pictures that have one, gave nine different totals, and named faults nobody had seen. | The new question is the pipeline's judge, and `models.judge` is `claude-opus-5-5`: about 0.016 USD a picture. |
| E18 | A model that reads Amharic finds the subtitle that does not say what its line says. Expected before the run: it finds at least the tense mismatch in s03, which had been noticed by hand that morning. | Nothing in the film: a new check, each written subtitle against its Amharic line | What it reports for the eight draft lines, against a reading by hand | Found the s03 mismatch, and a second one in s07 that the reading by hand had missed. | The check is part of the script stage. Both lines go back to the author. |
| E19 | The character sheet with three poses is being copied into the scenes: one figure seen from behind as the reference gives one young man per picture, seen from behind. Added on 25 Nov after the first ten pictures with a person in them. This is E05 asked the other way round. | `reference_prompt` of the young man: a sheet of three poses against one back view. Same prompts, same seeds | A model counts, for each of 20 pictures, how often he appears and whether a face is turned to the viewer | More than one copy: 8 of 10 with the sheet, 3 of 10 with the back view. A face to the viewer: 8 of 10 against 1 of 10. | The back view is the reference. The friend gets one of his own. |
| E20 | All lines spoken in one request can be cut into one file per line at the long pauses, so the narration costs one of the day's ten speech requests and not eight. Written into `pipeline/narration.py` before the first take. | One request for eight lines, against the brief's tip of one request per line | The margin between the pauses used as cuts and the pauses left inside lines; how many lines two cutting methods agree on; requests spent | Margin 1.24, where 1.5 is needed. The methods agree on 4 of 8 lines. 5 speech requests in all. | A line is kept from a take only where both methods agree. The rest are spoken alone. See F04. |
| E21 | The listening check scored two correct lines 0.16 because of how it was asked, not because of how they were spoken. Added on 25 Nov after the first eight scores. | The question to the listener: "the script of the language being spoken" against naming the language. Same eight audio files | The match between line and transcript, per line | The two lines rose from 0.16 to 0.91 and 0.81. Another fell from 0.84 to 0.64 with no change in its audio. | The language is named. A score is read as a screen, never as a verdict on the voice. |
| E22 | A short description that names one instrument gets that instrument. The first description asked for a krar, a washint flute and a drone in 42 words, and the listening model heard a music box and a piano in two of the three candidates. Written on 25 Nov at 21:05, while the second job was running on Kaggle and before any of its music had been heard. | `music.caption`: 42 words and three instruments against 27 words and one instrument ("Solo krar ... One instrument only"). Same seeds, tempo, length and model | The instruments a listening model names in each candidate, with the same question as for the first set. Then my own ear | Not confirmed. No candidate is heard as a krar, and every candidate of the short description has two instruments. What changed is the family: two of three are now plucked zithers. | None yet: six candidates wait for my ear. |
| E23 | A stranger who clones the repository can rebuild the cut with one command, no key, and no call to any model, because every answer a model gave is committed and everything else is cut from those answers by FFmpeg. | Nothing in the film: a fresh clone in an empty folder, no `.env`, no key in the environment, `make setup`, then `python -m pipeline film` | Lines added to `runs.jsonl`; units that were cache hits against units that were rebuilt; the final-cut check | 0 model calls. 42 hits on model outputs, 53 units rebuilt by FFmpeg, in 1 min 49 s. The check passes. | Kept as a step before every release. |

## Log

Newest first. Copy this block for each experiment that has been run.

```
### E__  <short name>  (date)
Hypothesis:
Changed:            (one thing)
Held fixed:         (seed, model, everything else)
Evidence:           (runs.jsonl run_id, files, who listened or watched)
Result:
Decision:           (what went into storyboard.json or the code)
What it changed:
```

### E22  A short description of the score, against a long one  (25 Nov 2026)

Hypothesis: a short description that names one instrument gets that instrument. The first description asked for a krar, a washint flute and a drone, and the listening model heard a music box and a piano in two of the three candidates. Written into the plan table at 21:05, while the job was running on Kaggle and before any of its music had been heard.

Changed: `music.caption`, and nothing else.

- Long, 42 words: "Slow, sparse instrumental. A solo krar (Ethiopian lyre) plucks a gentle pentatonic melody in the tizita mood, a soft washint flute answers, warm low drone underneath. Intimate room sound, nostalgic and tender, a lot of space between notes. No drums, no vocals."
- Short, 27 words: "Solo krar, the Ethiopian six-string lyre, plucked slowly. A sparse pentatonic melody in the tizita mood. One instrument only, in a quiet room. No drums, no vocals."

Held fixed: the seeds (11, 22, 33), 66 beats a minute, 80 seconds, ACE-Step 1.5 turbo on two T4s, and the question to the listening model (`gemini-3.5-flash-lite`).

Evidence: the six files `outputs/music/candidate_*.flac`, with what the listener wrote beside each in `candidate_*_heard__*.json`. `runs.jsonl`: provider `kaggle`, runs `20261125T131559Z-de935f` and `20261125T181703Z-11f05a`.

Result:

| Seed | Long description: the listener hears | Short description: the listener hears |
|---|---|---|
| 11 | music box, piano | koto, shakuhachi flute, with a "flute entrance" at 7 s |
| 22 | zither | guzheng, bells |
| 33 | music box, chimes, strings | kalimba, chimes, with a "percussion entry" at 29 s |

None of the six has vocals and all six are slow. The second set took 10.1, 6.2 and 6.4 s on the GPU, 6.4 GB at the peak, 0.004 USD at the list price of a rented T4.

The hypothesis is not confirmed. No candidate is heard as a krar. "One instrument only" gave two instruments three times out of three, and "no drums" was broken once. What the short description did change is the family of the lead instrument: one plucked string instrument in three before, two in three now, both zithers from East Asia.

One caution about the measure itself. The listener named a koto and a guzheng. It may not know a krar when it hears one, the same way it wrote correct Amharic in Latin letters (E21). So the names are a screen, and whether any of the six sounds like a krar playing tizita is for an Ethiopian ear.

Decision: none yet. All six candidates wait for my ear. If none sounds right, the next change is the model's own vocabulary: ask for "lyre" or "harp" with no country in the description.

What it changed: I expected the music model to follow a named instrument the way an image model follows a named object. It does not know this one. A description steers the mood, the tempo and the family of the sound, and the rest has to be chosen by listening.

### E12  The ducking, measured instead of heard  (25 Nov 2026)

Hypothesis: the brief's ducking settings (threshold 0.02, ratio 6, attack 300 ms, release 1500 ms) are right for this voice and score. The plan was to judge it by ear, ratio 6 against ratio 3. Nobody was there to listen that evening, so it was measured.

Changed: the ratio of the sidechain compressor, 6 against 3.

Held fixed: the eight narration lines on the timeline of the radio cut, the score (candidate 2 of the first set), every other setting.

Evidence: `python experiments/e12_ducking.py` builds both mixes with the pipeline's own mix function and measures them. `outputs/experiments/E12/results.json` holds every number, with a line on how each is computed. It has three parts: `before` (the mix code of commit `7d3222a`), `after_first_fix` (`4a80a3e`) and `after` (`31faa93`). The script checks on every run that its copy of the mix chain gives the same file, byte for byte, as the pipeline.

Result, the question that was asked (the mix code as it is now):

| | Ratio 6 | Ratio 3 |
|---|---:|---:|
| The compressor takes off the score while the voice speaks | 11.1 dB | 9.4 dB |
| The same in the gaps between lines | 1.3 dB | 1.1 dB |
| Voice over score in the finished mix | 18.4 dB | 16.7 dB |
| The same for the weakest line | 17.1 dB | 15.2 dB |
| Loudness of the mix | -14.7 LUFS | -14.7 LUFS |

At both ratios every line stands at least 15 dB over the score. Ratio 6 buys 1.7 dB more. One number does not match the setting: 0.1 s into a line the score is already down by 9 to 22 dB, so an attack of 300 ms is no 300 ms ramp in this filter.

Result, what the measuring found. Three faults were in the mix, and nobody had heard them:

| | Before | After the first fix | Now |
|---|---|---|---|
| Samples of the mix over full scale before the last step | 167, clipped at 16 bit | 554, kept in float | 554, kept in float |
| How long the score lasts in a mix of 79.96 s | 78.66 s | 79.96 s | 79.96 s |
| Level of the eight lines before the last step, lowest to highest | 4.2 dB apart | 1.8 dB apart | 1.8 dB apart |
| The last step, as the code said | a fixed gain was asked for | "limited+linear" | "limited once, then one fixed gain" |
| The last step, as measured | the gain moved: 2.2 dB in speech, 5.0 dB in the gaps | the gain still moved: 2.6 and 4.3 dB | one gain of 2.90 dB, the same to 0.002 dB over 1,460 windows |
| Loudness of the mix | -14.5 LUFS | -14.1 LUFS | -14.7 LUFS |
| True peak of the mix after the AAC encoder | not measured | -1.16 dB | -1.43 dB |

1. The voice track peaked over full scale and was cut off at 16 bit before the loudness step.
2. A FLAC score arrives at the compressor in larger blocks than the voice, and the compressor then drops the end: the score stopped 1.3 s early and lost half of its fade.
3. `loudnorm` did not apply the fixed gain it was asked for. FFmpeg reported `dynamic`: the gain was 2.8 dB higher in the gaps than under the voice, which undoes part of the ducking.

The first fix was wrong about the third point, and said it was right. It limited the peaks and then called `loudnorm` again, and the code wrote "limited+linear" into the index without asking FFmpeg what it had done. The limiter had made the mix quieter, so more gain was needed, so the peaks were in the way again. The second measurement caught it: still `dynamic`. The step now uses no `loudnorm`. It limits once and applies the gain the peaks allow.

What the present mix costs, measured: it lands 0.7 LU under -14 with this score. The limiter is not light on this voice: it lowers 168 of 1,600 windows of 50 ms, all inside lines, by up to 7.65 dB on a peak, and that leaves the lines 1.3 LU apart in the finished mix. It delays the sound by about 5 ms.

Decision: ratio 6 stays. Whether 18 dB between voice and score is too much, so that the score disappears, is a question for the ear, and it goes to the viewers of the second test. The mix code is as described in `ARCHITECTURE.md`, "Sound".

What it changed: the ratio was the smallest thing this experiment answered. I had taken the mix as finished because the final-cut check passed: the loudness was near -14 and the peak under -1. Both were true and the mix was still wrong in three ways the check does not look at. And a fix is a claim like any other: the first one was only shown to be wrong because the same measurement was run again on it.

### E23  A clean clone rebuilds the cut without a key  (25 Nov 2026)

Hypothesis: the brief asks that a stranger can clone the repository, run one command and regenerate the film. The pipeline keeps every answer a model gave (original pictures, narration lines, the take, judge and listener answers) and git-ignores what FFmpeg can cut from them. If that split is right, a clone with no key rebuilds the cut and calls no model. If one file is missing from the repository, the run stops and asks for a key.

Changed: nothing in the film. The place it is built: a fresh clone of commit `11dcdc1` in an empty folder, with no `.env` and no key in the environment. Then the documented steps: `make setup`, `python -m pipeline film`.

Held fixed: the storyboard and every committed output.

Evidence: `outputs/experiments/E23/clean_clone.json`, taken from the event log of that run (`20261125T180311Z-8f6e0f`).

Result: the cut was rebuilt in 1 minute 49 seconds and the run log has 351 lines before and after.

| | Units |
|---|---:|
| Cache hits on model outputs: 8 subtitle checks, 8 narration lines and their 8 listening checks, 18 judge answers | 42 |
| Rebuilt by FFmpeg alone: 20 keyframes cut from their kept originals, 9 pan-and-zoom clips, the placeholder score, 23 assembly units | 53 |
| Calls to a model | 0 |

The final-cut check passed on the rebuilt files, with the same two notes as on the working machine: a placeholder score, and no generated motion yet. Both films are 79.96 s, as there.

Decision: this run is repeated on the release commit, and the README says how to repeat it.

What it changed: until this run "reproducible" was a claim that the tests supported with mock providers only. The test workflow on GitHub builds a mock film on every push. This is the first time the real cut was rebuilt somewhere else. It also sets the limit of the claim: what is reproduced is the cut from the kept model answers. Asking the models again would give other pictures and another voice.

### E21  Does the listening check measure the voice or the listener  (25 Nov 2026)

Hypothesis: two of the first eight narration lines scored 0.16 in the listening check, far under the floor of 0.6. The transcripts were in Latin letters ("Lambara cders məniştə nappa" for `ላምበረት ስደርስ መሽቶ ነበር`). Read aloud they are the right words. So the low score comes from the question, which asked for "the script of the language being spoken", and not from the speech.

Changed: the question to the listener. It now says the audio is narration in Amharic and asks for the usual script of Amharic (`LISTEN_PROMPT` in `pipeline/narration.py`).

Held fixed: the eight audio files, byte for byte. The listener, `gemini-3.5-flash-lite`, at temperature 0.

Evidence: `runs.jsonl`, units `s01_listen` to `s09_listen`, run `20261125T171237Z-6f6e51` with the old question and run `20261125T171701Z-c303d6` with the new one. The transcripts are in `outputs/narration/`.

Result:

| Line | Old question | Language named |
|---|---:|---:|
| s01 | 0.93 | 0.83 |
| s02 | 0.73 | 0.85 |
| s03 | 0.84 | 0.64 |
| s04 | 0.16 | 0.91 |
| s06 | 0.90 | 0.90 |
| s07 | 0.77 | 0.81 |
| s08 | 0.16 | 0.81 |
| s09 | 0.87 | 0.91 |

The two lines written in Latin letters are now written in Ethiopic and pass. All eight are at or above the floor. But s03 fell by 0.20 on the same audio: this time the listener began its transcript with a sentence about Martin Luther King that nobody spoke.

Decision: the language is named in the question. The check stays what its docstring says: it measures, it does not decide. A low score sends a person to listen to that line, and a high one does not excuse them.

What it changed: until this run a low score was read as "the speech model said the line badly". On these eight lines the score moved by up to 0.75 with no change in the sound. The largest part of it is the listener.

### E20  One take for all lines, against one request per line  (25 Nov 2026)

Hypothesis: the free speech tier allows ten requests a day, so eight lines spoken one by one leave two for every re-take. Spoken in one request, with the documented pause tag after each line, the answer can be cut at its longest pauses into one file per line. Written into the narration stage before the first real take.

Changed: one request for the eight lines, where the brief's tip is one request per line.

Held fixed: the voice (`Charon`), the style sentence, the lines.

Evidence: the take is `outputs/narration/takes/take__49b531e67e924f58_1.wav`, with what the listener heard in each of its 35 phrases in the record beside it. `runs.jsonl`: unit `take` in run `20261125T164336Z-2fb093`, units `take_phrase_01` to `take_phrase_35` in run `20261125T170143Z-902d5d`, units `s06` to `s09` in run `20261125T171237Z-6f6e51`. The whole story is F04 in `FAILURES.md`.

Result: one request gave 70.19 s of audio in 19 s. It could not be cut as planned.

| | |
|---|---|
| Pauses of 0.25 s or more in the take | 36 |
| The seven longest, which should be the seven gaps between lines | 1.42 to 1.90 s |
| The longest pause left inside a line | 1.15 s |
| Margin between the two (1.5 is the least the stage accepts) | 1.24 |
| Lines where the cut by pauses and the cut by words agree | 4 of 8 (s01 to s04) |
| Phrases the listener heard as the pause tag itself | phrase 23 as `long pause`, phrase 28 as `ሎንግ` |
| Speech requests spent on the eight lines | 5: the take and four single lines |

Decision: the take stays as the first try, because four lines for one request is still a gain. What changed is the rule for trusting it: a line is cut from a take only where the pauses and the words agree on both of its ends, and any other line is spoken alone.

What it changed: the brief says "generating narration line by line, one file per shot, makes re-takes cheap and timing easy to adjust". This project took the first half as a cost and set out to avoid it. The tip is about the second half: a line that comes back alone needs no cutting, and cutting is where an evening went. With ten requests a day the honest price of eight lines is between five and eight requests, not one.

### E19  The character sheet that copied itself into the scenes  (25 Nov 2026)

Hypothesis: the brief suggests a reference sheet for each character, and the first storyboard asked for the usual one: the young man three times, from the front, the side and behind. In the first pictures he stood in the scene two or three times, in those same three poses, face to the viewer. So the image model treats the sheet as content to keep. A reference with one figure seen from behind should give one figure, seen from behind.

Changed: the `reference_prompt` of the young man, and nothing else. Before: "Character sheet on a plain warm background: the same young man shown three times, from the front, from the side and from behind". After: "One single full-length figure on a plain warm background, seen from behind".

Held fixed: the five shot prompts with him in them (s01, s03, s04, s06, s08), their seeds, two candidates each, the model (FLUX.2 klein 4B), the style block.

Evidence: the twenty pictures are in `outputs/keyframes/original/`, drawn in runs `20261125T165037Z-d7d28c` and `20261125T170301Z-fdd723`. The count is `python experiments/e19_reference.py`: one question to `claude-opus-5-5` for each picture, the same for both sets. Answers in `outputs/experiments/E19/results.json`, calls in `runs.jsonl` under run `20261125T171008Z-ca221d`.

Result:

| Reference | Pictures | He appears more than once | A face is turned to the viewer | Looks like a photograph |
|---|---:|---:|---:|---:|
| Sheet of three poses | 10 | 8 | 8 | 1 |
| One back view | 10 | 3 | 1 | 0 |

With the sheet, both candidates of s03 and of s06 held him three times. With the back view, the three pictures that still show two of him are all shots with his friend in them (s04, s06, s08): the model drew the friend as a second copy of the only reference it was given. Twenty answers in 3.0 to 11.2 s, 0.27 USD.

Decision: the reference for a character is one figure, in the view the film uses. The friend got a reference of his own, with different clothes. That settled the one shot where the two stand side by side (s06). It did not rescue the two shots that put them in a crowd: see F05 in `FAILURES.md`.

What it changed: a reference sheet was taken as plain good practice, and E05 was planned to ask only whether it helps. It was the cause of the worst fault in the first pictures. It also matters beyond looks: the rule of this film is that nobody's face is generated, and the sheet put a face in eight pictures of ten.

### E18  Does the subtitle say what the line says  (25 Nov 2026)

Hypothesis: a model that reads Amharic finds the subtitle that does not say what its line says. Before the run one such case was known: in s03 the line says "he knows the city" and the subtitle "he knew". It had been noticed by hand that morning, so the check had to find at least that one.

Changed: nothing in the film. A new check in the script stage: for each written subtitle, the model translates the Amharic line literally and names every difference in meaning (`CHECK_PROMPT` in `pipeline/script.py`).

Held fixed: the eight draft lines and their subtitles as they stood, the model (`claude-opus-5-5`).

Evidence: `outputs/script/index.am.json` holds each literal translation and each difference. The eight calls are in `runs.jsonl`, units `s01_subtitle_check` to `s10_subtitle_check`. These were the lines of the first draft, with ten shots. The storyboard was rewritten the same evening from the story as the author told it, and the check ran again on the eight new lines: all eight subtitles pass.

Result: six subtitles pass. Two do not.

| Shot | The line says | The subtitle says |
|---|---|---|
| s03 | From Lamberet. He knows the city. | At Lamberet. He knew the city. |
| s07 | In the morning a bus takes me to Bahir Dar. | In the morning a bus would take me to Bahir Dar. |

The s07 mismatch had not been seen by hand. Eight answers in 2.7 to 6.0 s, 0.059 USD in all.

Decision: the check stays in the script stage, as an optional unit, so it can never stop a run. Its findings are shown on the review page and listed by the final-cut check. Both lines go back to the author with the literal translation: which of the two is right is his to say, not the model's.

What it changed: the subtitles were assumed correct because the same hand wrote both versions. A reader who knows no Amharic cannot check them, and the film is graded on them.

### E17  A judge that looks for what is wrong  (25 Nov 2026)

Hypothesis: a judge asked to find what is wrong tells pictures apart that the 1 to 5 judge scored the same, and a stronger model does it better than the light one.

Changed: two steps, one change each. First the question, on the same model (`gemini-3.5-flash-lite`): the old one asked for three scores from 1 to 5, the new one asks for a list of what must be visible, and yes or no on a border, on writing, on a wrong setting and on broken anatomy (`JUDGE_PROMPT` in `pipeline/keyframes.py`). Then the model: `claude-opus-5-5` with the new question.

Held fixed: the twelve pictures of 25 Nov (shots s02, s05 and s07, two candidates each, before and after E16), the picture size sent to the judge, temperature 0.

Evidence: `python experiments/e17_judges.py` writes `outputs/experiments/E17/results.json`, with every answer in full and the measured border of each picture. Its calls are in `runs.jsonl` as stage `experiment`, run `20261125T120616Z-8a8230`.

Result, first step (the question):

| | Old question (E15) | New question |
|---|---|---|
| Pictures the judge calls bordered | 0 of 12 | 8 of 12 |
| Of the 7 pictures the border check measures as bordered | 0 flagged | 6 flagged |
| Different totals over the 12 pictures | 2 (eleven at 5.0, one at 4.4) | 5 (from 5.0 down to -0.1) |
| Other faults named | none | "nothing in sharp focus" missing on three of the four crowd pictures, a wrong setting on one |

The two pictures it flagged beyond the measured seven are the picks of E16 that the border check passes with 0 bare sides. Looked at by eye, both have the thin ragged edge noted in E16: the judge saw what the measurement was too coarse for. The one measured border it missed is s02 candidate 2 of the first set, with paper on three sides.

The calls: 12 answers in 1.9 to 9.1 s, after 7 attempts that got HTTP 503 and passed on a later attempt. List price 0.012 USD for all of it.

Result, second step (the model). The first try was refused for lack of credit (F03). It ran two hours later, in run `20261125T131628Z-45b336` of the same script, which skipped the answers it already had.

| | `gemini-3.5-flash-lite` | `claude-opus-5-5` |
|---|---|---|
| Pictures it calls bordered | 8 of 12 | 9 of 12 |
| Of the 7 the border check measures as bordered | 6 | 7 |
| Different totals over the 12 pictures | 5 | 9 |
| Highest total it gave | 5.0, four times | 4.4, twice |
| Seconds per answer | 1.9 to 9.1 | 3.6 to 9.6 |
| Failed attempts | 7 of 19, all HTTP 503 | none of 12 |
| List price for the 12 | 0.012 USD, not charged | 0.195 USD, paid |

The nine pictures the stronger model calls bordered are exactly the nine with a border when looked at by eye: the seven measured ones and the two with the thin ragged edge. The three it passes are the three that fill their frame. It also named things nobody had noticed: the room's window shows cars where the description asks for buses, the legs of the walkers in the crowd run into each other, and the road picture has its clouds high in the sky where the description puts low cloud on the far hills. The light model gave that road picture 5.0.

Decision: the new question is the pipeline's judge (`JUDGE_VERSION = 2`), and a border, writing, a wrong setting or broken anatomy each take points off the total. `models.judge` is `claude-opus-5-5`. The measured border check stays first in the pick: it costs nothing, and on thin edges the judge sees more than it does, so neither replaces the other.

What it changed: the weak judge of E15 was blamed on the model. Most of it was the question. Asked "how good is this, 1 to 5" the light model said 5. Asked "is there a border, yes or no" it found eight. The stronger model is still worth its two cents a picture, because its notes say what to change in the prompt.

### E16  One sentence against the white border  (25 Nov 2026)

Hypothesis: one sentence in the style block ("the painting fills the whole frame") removes the white paper border that five of the first six pictures came back with.

Changed: `style.block` gained the sentence "The painting fills the whole frame from edge to edge."

Held fixed: the prompts of shots s02, s05 and s07, their seeds (two candidates each), the image model, the size.

Evidence: the border check counts, for each picture, how many of its four sides are bare paper (`paper_sides` in `outputs/keyframes/index.json`; the code is `paper_edges` in `pipeline/keyframes.py`). The image calls are in `runs.jsonl`: run `20261125T104632Z-cf26db` before, run `20261125T112815Z-29626b` after. Both sets of pictures are kept in `outputs/keyframes/original/`.

Result:

| Shot | Bare sides before (candidate 1, 2) | Bare sides after (candidate 1, 2) |
|---|---|---|
| s02 the road | 0, 3 | 1, 1 |
| s05 the crowd | 4, 2 | 3, 0 |
| s07 the room | 4, 4 | 2, 0 |

A picture counts as bordered at two bare sides or more, because one bare side can be a white sky. Bordered candidates: 5 of 6 before, 2 of 6 after. Bare sides in total: 17 of 24 before, 7 of 24 after. Looked at by eye, the two picks that the check passes with 0 sides (s05 candidate 2, s07 candidate 2) still had a ragged cream edge about 1% of the side wide, too thin for the check.

Decision: the sentence stays in `style.block`. The pick prefers the candidate with the fewest bare sides before it looks at the judge's score. `format.edge_trim` cuts 3.5% from each side of every picture, for the thin edge the check cannot see.

What it changed: a prompt sentence was expected to be enough, and it was not. After it, each shot had exactly one clean candidate out of two, so a single candidate per shot would have left a border in the film. The frame is now guaranteed by a measurement and a trim.

### E15  A lighter model for the checking calls  (25 Nov 2026)

Hypothesis: `gemini-3.5-flash-lite` does the checking calls in seconds where `gemini-3.8-flash` needs minutes on the free tier, and gives the same verdicts. Written after failure F01.

Changed: `models.text`.

Held fixed: the pictures, the judge prompt, temperature 0.

Evidence: `runs.jsonl`, every line whose unit ends in `_judge`. `gemini-3.8-flash`: runs `20261125T104632Z-cf26db` and `20261125T105827Z-7dbbde`. `gemini-3.5-flash-lite`: runs `20261125T110100Z-1899ca`, `20261125T112523Z-4df8a1` and `20261125T112815Z-29626b`. The scores are the `*_judge__*.json` files in `outputs/keyframes/`.

Result:

| | `gemini-3.8-flash` | `gemini-3.5-flash-lite` |
|---|---|---|
| Judge attempts | 22 | 19 |
| Answered | 2 | 15 |
| Failed | 16 with HTTP 503, 2 timed out at 300 s, 2 with HTTP 429 | 4 with HTTP 503, each answered on the next attempt |
| Seconds per answer | 104 and 144 | 1.8 to 9.8 |
| Seconds spent in failed attempts | 825 | 9 |
| Pictures left without a score | 4 of 6 | 0 of 12 |

Verdicts: the two pictures that both models scored got 4.0 and 4.0 from `gemini-3.8-flash` and 5.0 and 5.0 from `gemini-3.5-flash-lite`. Over all its answers the lighter model gave 5.0 fourteen times out of fifteen, including to a picture with a white frame on all four sides. Neither model mentioned a border.

Decision: `models.text` is `gemini-3.5-flash-lite`. A check that answers is worth more than a better one that does not, and the free tier gives it 500 requests a day against 20.

What it changed: the hypothesis was half right. The lighter model is faster and available, and its 1 to 5 scores do not tell two pictures apart. So the pick no longer rests on those scores alone: the border is measured in code, and a stricter judge is the next experiment.

## Offline checks (mock providers: not evidence about any model)

These were measured on 25 Nov 2026 with the mock providers. They show that the plumbing works, and nothing about model quality.

| Check | Result |
|---|---|
| Full pipeline from a clean copy, mock providers | 72.5 s film in both ratios, final-cut check passed |
| Change one narration line, run again | 3 model calls (subtitle check, speak, listen); 8 units rebuilt, 9 when the longer line makes its shot longer; everything else a cache hit |
| Change one keyframe prompt, run again | 4 model calls (2 candidates, 2 judge calls); only that shot's clip and scenes rebuilt |
| Run again with nothing changed | 0 model calls, 0 units rebuilt |
| Mix loudness on the mock audio | -13.9 LUFS integrated |
