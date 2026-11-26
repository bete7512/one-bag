# Failures

What broke, what was tried, what fixed it. An entry is added the moment something breaks, while the error text is still on the screen. F08 to F10 are the exception: the coding agent wrote them on 26 Nov, some hours after they happened, from the commits, the run log and the kept files. F11 and F12 were written by the coding agent within the hour.

## From real runs

### F01  The text model answered "high demand" and the keyframe stage stopped  (25 Nov 2026)

Stage and model: keyframes, the picture judge. `gemini-3.8-flash` on the free tier of the Gemini API.

What happened: the six pictures for the three shots without people were made in 6 to 9 seconds each. The judge then scored two of them, slowly: 104 s and 144 s per call. The third judge call failed four times in two and a half minutes with

```
HTTP 503 {"error": {"code": 503, "message": "This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.", "status": "UNAVAILABLE"}}
```

and the stage stopped with `gemini call for s05_c1_judge failed`. The four attempts are in `runs.jsonl` under run `20261125T104632Z-cf26db`. The same model had already been slow in the smoke test half an hour earlier: 138 s and 42 s for a one-word answer.

What it showed: a busy provider, and two weaknesses of the pipeline.

1. The waits between attempts were 2, 4 and 8 seconds. That is far too short for an overloaded model, and one attempt alone hung for 127 s before it failed.
2. A failed judge call stopped the whole stage, although the judge only measures. The six pictures were already in the cache, and a person makes the final pick anyway.

What was tried, in order:

1. The same stage again, after two changes to the pipeline: waits of 10, 30 and 90 seconds between attempts, and the judge made optional so a failed score no longer stops the stage. The run finished this time, without the scores: 16 more attempts in twenty minutes, none answered (run `20261125T105827Z-7dbbde`). Twelve were HTTP 503 again and two ran into the five-minute timeout with no answer at all. The last two failed differently: `HTTP 429 You exceeded your current quota`.
2. The limits page of the project in Google AI Studio. It showed what the documentation does not: 20 requests a day for this model on the free tier, and the day's count at 22.
3. The lighter model, as experiment E15 in `EXPERIMENTS.md`.

What fixed it: `models.text` is now `gemini-3.5-flash-lite`, with 500 requests a day and 15 a minute. The same six judge calls took 2 to 6 seconds each. Three things stay in the pipeline whatever the model: the longer waits, checks that cannot stop a run, and a guard that reads the day's use from `runs.jsonl` and refuses a request over the limit before it is sent (`keep_within_free_tier` in `pipeline/core.py`, limits in `pricing.json`).

What it cost: 825 seconds inside failed attempts, about 35 minutes of wall time for two scores, and that model's allowance for the day.

What would be done differently: read the limits page in the provider's console before the first run. The free limits were not in the documentation, and a model with 20 requests a day should never have been given 20 judge calls per pass.

### F02  The first Kaggle run had no internet  (25 Nov 2026)

Stage and model: music, ACE-Step 1.5, as a script on Kaggle pushed from the command line (`python -m pipeline kaggle run music`).

What happened: the upload and the push worked, and the launcher found the job. Thirty-four seconds in, the first network step failed:

```
Cloning into '/kaggle/temp/ACE-Step-1.5'...
fatal: unable to access 'https://github.com/ACE-Step/ACE-Step-1.5.git/': Could not resolve host: github.com
```

What was checked: the settings Kaggle stored for that run, read back with `kaggle kernels pull -m`, say `"enable_internet": true`, `"enable_gpu": true` and `"machine_shape": "NvidiaTeslaT4"`. So the request for internet was sent and stored, and the session still had none.

What was tried, in order:

1. The phone number of the Kaggle account was verified, and the same job pushed again. That run never started: it stayed "queued" for 35 minutes, where the first one had started within a minute.
2. The job was pushed a third time. Queued for 2 seconds, running after 33, complete after 229: three score candidates of 80 seconds each, made in 9.2, 6.5 and 6.6 seconds on two T4s, with 6.4 GB of GPU memory at the peak. The model took 61.7 seconds to load.

