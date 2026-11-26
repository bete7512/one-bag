# Experiments

One entry per experiment: a hypothesis, the one thing changed, how it is measured, the result, the decision. Change one thing at a time and keep the seed fixed, or the result cannot be read.

**Status on 26 Nov 2026, 15:09: E08, E12 and E15 to E31 have a result. E01, E03, E04, E06, E07, E09, E10, E13 and E14 were not run. E02, E05 and E11 were not run as planned: a later experiment answered each in another form.** Each hypothesis is written down before its run on purpose, so the result cannot bend it. E26 and E27 are the exceptions, and their entries say so. A result is filled in only from a real run, with the evidence it points to (`runs.jsonl` lines, a listening sheet, a blind-test result).

## Plan

Rows E01 to E14 were written before the first real run. A row that was never run says "Not run." and has no decision. Three of them were answered by a later experiment in another form, and the row says which.

| ID | Hypothesis | The one thing changed | Measured by | Result | Decision |
|---|---|---|---|---|---|
| E01 | A style instruction ("calm, warm, unhurried") makes Amharic narration sound more natural than none. | `voice.style` for line s09 only | 3 listeners rate both takes 1 to 5; listening-check score | Not run. The voice now in the cut takes no style instruction (E26). | |
| E02 | Voices differ in how they say Ankober, Lamberet and Autobus Tera. | `voice.name`, three voices, the lines that hold those names (s01, s04, s06) | Native-speaker rating; which names are said wrongly | Not run in this form. E26 compared four voices on all eight lines, by a listening model and by pitch. Nobody rated how each voice says the three names. | See E26. |
| E03 | Writing the year in words avoids a misread "2019". | Digits against words in line s01, once the year is in it | Listening-check transcript; one native listener | Not run. The year is in the narration since 26 Nov, now in line s00, written in words: ሁለት ሺህ አሥራ ሁለት, 2012 in the Ethiopian calendar. The same line with digits was never recorded. | |
| E04 | The listening check agrees with a human ear often enough to be a useful screen. | Nothing: compare its score with human ratings on all 8 lines | Rank agreement between score and rating | Not run. No person has rated the lines one by one: the listeners of user test 1 wrote free comments (`DESIGN.md`). | |
| E05 | A reference sheet keeps the young man recognisably the same person across shots. | Keyframes with and without `reference_prompt`, same seeds | Judge `character_match`; 3 viewers answer "same person?" | Not run in this form. E19 asked it the other way round: the sheet was the cause of the worst fault. | See E19. |
| E06 | FLUX.2 klein follows the prompt better than FLUX.1 schnell at the same seed. | `models.image`, shots s01, s04, s08 | Judge scores; my own side-by-side | Not run. `flux-1-schnell` was never called (`runs.jsonl`). | |
| E07 | Two candidates per shot are enough: a third rarely wins. | `qa.keyframe_candidates` 2 against 3 | How often candidate 3 is picked; image quota used | Not run. | |
| E08 | Wan 2.2 fits a 16 GB T4 at 480x832 with 81 frames, and not at 720p. | `video.max_area` and `video.num_frames` | Peak memory and latency per clip from the job results | It fits at the small size: 13.45 to 13.46 GB at the peak for 608 x 608 and 81 frames, 766 to 890 s a clip. 720p was not tried: 1.6 GB are left. The second clip of the first job was killed (F07). Of the four clips made, one is used. | The settings stay. A job of several clips works since the fix in F07. Only the road shot moves. |
| E09 | A motion-only prompt gives a steadier clip than one that describes the subject again. | `motion.prompt` for s03, same keyframe and seed | Side-by-side; flicker and drift noted | Not run. | |
| E10 | Viewers prefer a Wan clip to a pan over the still for the same shot. | `motion.backend` for the shots that have a Wan clip | Blind A/B with at least five people (`blindtest`) | Not run. It is the blind pair of user test 2, which is not done (`DESIGN.md`). | |
| E11 | A longer, more specific music caption gives a score that leaves more room for the voice. | `music.caption` short against long, same seeds | Listening under the narration at low volume; my choice and why | Not run in this form. E22 compared a long and a short description by what a listener hears in them. | See E22. |
| E12 | The brief's ducking settings are right for this voice and score. | Ratio 6 against 3 in the sidechain compressor | Planned: listening on a phone speaker and on headphones. Done: measured, because nobody was there to listen that evening | At ratio 6 the voice stands 18.4 dB over the score, at ratio 3 16.7 dB. Measuring it found three faults in the mix that listening had not. | Ratio 6 stays. The mix was rewritten twice. |
| E13 | Enlarging a square crop for the vertical film is not noticed in a painted style. | Vertical from a square master against a vertical keyframe, one shot | Blind A/B | Not run. | |
| E14 | The speech model handles Tigrinya and Somali, and fails on Afaan Oromo, which is not on its supported list. | Language of the same four lines (`langtest`) | Listening-check score and a native speaker's rating per language | Not run. No call of the language test is in `runs.jsonl`. | |
| E15 | The lighter text model does the checking calls in seconds, where `gemini-3.8-flash` needs minutes on the free tier, and gives the same verdicts. Added on 25 Nov after failure F01. | `models.text`: `gemini-3.5-flash-lite` against `gemini-3.8-flash`, same pictures, same judge prompt | Latency and failed attempts per call in `runs.jsonl`; the two sets of judge scores side by side | Half right. 1.8 to 9.8 s a call against 104 and 144 s, and 15 of 15 judge calls answered against 2 of 6. But it gave 5.0 to pictures the other model gave 4.0, and 5.0 to pictures with a white frame. | Kept for the checks, because it answers. Its scores no longer decide alone: see the log. |
| E16 | One sentence in the style block ("the painting fills the whole frame") removes the white paper border that five of the first six pictures came back with. Added on 25 Nov after the first real pictures. | One sentence added to `style.block`, same prompts and seeds | Edges that are bare paper, counted by the border check, on the same six candidates | Bordered candidates went from 5 of 6 to 2 of 6. A thin ragged edge stayed on the picks. | Sentence kept. The frame is now guaranteed by the border check and an edge trim, not by wording. |
| E17 | A judge asked to find what is wrong (yes or no questions, a list of what must be visible) tells pictures apart that the 1 to 5 judge scored the same. A stronger model does it better than the light one: it flags a border on the pictures the border check counts as bordered. Added on 25 Nov after E15. | Two steps, one change each: the question (same model, `gemini-3.5-flash-lite`), then the model (`claude-opus-5-5`, same question) | On the same 12 pictures: how many of the 7 measured borders each judge flags, how many different totals it gives, seconds and list price per call | The question did most of it: the light model went from 0 borders flagged to 8. The stronger model then flagged all 9 pictures that have one, gave nine different totals, and named faults nobody had seen. | The new question is the pipeline's judge, and `models.judge` is `claude-opus-5-5`: about 0.016 USD a picture. |
| E18 | A model that reads Amharic finds the subtitle that does not say what its line says. Expected before the run: it finds at least the tense mismatch in s03, which had been noticed by hand that morning. | Nothing in the film: a new check, each written subtitle against its Amharic line | What it reports for the eight draft lines, against a reading by hand | Found the s03 mismatch, and a second one in s07 that the reading by hand had missed. | The check is part of the script stage. Both lines go back to the author. |
| E19 | The character sheet with three poses is being copied into the scenes: one figure seen from behind as the reference gives one young man per picture, seen from behind. Added on 25 Nov after the first ten pictures with a person in them. This is E05 asked the other way round. | `reference_prompt` of the young man: a sheet of three poses against one back view. Same prompts, same seeds | A model counts, for each of 20 pictures, how often he appears and whether a face is turned to the viewer | More than one copy: 8 of 10 with the sheet, 3 of 10 with the back view. A face to the viewer: 8 of 10 against 1 of 10. | The back view is the reference. The friend gets one of his own. |
| E20 | All lines spoken in one request can be cut into one file per line at the long pauses, so the narration costs one of the day's ten speech requests and not eight. Written into `pipeline/narration.py` before the first take. | One request for eight lines, against the brief's tip of one request per line | The margin between the pauses used as cuts and the pauses left inside lines; how many lines two cutting methods agree on; requests spent | Margin 1.24, where 1.5 is needed. The methods agree on 4 of 8 lines. 5 speech requests in all. | A line is kept from a take only where both methods agree. The rest are spoken alone. See F04. |
| E21 | The listening check scored two correct lines 0.16 because of how it was asked, not because of how they were spoken. Added on 25 Nov after the first eight scores. | The question to the listener: "the script of the language being spoken" against naming the language. Same eight audio files | The match between line and transcript, per line | The two lines rose from 0.16 to 0.91 and 0.81. Another fell from 0.84 to 0.64 with no change in its audio. | The language is named. A score is read as a screen, never as a verdict on the voice. |
| E22 | A short description that names one instrument gets that instrument. The first description asked for a krar, a washint flute and a drone in 42 words, and the listening model heard a music box and a piano in two of the three candidates. Written on 25 Nov at 21:05, while the second job was running on Kaggle and before any of its music had been heard. | `music.caption`: 42 words and three instruments against 27 words and one instrument ("Solo krar ... One instrument only"). Same seeds, tempo, length and model | The instruments a listening model names in each candidate, with the same question as for the first set | Not confirmed. No candidate is heard as a krar, and every candidate of the short description has two instruments. What changed is the family: two of three are now plucked zithers. | Candidate 2 of the short description is in the cut since 25 Nov (`music.chosen`). The coding agent picked it from the listener's descriptions, on my instruction to decide. |
| E23 | A stranger who clones the repository can rebuild the cut with one command, no key, and no call to any model, because every answer a model gave is committed and everything else is cut from those answers by FFmpeg. | Nothing in the film: a fresh clone in an empty folder, no `.env`, no key in the environment, `make setup`, then `python -m pipeline film` | Lines added to `runs.jsonl`; units that were cache hits against units that were rebuilt; the final-cut check | 0 model calls. 42 hits on model outputs, 53 units rebuilt by FFmpeg, in 1 min 49 s. The check passes. | Kept as a step before every release. |
| E24 | The reference picture decides the layout of a shot: every shot drawn with it comes out as one figure standing in the centre. Drawn from the words alone, the scene leads and the figure does what the words say. Written into the schema and the storyboard before the run, after a second review found four of nine shots to be the same composition. | `keyframe.reference`: on against off, for three shots. Same words, same seeds | A model measures, in each of 12 pictures, how much of the height he takes, whether he stands or sits, and whether he is in the middle | With the reference he stands in the middle at half the height or more in 5 of 6 pictures. From the words alone, in 1 of 6, and he sits by the bus window in both pictures of that shot. | The three shots are drawn without the reference. The price: in the bus seat shot his face shows from the side. |
| E25 | The voice did not continue from one line to the next because the eight lines came from three sittings, and that shows as steps in pitch. Recorded in one sitting, with one seed and a short style, the step from line to line comes down. Written down on 25 Nov at 23:45, after my comment on the cut and before the new recording. | How the lines were recorded: three sittings with no seed, against one sitting with `voice.seed` 7 and a style of three words, each line in a request of its own. Three changes at once, and five lines also got new words | The median pitch of each line and the step between neighbouring lines, in semitones (`outputs/experiments/E25/results.json`) | The largest step went from 4.5 to 1.8 semitones. The eight lines lay 7.1 semitones apart and now lie 4.5 apart. | The seed and the short style went into the storyboard (commit `4ed0344`). An hour later the voice itself was replaced: see E26. |
| E26 | No hypothesis was written before the run: see the entry. The question: does a voice of Addis AI, a provider built for Ethiopian languages, say the eight lines as well as the Gemini voice, and do its lines sit as close together in pitch? Added on 26 Nov. | `models.tts` and `voice.name`: three voices of Addis AI against the Gemini voice `Charon`, on the same eight lines | The match of the listening check for each line, where the listener is a model, and the largest step in pitch between neighbouring lines | Mean match 0.78, 0.87 and 0.81 for the three voices, against 0.80 for the Gemini voice, which has one line at 0.16. Largest step 2.2, 1.7 and 1.6 semitones, against 1.8. | `am-nahom` is in the cut, picked from these numbers by the coding agent. |
| E27 | No hypothesis was written in this file before the run: see the entry. Two questions. Does a speech model built for Amharic hear the eight lines better than the text model that had been the listener? And how far off was the pipeline's way of finding where a spoken sentence ends, which the subtitles are timed by? Added on 26 Nov. | The listener (`models.listener`): the text model against Addis AI's speech-to-text, on the same eight audio files. And the way a sentence end is found: letters and measured pauses, against the times of the heard words | The match of what was heard with the script, per line. The distance between the two sentence ends, for 18 ends | Mean match 0.96 against 0.84, lowest line 0.89 against 0.72. The two ways of finding a sentence end are 0.26 s apart on average and 0.53 s at most. | The speech model is the listener, and the subtitles are timed from the words it heard (commit `ac3ac21`). |
| E28 | His clothes and backpack change from shot to shot because the description names no colour. With the colours written into the description, a shot drawn from the words alone holds them. Stated in a written review of the cut at 00:45 on 26 Nov, before any picture was redrawn. | The character description: colours named, against none. Not the only change: every shot with him is now drawn without the reference picture, and three prompts were rewritten | One model names the colour of his jacket, trousers and backpack and what is on his feet, in the picked picture of each shot, before and after | Backpack as described in 7 of 7 shots (before: 0 of 6, in four colours). Plastic sandals in 5 of 5 (before: 1 of 5). Trousers 4 of 5 (before: 2 of 5). Jacket grey or charcoal grey in 5 of 5 (before: 2 of 5, three navy blue). | The description keeps its colours and no shot uses the reference picture (commit `ac3ac21`). |
| E29 | The voice leaves out a short first word when a punctuation mark follows it at once. The same text sent again loses the word again, and the text without the comma keeps it. Written down after the fault was seen (F12) and before the recordings. | The mark after the first word of one line: a comma, a full stop, nothing | A speech model writes down each recording: is the first word there | With a comma or a full stop: missing in three of three recordings. Without: there in three of four. | The line is sent to this voice without that comma. The listening check reports a missing first or last word, and `voice.takes` asks for the line again. |
| E30 | A word that a second, different listener writes as the script has it was said, and the first listener misheard it. A word that neither writes is in doubt, and a further take may say it more clearly. Written down before the second listener ran. | The listener (the text model on the same ten audio files), then the take of three lines | Which words of the script each listener wrote. For each take: the match, and the first and the last word | Of nine words in doubt, three were the listener's mistake and three are heard in a new take. The last line needed its twelfth take to have both its first and its last word. | Take 2 of s00, take 3 of s04 and take 12 of s09 are in the film. |
| E31 | The subtitles of the tall film were placed 330 px above the bottom by a guess. If the platforms publish a safe area, the guess is to be measured against it. Written down before the numbers were read. | `subtitle_margin_v` of the vertical export: 330 against 672 | The published safe areas of YouTube Shorts, Instagram Reels and TikTok for 1080 x 1920, and the place of the subtitle text in three frames | Before: 332 to 411 px above the bottom, inside the area all three ask to keep clear (660 to 672 px). After: 682 to 752 px. The width was inside the side limits before and after. | The margin is 672. |

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

