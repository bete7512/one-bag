# Experiments

One entry per experiment: a hypothesis, the one thing changed, how it is measured, the result, the decision. Change one thing at a time and keep the seed fixed, or the result cannot be read.

**Status on 25 Nov 2026, 16:40: E15, E16, E17 and E18 have been run. The others have not.** Each hypothesis is written down before its run on purpose, so the result cannot bend it. A result is filled in only from a real run, with the evidence it points to (`runs.jsonl` lines, a listening sheet, a blind-test result).

## Plan

| ID | Hypothesis | The one thing changed | Measured by | Result | Decision |
|---|---|---|---|---|---|
| E01 | A style instruction ("calm, warm, unhurried") makes Amharic narration sound more natural than none. | `voice.style` for line s10 only | 3 listeners rate both takes 1 to 5; listening-check score | | |
| E02 | Voices differ in how they say Ankober, Lamberet and Autobus Tera. | `voice.name`, three voices, line s03 | Native-speaker rating; which names are said wrongly | | |
| E03 | Writing the year in words avoids a misread "2019". | Digits against words in line s01 | Listening-check transcript; one native listener | | |
| E04 | The listening check agrees with a human ear often enough to be a useful screen. | Nothing: compare its score with human ratings on all 8 lines | Rank agreement between score and rating | | |
| E05 | A reference sheet keeps the young man recognisably the same person across shots. | Keyframes with and without `reference_prompt`, same seeds | Judge `character_match`; 3 viewers answer "same person?" | | |
| E06 | FLUX.2 klein follows the prompt better than FLUX.1 schnell at the same seed. | `models.image`, shots s01, s04, s08 | Judge scores; my own side-by-side | | |
| E07 | Two candidates per shot are enough: a third rarely wins. | `qa.keyframe_candidates` 2 against 3 | How often candidate 3 is picked; image quota used | | |
| E08 | Wan 2.2 fits a 16 GB T4 at 480x832 with 81 frames, and not at 720p. | `video.max_area` and `video.num_frames` | Peak memory and latency per clip from the job results | | |
| E09 | A motion-only prompt gives a steadier clip than one that describes the subject again. | `motion.prompt` for s03, same keyframe and seed | Side-by-side; flicker and drift noted | | |
| E10 | Viewers prefer a Wan clip to a pan over the still for the same shot. | `motion.backend` for the shots that have a Wan clip | Blind A/B with at least five people (`blindtest`) | | |
| E11 | A longer, more specific music caption gives a score that leaves more room for the voice. | `music.caption` short against long, same seeds | Listening under the narration at low volume; my choice and why | | |
| E12 | The brief's ducking settings are right for this voice and score. | Ratio 6 against 3 in the sidechain compressor | Listening on a phone speaker and on headphones | | |
| E13 | Enlarging a square crop for the vertical film is not noticed in a painted style. | Vertical from a square master against a vertical keyframe, one shot | Blind A/B | | |
| E14 | The speech model handles Tigrinya and Somali, and fails on Afaan Oromo, which is not on its supported list. | Language of the same four lines (`langtest`) | Listening-check score and a native speaker's rating per language | | |
| E15 | The lighter text model does the checking calls in seconds, where `gemini-3.8-flash` needs minutes on the free tier, and gives the same verdicts. Added on 25 Nov after failure F01. | `models.text`: `gemini-3.5-flash-lite` against `gemini-3.8-flash`, same pictures, same judge prompt | Latency and failed attempts per call in `runs.jsonl`; the two sets of judge scores side by side | Half right. 1.8 to 9.8 s a call against 104 and 144 s, and 15 of 15 pictures scored against 2 of 6. But it gave 5.0 to pictures the other model gave 4.0, and 5.0 to pictures with a white frame. | Kept for the checks, because it answers. Its scores no longer decide alone: see the log. |
| E16 | One sentence in the style block ("the painting fills the whole frame") removes the white paper border that five of the first six pictures came back with. Added on 25 Nov after the first real pictures. | One sentence added to `style.block`, same prompts and seeds | Edges that are bare paper, counted by the border check, on the same six candidates | Bordered candidates went from 5 of 6 to 2 of 6. A thin ragged edge stayed on the picks. | Sentence kept. The frame is now guaranteed by the border check and an edge trim, not by wording. |
| E17 | A judge asked to find what is wrong (yes or no questions, a list of what must be visible) tells pictures apart that the 1 to 5 judge scored the same. A stronger model does it better than the light one: it flags a border on the pictures the border check counts as bordered. Added on 25 Nov after E15. | Two steps, one change each: the question (same model, `gemini-3.5-flash-lite`), then the model (`claude-opus-5-5`, same question) | On the same 12 pictures: how many of the 7 measured borders each judge flags, how many different totals it gives, seconds and list price per call | The question did most of it: the light model went from 0 borders flagged to 8. The stronger model then flagged all 9 pictures that have one, gave nine different totals, and named faults nobody had seen. | The new question is the pipeline's judge, and `models.judge` is `claude-opus-5-5`: about 0.016 USD a picture. |
| E18 | A model that reads Amharic finds the subtitle that does not say what its line says. Expected before the run: it finds at least the tense mismatch in s03, which had been noticed by hand that morning. | Nothing in the film: a new check, each written subtitle against its Amharic line | What it reports for the eight draft lines, against a reading by hand | Found the s03 mismatch, and a second one in s07 that the reading by hand had missed. | The check is part of the script stage. Both lines go back to the author. |

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

### E18  Does the subtitle say what the line says  (25 Nov 2026)

Hypothesis: a model that reads Amharic finds the subtitle that does not say what its line says. Before the run one such case was known: in s03 the line says "he knows the city" and the subtitle "he knew". It had been noticed by hand that morning, so the check had to find at least that one.

Changed: nothing in the film. A new check in the script stage: for each written subtitle, the model translates the Amharic line literally and names every difference in meaning (`CHECK_PROMPT` in `pipeline/script.py`).

Held fixed: the eight draft lines and their subtitles as they stood, the model (`claude-opus-5-5`).

Evidence: `outputs/script/index.am.json` holds each literal translation and each difference. The eight calls are in `runs.jsonl`, units `s01_subtitle_check` to `s10_subtitle_check`.

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
| Change one narration line, run again | 2 model calls (speak, listen); 7 units rebuilt; everything else a cache hit |
| Change one keyframe prompt, run again | 4 model calls (2 candidates, 2 judge calls); only that shot's clip and scenes rebuilt |
| Run again with nothing changed | 0 model calls, 0 units rebuilt |
| Mix loudness on the mock audio | -13.9 LUFS integrated |