What fixed it: the verified phone number. With it the session had internet, and the job script, which had been rewritten that afternoon from the upstream documentation, ran without a change. Why the second push never left the queue is not known: nothing in its status or its log said.

What it cost: an hour of wall time, most of it waiting on the queued run, and no GPU quota to speak of.

What would be done differently: verify the phone before the first push, and stop waiting on a queued run after five minutes instead of thirty-five.

What the run did prove: Kaggle's Python is 3.13 (the job script builds ACE-Step's own environment for that reason), and a dataset is mounted at `/kaggle/input/datasets/<owner>/<name>/`, not at `/kaggle/input/<name>/`. The job scripts search for their manifest instead of assuming a path, so this cost nothing.

### F03  The Claude API key had no credit  (25 Nov 2026)

Stage and model: experiment E17, the keyframe judge on `claude-opus-5-5`, through the Anthropic SDK.

What happened: each of the 12 calls was refused at once:

```
HTTP 400 {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.'}}
```

The key itself was accepted: the refusal is about billing, not about who is calling. The 12 attempts are in `runs.jsonl` under run `20261125T120616Z-8a8230`, each with `cost_usd` 0. A rejected request is not retried, so nothing was spent on waiting either.

What was done that afternoon: nothing was changed to get around it. At that hour the comparison of the two judge models stayed unmeasured, and E17 said so. The first step of that experiment, the new question on the free model, did run. `models.judge` in the storyboard stayed unset, so the judge was the free model until the key worked (see the end of this entry).

Two more attempts the same afternoon, one tiny call each:

1. A new key from the organisation that shows a monthly credit. It was refused for another reason: `This API key is not scoped to a workspace, so this request must include the anthropic-workspace-id header`. The pipeline now sends that header when `ANTHROPIC_WORKSPACE_ID` is set.
2. A third key, scoped to a workspace. The first error came back: `Your credit balance is too low`. So the key and its workspace are accepted, and the credit that the Console shows for the organisation cannot be spent by this key today.

What fixed it: nothing in the repository. Two hours later the organisation's monthly credit showed as available and a key made inside that organisation worked: one test call answered in 4 seconds. The missing step of E17 then ran with `python experiments/e17_judges.py`, which skipped every answer it already had.

What it cost: three refused attempts and about an hour of the author's time in the provider's console. No money: a refused call is not charged.

What would be done differently: before writing code against a paid provider, make one tiny call with the key that will be used. The message of a billing error does not say which organisation the key belongs to, and that was the whole problem.

### F04  The narration take could not be cut into its lines  (25 Nov 2026)

Stage and model: narration. The speech is `gemini-3.8-flash-tts`, the listener is `gemini-3.5-flash-lite`, both on the free tier.

What happened: all eight lines were spoken in one request, each line followed by the pause tag from the speech docs, `<long pause>`. The answer was one audio of 70.19 s (run `20261125T164336Z-2fb093`). The stage cuts such a take at its seven longest pauses, and refused:

```
take__9d84fd84f741392d_1.wav: the pauses between lines are only 1.24 times longer than the pauses inside them, so the cuts would be a guess. Nothing was cached.
```

The take has 36 pauses of a quarter of a second or more. The seven longest run from 1.42 to 1.90 s, the next is 1.15 s. The voice tells the story slowly and stops inside a line almost as long as between two lines.

What was tried, in order:

1. Cut by the words instead of the pauses: send the 35 phrases between the pauses to the listener in one request, have each transcribed, and match the phrases to the script. The request was refused four times with `HTTP 503 This model is currently experiencing high demand` (run `20261125T164633Z-142520`).
2. The same with a label before each clip. Four more refusals (run `20261125T165246Z-a8e679`).
3. Twelve clips in a request. Four more (run `20261125T165821Z-478b29`). That made twelve refusals in a quarter of an hour. A probe then showed the listener was not down: a request with text only answered in 1.4 s and a request with one clip in 5.1 s (run `20261125T165727Z-760672`).
4. One phrase per request. 35 of 36 attempts answered, in 1.5 to 53 s each, four minutes in all (run `20261125T170143Z-902d5d`).