### E31  Where the subtitles sit in the tall film, against what the apps publish as safe  (26 Nov 2026)

Hypothesis: the storyboard put the subtitles of the tall film 330 px above the bottom, and `ARCHITECTURE.md` said that this was "above the area that phone apps cover with buttons". That was a guess: nobody had looked at the film in an app or at a published number. Written down before the numbers were read: if the platforms publish a safe area, the guess is to be measured against it, and the subtitles moved if they fail.

Changed: `subtitle_margin_v` of the vertical export in `storyboard.json`, from 330 to 672.

Held fixed: the film, the subtitle text, the font and its size.

Evidence: the published numbers, read from the platforms' pages by an agent on 26 Nov, for a frame of 1080 x 1920. All three are specifications for ads, the only numbers that were found. And the place of the white subtitle text in three frames of the tall film, measured in pixels before and after the change.

| | Keep clear at the bottom | At the top | Left | Right | Source |
|---|---:|---:|---:|---:|---|
| YouTube Shorts | 672 px | 288 px | 48 px | 192 px | Google, "Universal Video Ad Safe Zones" (`services.google.com/fh/files/helpcenter/ytadsafezones.pdf`), read off its diagram |
| Instagram Reels | 35%, 672 px | 14%, 269 px | 6%, 65 px | 6%, 65 px | Meta Ads Guide: "Consider leaving at least 14% of the top, 35% of the bottom, and 6% on each side of your asset free from text" |
| TikTok | 660 px | 240 px | 120 px | 120 px, and a column of buttons 180 px wide from 840 px down | TikTok's own page gives no numbers. Three other pages agree on these (socialync.io, merginit.com, manypixels.co) |

