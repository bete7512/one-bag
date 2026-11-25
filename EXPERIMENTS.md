# Experiments

One entry per experiment: a hypothesis, the one thing changed, how it is measured, the result, the decision. Change one thing at a time and keep the seed fixed, or the result cannot be read.

**Status on 25 Nov 2026: none of the experiments below has been run.** They are written down first on purpose, so the result cannot bend the hypothesis. A result is filled in only from a real run, with the evidence it points to (`runs.jsonl` lines, a listening sheet, a blind-test result).

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

## Log

Newest first. Copy this block for each experiment that has been run.

```
### E__  <short name>  (date)
Hypothesis:
Changed:            (one thing)
Held fixed:         (seed, model, everything else)
Evidence:           (runs.jsonl run_id, files, who listened or watched)
Result:
Decision:           (what went into storyboard.json or the code, and the commit)
Did it change my mind?
```

## Offline checks (mock providers: not evidence about any model)

These were measured on 25 Nov 2026 with the mock providers. They show that the plumbing works, and nothing about model quality.

| Check | Result |
|---|---|
| Full pipeline from a clean copy, mock providers | 72.5 s film in both ratios, final-cut check passed |
| Change one narration line, run again | 2 model calls (speak, listen); 7 units rebuilt; everything else a cache hit |
| Change one keyframe prompt, run again | 4 model calls (2 candidates, 2 judge calls); only that shot's clip and scenes rebuilt |
| Run again with nothing changed | 0 model calls, 0 units rebuilt |
| Mix loudness on the mock audio | -13.9 LUFS integrated |