What the transcripts showed: the pauses were not the only problem. Phrase 23 is 0.65 s long and stands alone between two pauses of 1.4 s, after the last word of line s06. The listener was told it is Amharic and still wrote two English words for it: `long pause`. Phrase 28, after the last word of s07, came back as `ሎንግ`, the sound of "long" in Ethiopic letters. The speech model had read the pause tag aloud after some lines, and stayed silent for it after others. This is the listener's word and not yet a person's ear: the take is kept in `outputs/narration/takes/`, and the place is at 45.9 s.

No way of cutting can be trusted on a take like that. The short phrases at the edges of a line are exactly the ones the listener hears worst: it wrote `ምን` for what is probably `ጠዋት`, and `ቁጥር` for the last word of the film, `ኑረው`. A rule that drops what does not match the script would drop real words.

What fixed it: a stricter rule, and four more speech requests. A line is now kept from a take only where two methods agree on both of its ends: the cut at the longest pauses, and the phrases matched to the script (`take` in `pipeline/narration.py`). They agree on s01, s02, s03 and s04, which sit between the four cleanest pauses. They disagree on s06 to s09, so those were not cut at all. Each was spoken again in a request of its own (run `20261125T171237Z-6f6e51`), which is the way the brief suggests in the first place.

One more fault showed up at the end. The listening check gave two correct lines a score of 0.16, because the listener had written them in Latin letters ("Lambara cders ..."). The question now names the language, and the same two files score 0.91 and 0.81 (E21 in `EXPERIMENTS.md`).

What it cost: half an hour from the take to the radio cut. 50 requests to the free listener, 13 of them refused. Five speech requests for eight lines, where one was planned and eight would have been safe. Six of the day's ten are used.

What would be done differently: speak two lines in one request first and listen to the result before building a stage on it. And an old lesson again: F01 ended with "a check that cannot reach its model never stops a run", and here the cut itself hung on that same busy model. The rule that came out of it does not: when the listener cannot be reached or does not agree, the line costs one speech request and nothing waits.

### F05  Two people from behind in a crowd: sixteen pictures, none usable  (25 Nov 2026)

Stage and model: keyframes. FLUX.2 klein 4B on Cloudflare Workers AI, with a reference picture for each character. The judge is `claude-opus-5-5`.

What happened: two shots asked for the young man and his friend, both seen from behind, inside a busy scene: Lamberet at night (s04) and the ticket queue (s08). They were drawn in four runs, two candidates each. Of the sixteen pictures none could go into the film. The judge's totals run from -2.0 to 1.15, and the pipeline asks a person to look at any picture under 3. In its own words:

| Run | What had changed | Lamberet (s04) | The queue (s08) |
|---|---|---|---|
| `20261125T165037Z-d7d28c` | first try, with the three-pose sheet | "The two figures are fused into one body: a taller head and shoulders rise directly out of the shorter man's back" | "Reads as an East Asian train or subway concourse" |
| `20261125T170301Z-fdd723` | one back view as the reference (E19) | "The two men are near-identical clones: same height, same dark jacket, same backpack and same stance." | "The crowd and station design read as East Asian rather than Addis Ababa" |
| `20261125T171336Z-c89c90` | a reference for the friend too, Ethiopian detail in every prompt | "Low suburban houses with white fences, wooden utility poles and an American-style residential street" with one figure in it | "No setting at all: a single figure stands against a blank parchment background" |
| `20261125T172210Z-b760af` | the two named first and put in the foreground | "The two characters are merged into a single figure" | "A single young woman in a white head shawl stands facing the viewer" |

Two faults are tangled together here. The model does not know what Addis Ababa looks like and falls back on the cities it has seen most. And each reference picture pulls toward its own layout: one figure, centred, on an empty ground. With two references and a crowded scene, the references won and the scene was dropped.