Result:

| The subtitle text in the tall film | Before | After |
|---|---|---|
| Above the bottom of the frame | 332 to 411 px | 682 to 752 px |
| From left to right, widest line | 203 to 878 px | 203 to 878 px |
| Clear of the bottom area on all three | no | yes |
| Inside the side limits of all three (120 to 888 px) | yes | yes |

Decision: 672. The subtitles of the tall film now stand at about 61 to 65% of its height. The price: in four shots they cross the lower part of the figure (s01, s04, s06, s08). The wide film is not changed.

What it changed: the sentence in `ARCHITECTURE.md` is now a measurement and names its sources. Limits: the film was not looked at on a phone inside the apps. The numbers are for ads, and what an app lays over an ordinary post may be smaller.

### E30  Two listeners, and further takes of three lines  (26 Nov 2026)

Hypothesis: the speech model that checks the film wrote nine words of the ten lines differently from my text, and a review asked whether the voice or the listener was wrong. Written down before the second listener ran: a word that a second, different listener writes as the script has it was said, and the first listener misheard it. A word that neither writes is in doubt, and a further take of its line may say it more clearly.

Changed, part 1: the listener. The text model `gemini-3.5-flash-lite` was asked to write down the same ten audio files.

Changed, part 2: the take, for the three lines with a word that neither listener wrote. Each further take is a new request to the same voice with the same text.

Held fixed: the ten lines and the voice `am-nahom`. In part 1, the audio files.

Evidence: `python experiments/e30_two_listeners.py` (run `20261126T114255Z-6d1836`), answers in `outputs/experiments/E30/results.json`. What the speech model wrote for every take is in `outputs/experiments/E30/takes.json`.

Result, part 1: the text model is the weaker listener. It matches the lines at 0.90 on average, the speech model at 0.99, and it did not write 40 words of the script where the speech model did not write 13. Eight words were written by neither:

| Line | Words that neither listener wrote | Of the nine words in doubt, written by the second listener |
|---|---|---|
| s00 | ርቄ | |
| s01 | ከአንኮበር (both wrote ካንኮበር, which is how it is said) | እንደጨረስኩ, ቦርሳ |
| s04 | ላምበረት, ስደርስ, ጠፋኝ | ተቀበለችኝ |
| s09 | የጉዞው, አትሽሸው, አጣጥመው | |

Result, part 2:

| Line | Takes | Best take, and what the speech model wrote in it |
|---|---|---|
| s00 | 2 | Take 2: every word, match 1.00 |
| s04 | 7 | Take 3: every word but the last letter of ተቀበለችኝ, match 0.99 |
| s09 | 10, takes 3 to 12 | Take 12: the first word ዛሬ and the last word አጣጥመው as written, match 0.99 |

In the ten takes of the last line the first word was missing four times (takes 5, 8, 10 and 11), and the last word was written as I wrote it three times (takes 5, 11 and 12). Only take 12 has both. In every take the listener wrote የጉዞ for የጉዞው and አትሸው for አትሽሸው.

Twelve requests to the text model, two of them refused with HTTP 503 and answered on the next attempt. Sixteen speech requests and sixteen listening requests for the takes, from the sign-up credit.

Decision: the film uses take 2 of s00, take 3 of s04 and take 12 of s09 (`voice.takes` in the storyboard). The lines of the film now match at 0.945 to 1.00, 0.99 on average, and no first or last word is missing.

What it changed: of the nine words, three were the listener's mistake, three are heard in the new takes, and three stay as they were: የጉዞው and አትሽሸው, which this listener writes the same way in every take, and the last letter of ተቀበለችኝ. Limits: both listeners are models. Whether a word is said as an Amharic speaker says it is for a person to hear.

### E29  The first word that the voice did not say  (26 Nov 2026)

Hypothesis: the last line of the narration begins ዛሬ፣ ("Today,") and came back without that word (F12 in `FAILURES.md`). Written down before the three recordings below: the voice leaves out a short first word when a punctuation mark follows it at once. If so, the same text sent again loses the word again, and the text without the comma keeps it.

Changed: the mark after the first word of the line. A comma, as I wrote it. A full stop, which makes the word a sentence of its own. Nothing.

Held fixed: the other words of the line, the voice `am-nahom`, the provider. This voice takes no seed, so no two recordings are the same.

Evidence: run `20261125T235426Z-7dc4e7`, three speech requests and three listening requests. The three recordings and what the speech model heard in each are in `outputs/experiments/E29/`. Each recording was sent to the listener with silence before and after it.

Result:

| Sent to the voice | First words heard | Is ዛሬ there |
|---|---|---|
| ዛሬ፣ ከሰባት ዓመት በኋላ፣ ... (as written, again) | ከሰባት ዓመት በኋላ | no |
| ዛሬ። ከሰባት ዓመት በኋላ፣ ... | ከሰባት ዓመት በኋላ | no |
| ዛሬ ከሰባት ዓመት በኋላ፣ ... | ዛሬ ከሰባት ዓመት | yes |

With the first recording in the pipeline, the word is missing in three of three recordings where a mark follows it. After the change it was sent without the comma three more times in the pipeline: the word is there in the first and the third take and missing in the second. So without the comma it is there in three of four.

Six answers, 11.2 to 11.7 s of audio each, a few cents of the sign-up credit.

Decision: a voice of Addis AI is sent its line without a comma after the first word (`speech_text` in `pipeline/providers.py`). The storyboard, the subtitles and the listening check keep my text as I wrote it. Because one recording in four still lost the word, two more things went in: the listening check reports a first or last word that was not heard, and `voice.takes` asks for a further take of one line. The film uses the third take of this line.

What it changed: the hypothesis holds as far as three recordings can show, and it is not the whole cause. Limits: one line, one voice, seven recordings in all. I do not know why the voice does it, and nobody has heard these recordings but two models.

### E28  The colours written down, and no reference picture  (26 Nov 2026)

Hypothesis: a written review of the cut of 01:13 (commit `531e84a`), done by a second coding session before anything here was run, said: his jacket, trousers, shoes and backpack change from shot to shot, because the three shots drawn without the reference picture (E24) are held only by a description that names no colour. Name the colours once in the description, and the words alone will hold them. The review is kept outside the repository. Its sentence about the cause is repeated here as the hypothesis.