In the same hour a third fault showed in the shot of blurred city lights (s05), which has nobody in it. The style block asks for "the subject in the centre of the frame", so the model put one there: a faceless figure in a shirt in one candidate, a portrait of a girl in the other (run `20261125T172210Z-b760af`). Saying in the prompt that the lights themselves are the subject removed it.

What fixed it: the design changed, the prompt did not get cleverer. Where the model is given one person from behind, it holds: the brokers' shot (s06), where the two stand still in the centre like their references, reached 3.3 in its fourth run, once the brokers were asked for as silhouettes. So Lamberet and the queue were rewritten with the young man alone in the frame, and the voice says his friend was there. Run `20261125T172744Z-c6d56e`: Lamberet scored 4.05 on that first try, the queue 2.55, and he wears the same jacket, backpack and sandals as in Ankober.

The change also answers a question that was open at the same moment. His friend had agreed to be shown in one scene, and the storyboard had grown to three. Now it is one again (`ETHICS.md`).

What it cost: 16 of the 81 pictures made up to that hour, 0.34 USD of judge calls, and thirty-five minutes.

What would be done differently: draw the hardest shot first, before writing eight more around it. And keep to the limit of three attempts: the fourth run on these two shots said nothing the third had not.

### F06  Kaggle made the first three scores a second time  (25 Nov 2026)

Stage and tool: music, sent to Kaggle with `python -m pipeline kaggle run music`.

What happened: the description of the score was changed in the storyboard at 20:22 for experiment E22, and the job was sent with that one command. Three things then went wrong, in this order.

1. The run sat in Kaggle's queue for 39 minutes. The afternoon's run had started within a minute.
2. After a quarter of an hour I pushed it again, as F02 had taught. Kaggle refused, and the pipeline did not notice. The tool printed `Kernel push error: Maximum batch GPU session count of 2 reached.`, exited with 0, and the next line on the screen was `running on Kaggle`.
3. When the run did start and finish, its results could not be taken in:

```
error: the output on Kaggle belongs to an older job (2026-11-25T11:41:28Z), not this one (2026-11-25T17:31:31Z). Is the run still going?
```

The cause was the first step, not the queue. `kaggle run` sent the job folder as it lay on disk. That folder had been written in the afternoon, with the first description: only a run of the music stage writes the job, and no stage had run since the storyboard changed. Kaggle spent its 39 minutes of queue and seven of GPU session on the three candidates that already existed.

What saved the film: the stamp that travels with every job. The results came back with the afternoon's stamp, the job on disk had a new one, and the ingest refused them. Without that check the old music would have entered the cache under the new description, and E22 would have compared a description with itself.

What fixed it: `kaggle run` now has the stage write the job from the storyboard as it is, before anything is uploaded, and stops with "nothing in the music stage is waiting for a GPU" when the cache is full (`refresh_job` in `pipeline/kagglerun.py`). A push that Kaggle refuses stops the command with Kaggle's own words. Both have a test. The right job was pushed at 21:13 and was complete at 21:17.

What it cost: 55 minutes from the first push to the right result, where the work itself takes four.

What would be done differently: a command that sends work should build what it sends. It should not trust what an earlier command left on disk.

### F07  The second Wan clip was killed  (25 Nov 2026)

Stage and model: shots. Wan 2.2 TI2V-5B through Diffusers on Kaggle, two T4s, a job of two clips (s02 and s05).

What happened: the first clip was made. The log then ends:

```
[1/2] s02_wan: ok in 820.7s, peak 13.45 GB
Killed
```

Kaggle reported the run as an error. `Killed` with no Python error is the system ending a process that has used up the machine's main memory. It is not the GPU: the GPU peak of the clip before was 13.45 GB, under the card's limit, and a GPU that runs out raises an error that the script catches and logs.

What was kept: the first clip. The job writes its report after every clip, so the clip was fetched and is in the film.

What I think the cause is, from the order of the script and not from a measurement: with model offloading, each large part waits in main memory while another is on the GPU. To encode the prompt of the second clip the text encoder goes back to the GPU and the transformer comes back to main memory. For a moment both are there, with the decoder and the frames of the first clip.

What was done:

1. The clip that was lost was sent again as a job of its own, which is the order that had just worked. It ran: 890.4 s, the same 13.45 GB at the peak (`runs.jsonl`, unit `s05_wan`, run `20261125T190635Z-9cb56a`).
2. For a job of several clips the script now encodes every prompt before the first clip and then drops the text encoder for good (`kaggle/wan22_i2v.py`). The first version of that change was wrong. It moved the encoded prompts to main memory, and in the next job of two clips both failed within twenty seconds with `RuntimeError: Expected all tensors to be on the same device, but got mat1 is on cpu, different from other tensors on cuda:0`. No GPU time was lost beyond loading the model. The encoded prompts stay on the GPU now. The job sent after that correction made both of its clips: the log says `2 prompts encoded, text encoder released`, then 779.2 s and 765.6 s a clip, 13.46 GB at the peak (`runs.jsonl`, units `s04_wan` and `s09_wan`). So a job of several clips works.

What it cost: the 14 minutes of the second clip were never spent. The cost is the second trip through Kaggle's queue.

What would be done differently: watch the machine's main memory as well as the GPU's. The script records GPU memory per clip and nothing about the other.

### F08  The rough cut was published by mistake  (25 Nov 2026)

Stage and tool: none of the pipeline. A git commit, made by the coding agent in my working session.

What happened: commit `9935183` (25 Nov, 23:24) was about the changes after the first listeners. It also carried the rough cut: `outputs/film_vertical.mp4` (33.8 MB), `outputs/film_horizontal.mp4` (34.0 MB), `outputs/radio_cut.mp4` (2.3 MB), `outputs/qc_report.json` and three files under `outputs/assemble/`. The narration lines in that cut were not confirmed by me. The commit was pushed at 23:25, 71 seconds after it was made (`git reflog show origin/main` on my machine): my editor pushes when it syncs. The `site` workflow runs on every push to `main`. It builds the public page and copies the two films into it when they are in the checkout (`.github/workflows/site.yml`, `pipeline/site.py`). By those rules the page built from that push held the rough cut, under a notice that the cut is not final. The record of that workflow run is on GitHub, not in this repository.

Cause, as far as it is known: the seven files were staged when the commit was made, and the list of staged files was not read before committing. The message of commit `683cfae` says so. Nothing in `.gitignore` kept them out. Until then the rule in the README was that the finished films are kept in `outputs/`, and no rule told a rough cut from a finished film.

What was done:

1. Commit `683cfae` (23:44, twenty minutes later) took the seven files out of the repository and added ignore rules for `outputs/film_*.mp4`, `outputs/radio_cut.mp4`, `outputs/qc_report.json` and `outputs/assemble/`. The files stay on my machine.
2. That commit was pushed at 00:33 on 26 Nov, with the push of `434f5de` (`git reflog show origin/main`). On my machine `origin/main` holds `683cfae` since then.

What is not undone: commit `9935183` stays in the history, so the three video files can still be read from it. The history of the pushed branch was not rewritten. Whether the public page was built again without the films after the push of 00:33 was not checked for this entry.

What it cost: a rough cut with lines I had not confirmed was the newest state of the branch on GitHub for 67 minutes, and it stays in the history.

What would be done differently: read the names of the staged files before every commit. And a file that must not be published gets its ignore rule on the day it is first made, not after it has gone out.

### F09  The speech quota ran out, and a second free key was put in  (25 and 26 Nov 2026)

Stage and model: narration. `gemini-3.8-flash-tts` on the free tier of the Gemini API: 10 requests a day. The day resets at midnight Pacific time (`pricing.json`), which is 11:00 East Africa Time.

What happened: by 23:16 on 25 Nov the ten requests of the day were used (`runs.jsonl`): 1 in the smoke test, 1 take, 4 single lines after the take could not be cut (F04), and 4 lines rewritten after the first listeners (run `20261125T201514Z-906fdc`). All ten were answered. From there the guard in the pipeline refuses a request before it is sent. At about 23:35 I heard the cut and asked for changes that needed all eight lines recorded again (F10). No request was left until 11:00 the next morning.