Changed: the description of the young man in `storyboard.json`. Before: "a plain dark jacket over a light shirt, plain trousers and moulded plastic sandals ..., carrying one simple backpack". After: "a charcoal grey jacket over a white shirt, olive green trousers rolled at the ankle, and dark blue moulded plastic sandals with a closed toe and a buckle strap on bare feet. He carries one olive green canvas backpack." The backpack in the room (s07) and on the balcony (s09) is named "olive green canvas" as well.

Not held fixed, and I say so: the reference picture is switched off for the two shots that still had it (s01, s06), and the prompts of three shots were rewritten for other faults (the bus seat, the first shot, the last shot). So this is the cut before against the cut after, not one change alone.

Evidence: the pictures were drawn in runs `20261125T224053Z-057fc1`, `20261125T224945Z-2d707d`, `20261125T225537Z-cad423` and `20261125T225747Z-f466f8` (42 pictures, 41 answers of the judge). I looked at every candidate and pinned one a shot (`keyframe.pick`). The measure is `python experiments/e28_clothes.py`: the same question to `claude-opus-5-5` about the picked picture of each of seven shots, before (the index of commit `531e84a`) and after. Answers in `outputs/experiments/E28/results.json`, counts in `summary.json`, calls under run `20261125T230458Z-5bbddc`.

Result:

| In the picked pictures | Before | After |
|---|---|---|
| Backpack is olive green | 0 of 6 (sage green 3, tan 1, charcoal grey 1, brown 1) | 7 of 7 |
| Plastic sandals on his feet | 1 of 5 (leather sandals 2, closed shoes 2) | 5 of 5 |
| Trousers are olive green | 2 of 5 (cream 1, grey 1, sage green 1) | 4 of 5 (sage green 1) |
| Jacket is charcoal grey | 2 of 5 (navy blue 3) | 2 of 5 (grey 3) |
| Jacket is grey or charcoal grey | 2 of 5 | 5 of 5 |

Before, the backpack could not be seen in the bus seat picture. Now it is on the seat beside him. The man on the balcony (s09) is seven years older and dressed differently on purpose: only his backpack is counted there.

Two things went wrong on the way, both with the reference picture. With the new description the reference came out as it should (grey jacket, olive trousers, blue sandals, olive backpack). Then:

- The first shot (s01), drawn with it, showed him in front of a thatched hut in all four candidates. The bus that the words ask for was in none (judge totals 2.7, 2.7, 0.6, 2.35). From the words alone all four have the bus (3.0, 2.5, 2.5, 3.1).
- The brokers shot (s06) is given two reference pictures, his and his friend's. None of its three candidates shows the scene: one is a single figure on blank paper in a white shirt and jeans, one a figure in a green hooded top, one a figure in a white shirt among grey outlines (judge totals 0.9, -1.85, 1.5). From the words alone all four candidates show two young men from behind among the brokers at the bus station (2.8 each).

Fourteen answers in 2.4 to 7.1 s, 0.18 USD. The redraw itself: 42 pictures and 41 judge answers, 0.93 USD for the judge.

Decision: the description keeps its colours. No shot is given the reference picture (`"reference": false` on s01, s03, s04, s06 and s08). The reference picture of each character is still drawn first, because it is the quickest way to see what a description gives.

What it changed: the brief's tip is to draw a character sheet first and give it to every keyframe. E19 found the right sheet, E24 showed that it fixes the layout as well as the person, and here it broke two shots outright. What held him together in the end is thirty words of description. Limits: the measure is one model's reading of small pictures, "grey" and "charcoal grey" are neighbours on its list, and it says nothing about his build or his hair. The judge still scores three of the picked pictures under 3 (s03 2.6, s05 1.6, s06 2.8): I picked them by eye, and the final-cut check lists them.

### E27  A listener built for Amharic, and where a sentence ends  (26 Nov 2026)

Hypothesis: none was written in this file before the run, and I say so. Two things led to it. The listening check had given 0.16 three times to a line that its listener, a general text model, wrote down in Latin letters (E21, E26). And a review of the cut found the first subtitle holding four sentences for the whole line, and the brokers' subtitles changing at the wrong moments. Addis AI, whose voice now speaks the lines, also has a speech-to-text model for Amharic that returns the time of each word. A first try on two lines (run `20261125T224350Z-965c72`) came back nearly word for word, with times. The change went into the code after that, and the measure over all eight lines after the change.

Changed, part 1: the listener. `gemini-3.5-flash-lite`, given the audio and asked to write it down, against Addis AI's speech-to-text (`models.listener: addis-scribe`).

Changed, part 2: how the end of a spoken sentence is found. Before: the speaking time is shared out by the number of letters in each sentence, and an end moves to a measured pause that is near. After: the words of the script are matched in order to the words the speech model heard, and a sentence ends where its last word ends.

Held fixed: the eight audio files of the cut (voice `am-nahom`, the same files for both listeners) and the script. Both listeners are scored in the same way, with Ethiopic letters that are written differently and said the same counted as one (ሰ and ሠ, ሀ and ሐ, አ and ዐ, ጸ and ፀ).

Evidence: `python experiments/e27_subtitle_timing.py` reads what each listener heard (the index of commit `531e84a` for the text model, the index as it is now for the speech model) and calls no model. Numbers in `outputs/experiments/E27/results.json`. The speech model's eight answers are run `20261125T225947Z-bf79b2`.

Result, the listening check:

| Line | Text model | Speech model |
|---|---:|---:|
| s01 | 0.75 | 0.98 |
| s02 | 0.93 | 0.96 |
| s03 | 0.72 | 0.98 |
| s04 | 0.87 | 0.98 |
| s06 | 0.91 | 0.95 |
| s07 | 0.83 | 0.99 |
| s08 | 0.78 | 0.89 |
| s09 | 0.92 | 0.95 |
| Mean | 0.84 | 0.96 |

The first line shows the difference. The text model wrote "እስከ መጋቢት 12 በኩልቀን ላይ ካንኮበር ተነሳው ...", which begins "until Megabit 12". The speech model wrote "መስከረም ሁለት ሺህ አስራ ሁለት እኩለ ቀን ላይ ካንኮበር ተነሣሁ ...", which is the line, with two spellings of the same sounds.

Result, the sentence ends: the eight lines have 26 sentences, so 18 ends inside a line. The two ways are 0.26 s apart on average and 0.53 s at most. The largest is the first sentence of the brokers' line: the letters put its end at 2.72 s, and the last word of that sentence ends at 3.25 s. In the same line one of the two measured pauses lies inside the last sentence ("in the end", then a breath, "we picked one"), so a rule that moves a change of subtitle to the nearest pause moves it into the middle of a sentence. That is what the review saw.

Ten answers in 1.7 to 5.0 s. Each answer reports its own price: 3.5 ETB for 1,000 characters written down, about 0.01 USD for all ten, taken from the sign-up credit.

Decision: `models.listener` is `addis-scribe`. A subtitle is shown sentence by sentence, each while its sentence is spoken, by the heard words. Short sentences share a cue until it has been up for 1.5 s. The film has 23 cues where it had 13, and no cue is one left-over word. Without a speech model as listener the letters and the pauses are still used.

Later that night the narration was replaced by ten lines that I wrote myself. On an early recording of them the speech model wrote ተከ for the last word of a line, ተከተልን. With 0.6 s of silence put before the audio and 0.8 s after, it wrote the word in full (run `20261125T235334Z-429c80`): the listener lost a last word when the audio ended at once. The check now sends every line with that silence. On the ten lines of the film it matches each line at 0.945 to 1.00, 0.99 on average (`outputs/narration/index.am.json`), and the film has 19 cues.

What it changed: the listening check no longer raises a false alarm on a line because of the script its listener chose to write in. Limits: the listener and the voice now come from one provider, and a model that hears its own provider's voice well may hear another voice less well. The match is still a model's. Whether each word is said as an Amharic speaker says it is for a person to hear, and that is me.

### E26  Three voices of Addis AI against the Gemini voice  (26 Nov 2026)

Hypothesis: none was written down before this run. I say so because every other entry has one. I had proposed Addis AI, a speech provider built for Ethiopian languages, after the voice kept changing from line to line (F10 in `FAILURES.md`). The message of commit `4a86d88` says what the new provider was for: "it is there to be compared by ear with the Gemini voice". The numbers below answer two smaller questions. Does the listening check understand these voices as well as the Gemini voice? Do their lines sit as close together in pitch?

Changed: the speech model and the voice (`models.tts`, `voice.name`). Addis Voices 2 with three of its voices, `am-yohanes-calm`, `am-nahom` and `am-dawit`, against `gemini-3.8-flash-tts` with `Charon` as recorded for E25.

Held fixed: the eight lines, word for word, each in a request of its own. The listener (`gemini-3.5-flash-lite`, with the question that names Amharic) and the pitch measure of E25. Not the same on both sides: the Gemini requests carried a seed and a style, and the Addis AI API takes neither.

Evidence: `runs.jsonl`, provider `addis`: runs `20261125T220304Z-b4be2b` (`am-yohanes-calm`), `20261125T220531Z-bff449` (`am-nahom`) and `20261125T220736Z-d20818` (`am-dawit`), eight requests each. The audio of every line and what the listener wrote for it are in `outputs/narration/`. The numbers are in `outputs/voices/results.json` and `outputs/voices/summary.json`, beside a radio cut for each voice. That folder is on my machine and is git-ignored. For the Gemini voice the pitch is that of E25, and the listening check is in `outputs/narration/index.am.json` as commit `4ed0344` has it.

Result:

| | `Charon` (Gemini) | `am-yohanes-calm` | `am-nahom` | `am-dawit` |
|---|---:|---:|---:|---:|
| Listening check, mean match over the eight lines | 0.80 | 0.78 | 0.87 | 0.81 |
| Listening check, lowest line | 0.16 (s04) | 0.61 (s02) | 0.71 (s07) | 0.69 (s08) |
| Lines under the floor of 0.6 | 1 | 0 | 0 | 0 |
| Largest step in pitch between neighbouring lines | 1.8 semitones | 2.2 | 1.7 | 1.6 |
| Speech in the eight lines, as spoken | 66.7 s | 55.8 s | 50.7 s | 50.1 s |

The Gemini line under the floor is s04. The listener wrote it in Latin letters ("Lambaret, hederesko, kemeche ..."), which is the fault of E21 again, although the question now names the language. Without that line the Gemini mean is 0.89. So by the listening check the Gemini voice and `am-nahom` are level, and the other two are a little lower.

By the largest step in pitch the order is `am-dawit` (1.6), `am-nahom` (1.7), the Gemini voice (1.8), `am-yohanes-calm` (2.2). The first three are 0.2 semitones apart. The voices of Addis AI speak faster: 50 to 56 s for the eight lines, against 67 s.

Two limits of these numbers. The listener is a model. It has now given 0.16 three times to a line that it wrote down in Latin letters, and it is no Amharic ear. And the pitch is one property of a voice: the pace and the tone are not in it. The numbers can screen out a voice that garbles the words. They do not say which voice sounds right.

The lines in the cut are not the lines in this table. They are a second recording of `am-nahom` (run `20261125T221023Z-84565e`). The style text in the storyboard was changed to "not used by this voice". The style is part of a line's fingerprint in the cache, so all eight lines were asked for again, although this API is sent no style. The numbers of `am-nahom` above are from the first recording. The second one scores 0.84 on average in the listening check, with its lowest line at 0.72 (`outputs/narration/index.am.json`). Its pitch has not been measured.

The 32 requests gave 206.7 s of audio in 6.1 to 11.0 s a request: 0.11 USD at the list price of 0.000533 USD a second, taken from the sign-up credit of 3.17 USD (`pricing.json`).