What was done, in order:

1. At about 00:10 on 26 Nov I replaced the Gemini key in `.env` with another key. The pipeline counts a model's daily use from the run log, so the count was set to start again: `pricing.json` holds `counted_from` `2026-11-25T21:10:00Z` for the three Gemini models, with a note that says why.
2. The eight lines were recorded with that key: a take, then each line alone (F10).
3. At 00:14 a request for line s01 was refused (`runs.jsonl`, run `20261125T211402Z-9d7c8e`, attempt 1):

```
HTTP 429, rate limit or quota reached. {"error":{"message":"Rate limit exceeded for model gemini-3.8-flash-tts (limit: 10 requests per day on Free Tier). Please retry in 10h45m56s or upgrade your tier at https://ai.dev/rate-limit.","code":"too_many_requests"}}
```

The retry rule sent the same request again, and 97 seconds after the refusal it was answered (attempt 2). Why a request was answered after a refusal that names the daily limit is not known.

What the message shows: the second key is a free-tier key too, with the same limit of 10 requests a day. It did not buy a larger allowance. It used a second free one on the same day.

Speech requests by key, from `runs.jsonl`: with 21:10 UTC as the boundary, as `pricing.json` has it, 11 requests lie before it, all answered, and 9 after it, 8 answered and 1 refused. That time is approximate. The take of 21:06:30 UTC lies before it, but it was sent in the same run as the seven lines after 21:10 (`20261125T210610Z-743eb1`), and a run reads the key once, when it starts (`load_env` in `pipeline/core.py`). Counted by run, 10 requests went to the first key and 10 to the second: 9 answered, 1 refused.

What has not been checked: whether Google's terms for the free tier allow a second key to be used when the first has reached its daily limit. The licence table in `ETHICS.md` quotes those terms on ownership and on data only.

What fixed it: nothing fixed the quota. Since 01:10 on 26 Nov the narration is spoken by a voice of Addis AI (E26 in `EXPERIMENTS.md`), which runs on a sign-up credit and states no daily limit on requests (`pricing.json`). The storyboard no longer names the Gemini speech model.

What it cost: 50 minutes in which no line could be spoken, from 23:16 to 00:06. Twenty speech requests in one quota day, where one free key allows ten. And an open question about the provider's terms.

What would be done differently: count what a change will need before the day's allowance is spent. And read the provider's terms before putting in a second key, not after.

### F10  The voice changed from one line to the next  (25 and 26 Nov 2026)

Stage and model: narration. `gemini-3.8-flash-tts` with the voice `Charon`, on the free tier.

What happened: I heard the cut of 23:20 on 25 Nov and wrote: "audio continuity ... that audio isnt continued from previous it is alsmot different" (quoted in `DESIGN.md`). My message named the line about the brokers (s06). The eight lines of that cut came from three sittings: a take at 16:43 UTC, single requests at 17:13 and single requests at 20:15. No request carried a seed.

What was measured: the median pitch of each line (`outputs/experiments/E25/results.json`). From one line to the next it moved by up to 4.5 semitones (s01 to s02), and by 2.8 semitones from s04 to s06. The lowest line is at 90.9 Hz and the highest at 136.8 Hz: 7.1 semitones apart.

What was tried, in order:

1. One take again, so that all lines come from one sitting. Since commit `ab3f224` a take is one text with the pause tag between the lines, and a speech request can carry a seed. The take of 00:06 on 26 Nov (run `20261125T210610Z-743eb1`, seed 7, style "calm, warm storyteller") gave 64.31 s of audio in 19.7 s. It could not be cut. Its record, `outputs/narration/takes/take__cc00c0151b072d82.json`, holds `cut_margin` 1.0, where 1.5 is the least the stage accepts, and `cut_from_take` names s01 only. The pauses between the lines were no longer than the pauses inside them.
2. Every line in a request of its own, with the same seed and the short style. The seven other lines were spoken alone in the same run, and s01 alone at 00:15 (run `20261125T211402Z-9d7c8e`). Measured again the same way, the largest step is 1.8 semitones and the eight lines lie 4.5 semitones apart (E25 in `EXPERIMENTS.md`).
3. Another provider. I proposed Addis AI, a speech service built for Ethiopian languages. Three of its voices were recorded on the same eight lines, each line in a request of its own: this API takes no seed and no style. In the first recording of the voice that is now in the cut, `am-nahom`, the largest step is 1.7 semitones (`outputs/voices/summary.json`, E26).