Decision: `models.tts` is `addis-voices-2` and `voice.name` is `am-nahom` (commit `531e84a`). The coding agent picked it from this table. The commit message calls it the steadiest of the three. By the listening check it is the best of the three. By the largest step in pitch `am-dawit` is steadier, by 0.1 semitones. The Gemini recording stays in the cache as the other choice.

What it changed: the narration no longer hangs on a limit of ten requests a day (F09), and a line is one request with nothing to cut. What it did not change: no number here replaces listening. And an entry without a hypothesis can only describe what was found. It cannot confirm anything.

### E25  One sitting and one seed, against lines from three sittings  (26 Nov 2026)

Hypothesis: I heard the cut of 25 Nov, 23:20, and wrote that the voice does not continue from one line to the next (F10 in `FAILURES.md`). The eight lines of that cut came from three sittings, and no request carried a seed. So the lines differ in pitch, and that can be measured. Recorded again in one sitting, with one seed and a short style, the step in pitch from one line to the next comes down. The plan and the measure were written down at 23:45 on 25 Nov, before the new recording, in my working notes, which are not in the repository.

Changed: how the eight lines were recorded. Before: a take at 16:43 UTC and single requests at 17:13 and at 20:15, no seed, the style "calm, warm and unhurried, like telling a memory to family". After: every line in a request of its own between 21:10 and 21:16 UTC, `voice.seed` 7, the style "calm, warm storyteller". That is three changes at once: the sitting, the seed and the style. Five lines also got new words in the same recording (s01, s02, s03, s07 and s09). So the result says what the three did together. It does not say which of them did it.

Held fixed: the model (`gemini-3.8-flash-tts`), the voice (`Charon`) and the measure.

Evidence: `outputs/experiments/E25/results.json`. The measure is the median pitch of each line as spoken, in Hz: autocorrelation on frames of 40 ms at 8 kHz, voiced frames only. The script that computed it is not in the repository. The recordings are in `runs.jsonl`: runs `20261125T164336Z-2fb093`, `20261125T171237Z-6f6e51` and `20261125T201514Z-906fdc` before, runs `20261125T210610Z-743eb1` and `20261125T211402Z-9d7c8e` after.

Result:

| Line | Before: median pitch | Step from the line before | After: median pitch | Step from the line before |
|---|---:|---:|---:|---:|
| s01 | 90.9 Hz | | 105.3 Hz | |
| s02 | 117.6 Hz | +4.5 semitones | 115.9 Hz | +1.7 semitones |
| s03 | 98.8 Hz | -3.0 | 108.8 Hz | -1.1 |
| s04 | 98.8 Hz | 0.0 | 108.8 Hz | 0.0 |
| s06 | 115.9 Hz | +2.8 | 117.6 Hz | +1.3 |
| s07 | 136.8 Hz | +2.9 | 127.0 Hz | +1.3 |
| s08 | 115.9 Hz | -2.9 | 136.8 Hz | +1.3 |
| s09 | 114.3 Hz | -0.2 | 123.1 Hz | -1.8 |
| Largest step | | 4.5 | | 1.8 |
| Lowest line to highest line (span) | | 7.1 | | 4.5 |

For the step the hypothesis holds. Before, five of the seven steps were 2.8 semitones or more. After, none is over 1.8. The step I had heard, from s04 to s06, went from 2.8 to 1.3.

For the voice as a whole it holds only in part. With one seed the pitch still drifts upward, from 105.3 Hz at s01 to 136.8 Hz at s08. A seed did not give one fixed voice. And the measure is pitch only: the pace and the tone are not in it.

A first try in the same sitting, one take for all eight lines, could not be cut and is not in these numbers (F10).

Decision: `voice.seed` 7 and `voice.style` "calm, warm storyteller" went into the storyboard with commit `4ed0344`. One request per line (`voice.one_take` false) was there already, since commit `9935183`. The seed and the style held for about one hour. Then the voice was replaced by one of another provider, which takes no seed and no style (E26).

What it changed: until this measure "the voice is different" was something I heard and could not point at. A pitch for each line makes it a table, and the table can be made before a listener has to say it. It also shows the price of E20: saving speech requests with a take and single re-takes is what put three sittings into one film.

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

Decision: candidate 2 of the short description is in the cut since the evening of 25 Nov (`music.chosen` 2, commit `9935183`). The coding agent picked it from the listener's descriptions, on my instruction to decide: a plucked string instrument and bells, slow, with no busy moment, where candidate 1 brings in a flute and candidate 3 percussion (`music.chosen_reason` in the storyboard). If none sounds right, the next change is the model's own vocabulary: ask for "lyre" or "harp" with no country in the description.

What it changed: I expected the music model to follow a named instrument the way an image model follows a named object. It does not know this one. A description steers the mood, the tempo and the family of the sound, and the rest has to be chosen by listening.

### E08  Wan 2.2 on a free T4  (25 Nov 2026)

Hypothesis: Wan 2.2 TI2V-5B fits a 16 GB T4 at an area of 480 x 832 with 81 frames, and not at 720p. The model card asks for a 24 GB GPU.

Changed: nothing against the plan. The first run used the small settings from the storyboard: `max_area` 399,360, 81 frames, 30 steps, guidance 5.0, with the transformer in float16.

Held fixed: the keyframe of shot s02, its motion prompt and seed 202.

Evidence: `outputs/shots/s02_wan__a5009af75983891d.mp4`. `runs.jsonl`, provider `kaggle`, unit `s02_wan`, run `20261125T184325Z-5d49c1`. The numbers are the job's own, from its `results.json`.

Result:

| | |
|---|---:|
| Clip | 608 x 608, 81 frames, 3.4 s at 24 fps |
| Peak GPU memory | 13.45 GB |
| Time for the clip | 820.7 s |
| Time to load the model | 248.1 s |
| GPU minutes logged, with both T4s of the session counted | 27.4 |
| List price of that time on rented T4s | 0.16 USD |
| Blank or not-a-number frames in float16 | none |

The clip is what the prompt asked for: the bus comes down the road and its dust grows behind it. The painted look of the keyframe holds over all 81 frames.

Three limits showed. A T4 gives about 15 GB, so 1.6 GB are left and 720p was not tried: it has two and a half times the pixels. The second clip of the same job never ran (F07 in `FAILURES.md`). And the clip is small: the vertical film enlarges it 3.2 times, where a pan over the still is enlarged 1.9 times. Side by side at full size the moving shot is clearly softer than the shots around it.

A second clip, made an hour later with the same settings, shows a fourth limit. Shot s05 is a painting of blurred city lights with nothing else in it, and its prompt asked for the lights to streak past a window. The clip ran without a fault (890.4 s, the same 13.45 GB, run `20261125T190635Z-9cb56a`), and it is not usable: after the first frame the model paints things into the blur that were never there, wet surfaces and photographic glare, and painted lights go out and come back. With nothing in the picture to move, it invented something. This is read from five frames of `outputs/shots/s05_wan__311b7a4f6fccfd01.mp4` by the coding agent.

Two more clips were made in the night, for the shots that had been left as pans without trying: the traffic at Lamberet (s04) and the man on the balcony (s09). Both ran without a fault. Neither is used. In the Lamberet clip the minibuses lose their shape from frame to frame and a car swells to fill a third of the picture. In the balcony clip the man and the city hold still, and marks that were not painted spread over his shirt and the backpack. Read from five frames of each clip by the coding agent (`outputs/shots/s04_wan__5da9f760d846e94e.mp4`, `outputs/shots/s09_wan__e3ac1eb447610abb.mp4`).

Decision: the settings stay. The road shot (s02) keeps its clip: it plays slowed to 4.2 s and the rest of the shot is a slow push over its last frame. That was 2.8 s while the shot lasted 7 s, and 1.8 s when the shot was cut to 6 s. Since 26 Nov the shot allows its clip to run slower with blended frames (`motion.slow_max`), and the clip fills the shot. The other three shots that were tried (s04, s05, s09) stay as pans over their stills. Of four clips, one is in the film. Whether a softer moving shot is better than a sharp pan is not mine to decide by looking at stills: it is the blind pair in the second user test (E10).

What it changed: the question was whether it would run at all on a free GPU. It does, at 14 minutes a clip. The price is not memory or time. It is sharpness, which the plan had not listed, and it is that the model needs something in the picture that can move.

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

### E24  The reference picture decides the layout  (25 Nov 2026)

Hypothesis: a second review of the rough cut found that four of the nine shots were one composition: the young man standing, seen from behind, full length, in the centre. The storyboard calls them medium, pov, wide and wide. F05 had already said why: a reference picture pulls a shot toward its own layout. So a shot drawn from its words alone, with no reference, should let the scene lead, and the figure should do what the words say.

Changed: `keyframe.reference`, off against on, for three shots: the bus seat (s03), Lamberet (s04) and the queue (s08).

Held fixed: the three prompts, rewritten once for both sets so that the scene comes first and the figure is small or cut off by the frame. The seeds, two candidates a shot, the model, the style block and the description of the young man.

Evidence: twelve pictures in `outputs/keyframes/original/`, drawn in runs `20261125T200529Z-396d4a` (words alone) and `20261125T200809Z-d647b6` (with the reference). The measure is `python experiments/e24_reference_layout.py`: the same questions to `claude-opus-5-5` about each picture. Answers in `outputs/experiments/E24/results.json`, calls under run `20261125T201545Z-8b3ebf`.

Result:

| | Words alone | With the reference |
|---|---:|---:|
| Pictures | 6 | 6 |
| He stands in the middle and takes half of the height or more | 1 | 5 |
| Share of the picture's height he takes, on average | 0.54 | 0.64 |
| He sits, in the two pictures of the bus seat | 2 of 2 | 0 of 2 |
| His face can be seen, from the side | 2 | 2 |
| Mean total from the pipeline's judge | 2.6 | 1.5 |
| Pictures with writing in them, by the judge | 1 | 3 |

With the reference the bus seat shot shows him standing in the aisle at 0.83 and 0.85 of the height, although the words say he sits on the window seat. From the words alone he sits by the window in both pictures. At Lamberet the best picture of each set is close (judge totals 3.4 and 3.65), but with the reference he fills 0.65 of the height and the street is behind him, and from the words alone he is half the height and the avenue is the picture.

The price shows in the same table. Seated and turned to the window, his face is seen from the side in both pictures of the bus seat. And without a reference his clothes are held only by the description: the trousers come out lighter than in the shots drawn with it.

Twelve answers in 3.5 to 6.9 s, 0.12 USD.

Decision: the bus seat, Lamberet and the queue are drawn without the reference (`"reference": false` in the storyboard). The shots where he stands close to us, Ankober and the brokers, keep it. For the queue the second candidate is picked by hand, because it has him in the line and the judge scored both 2.8. A day later the last two shots lost the reference as well, and all the pictures of this entry were replaced: see E28.

What it changed: E19 found the right reference and F05 saw its pull, and I had kept the reference on every shot with him in it, as the brief's tip says. It should be on only where the shot is about him. Where the shot is about a place, the place has to be drawn first.

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

Repeated on 26 Nov at 02:40, on commit `a877371`: ten shots, the narration I wrote that night, the generated score and the one generated clip. A clone with no key and no `.env` built both films. `runs.jsonl` had 745 lines before and after, and each film has the same SHA-256 as the one built on my machine. One difference from the first run: the clone was run with the Python environment of the working folder, not with a fresh `make setup`. Repeated again at 03:14 on commit `e0f3817`, with the final narration: both films were built with no key, the run log had 850 lines before and after, and each film has the same SHA-256 as the one on my machine. And on the release commit `3fd45b4` at 15:08: the two committed films were deleted in the clone, the strict build rebuilt them in 115 seconds with no key, the run log stayed at 901 lines, and each rebuilt film has the same SHA-256 as the committed one.

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