What fixed it: measured, the largest step came down from 4.5 to 1.8 and 1.7 semitones. That is a number, not an ear, and the pitch still drifts: with one seed the Gemini lines rise from 105.3 Hz at s01 to 136.8 Hz at s08. The film now uses the Addis AI voice.

What it cost: the ten speech attempts on the second free key (F09), and 32 requests to Addis AI, 0.11 USD at list price, taken from the sign-up credit.

What would be done differently: record all lines of a film in one sitting from the first day, and measure the pitch of each line before a person has to hear the fault. The plan to save speech requests with a take and single re-takes (E20) is what put three sittings into one film.

### F11  The tests failed on GitHub and passed on my machine  (26 Nov 2026)

Stage: the `tests` workflow on GitHub, on commit `38fa348`, pushed at 02:20.

What happened: 110 tests ran and one failed, `test_one_command_makes_the_film_and_only_changed_shots_regenerate`, with:

```
AssertionError: False is not true : [{'level': 'must', 'check': 'vertical: constant 24 fps', 'ok': False, 'detail': '1882112/78421'}, {'level': 'must', 'check': 'horizontal: constant 24 fps', 'ok': False, 'detail': '1882112/78421'}, ...
```

The commit before it on GitHub, `434f5de`, had passed. On my machine every run of the suite that night had passed.

Cause, in two layers:

1. The final-cut check compared the film's nominal frame rate and its average frame rate as two strings. 1882112/78421 is 24.0001. Worked out from the fraction: 919 frames in a file whose duration is two ticks of 1/12288 s shorter than 919 frames. That is a rounding in the container, not a film with a changing frame rate. The same commit, tested again in a scratch clone on my machine (FFmpeg 6.1.1), gives 24/1 and passes. Why the FFmpeg on GitHub writes the shorter duration was not found.
2. The coding agent had run the suite with `HERITAGE_FAST_TESTS=1` all night. That switch skips the three slowest tests, and this is one of them. So "the tests pass" had been said of a suite that did not build the offline film at all. Run in full on the next state of the storyboard, the same test failed on my machine too, for another reason: the offline film was 94.5 s long, over the limit of 90. The stand-in voice spoke 6.0 Ethiopic letters a second, and the real voice in the film speaks 6.7 (468 letters in 70.2 s).

What fixed it: the check asks for the nominal rate exactly and for the average within 0.01 of it (`pipeline/qc.py`). The stand-in voice and the estimate of a line's length use the measured pace (`SYLLABLES_A_SECOND` in `pipeline/core.py`). The full suite, 114 tests with none skipped, passes on my machine on the commit that holds this entry. Whether GitHub is green again is known only when that commit has been pushed and run there.

What it cost: one failed run on a public repository, and a claim of passing tests in the working notes that was not true of the whole suite.

What would be done differently: before a commit that changes the pipeline, run what GitHub runs, `make test`, not the short form.

### F12  The voice left out the first word of a line  (26 Nov 2026)

Stage and model: narration. Addis Voices 2 with the voice `am-nahom`.

What happened: the last line of my narration begins ዛሬ፣ ከሰባት ዓመት በኋላ፣ ("Today, seven years later,"). The recording began at ከሰባት. The listening check did not catch it: the speech model wrote the line down without its first word, and the match of the whole line was 0.96, far above the floor of 0.6. One word of fifteen does not move that number. The coding agent saw it when it read what the listener had written.

What was tried, in order:

1. Silence around the audio for the listener, 0.6 s before and 0.8 s after (run `20261125T235334Z-429c80`). In another line the listener had written ተከ for the last word ተከተልን, and with the silence it wrote the word in full: that one was the listener's fault. The first word of the last line was still missing.
2. A second listener, the text model (run `20261125T235356Z-e6490f`). It also wrote the line from ከሰባት. So the word is not in the audio.
3. Three new recordings of the line (E29 in `EXPERIMENTS.md`): the same text again, the first word as a sentence of its own, and the text without the comma after the first word. Only the third has the word.
4. In the pipeline the line is now sent to this voice without that one comma. The first take has ዛሬ, and its last word, አጣጥመው, was written as አታጥሞ. The second take is without ዛሬ again. The third has both ends.

What fixed it: for this film, the third take (`"takes": {"s09": 3}` in the storyboard). In general it is not fixed: of four recordings sent without the comma, one still lacks the first word. What changed is that it is now seen. The listening check looks at the first and the last word of every line on their own (`unheard_edges` in `pipeline/core.py`), the final-cut check lists a line where one was not heard, and `voice.takes` asks the voice for that line again.

What it cost: six extra speech requests and about twenty listening requests, a few cents of the sign-up credit. And it could have cost the film its "today": I had not heard this cut yet.

What would be done differently: a score over a whole line cannot see one missing word. The two ends of a line are where a speech model cuts, so they are checked on their own from the first recording on.

## From the offline build (coding agent, 25 Nov 2026)

These happened while the pipeline was first written, before any real model call. They are kept because each one changed the code.

### B1  The build machine could not reach any model provider
What happened: the sandbox the coding agent worked in could reach GitHub and PyPI only. Requests to the Gemini API, Cloudflare, Kaggle and Hugging Face all failed to connect.
What was done: every provider got an offline stand-in (`--mock`): beeps the length of the line for speech, labelled colour cards for images, fixed answers for text. The whole pipeline and the tests run on them. Mock output goes to `outputs_mock/` and a separate log, so it can never be mistaken for a real run.
What it means: the code for real calls follows the provider docs but had not touched a real model when it was written. The README status table tracks what has since.

### B2  The speech API in the docs was not the one expected
What happened: the Gemini speech page (25 Nov 2026) documents the Interactions API (`/v1beta/interactions`, style as a `speech_metadata` annotation, audio in `steps[].content[]`), not the older `generateContent` call with `speechConfig`.
What was done: the client was written for the documented call, and the response parser searches the JSON for the audio wherever it sits, so either shape is read.
Open when this was written: no seed parameter was known for speech, so two takes of one line could differ, and speech was logged as `seed: null`. Changed on the night of 25 Nov: the message of commit `ab3f224` says the documentation names a seed for reproducible decoding. Since that commit every Gemini speech request carries one when `voice.seed` is set (`speech_config` in `pipeline/providers.py`), and the line is logged with it (F10).

### B3  The plan disagreed with the run
What happened: after one narration line was changed, `plan` said four unrelated shots would be rebuilt. The run rebuilt only the right one.
Cause: `plan` skipped the keyframe judge, so it picked candidate 1 where the run had picked candidate 2, and everything downstream of those shots looked changed.
Fix: `plan` now reads the judge scores already in the cache. A test of the real run already covered selective rebuilds; the plan was checked by hand (0 units to build on an unchanged storyboard).

### B4  The MCP server died on start
What happened: `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`. The installed `mcp` package was 2.3.0, where `FastMCP` was renamed to `MCPServer`.
Fix: the server imports the new name and falls back to the old one. Checked with a real MCP client: tools listed, `validate` and `plan` called.

### B5  Wan 2.2 does not officially fit the free GPU (a risk, not yet hit)
What is known: the model card asks for at least 24 GB of GPU memory, and a Kaggle T4 has 16 GB. A Diffusers issue reports memory jumping from about 8 GB to 26 GB when the finished 720p clip is decoded.
What was done before the first run: the default job is a draft size (480x832 area, 81 frames), the model parts are moved to the GPU one at a time, each clip's peak memory is recorded, and a failed clip does not stop the others. If it still does not fit, the shot stays on its Ken Burns fallback and the film is still complete.
Experiment E08 is the first real test of this.
