# Costs

Money is spent in two places, and one provider runs on a credit. The amounts are from the run log as it stood on 26 November 2026 at 02:33 East Africa Time, with 745 lines.

| Provider | What is paid | Amount |
|---|---|---|
| Claude Opus 5.5: the picture judge, the subtitle check, four experiments | Every call. It has no free tier, and the calls are paid from prepaid credit (`pricing.json`) | 4.17 USD: the sum of `cost_usd` over provider `anthropic` in `runs.jsonl` |
| Cloudflare Workers AI: the pictures | The Workers Paid plan, 5 USD a month, since about 23:50 on 25 Nov (`pricing.json`). On top of it, the part of each UTC day that goes over the free allowance of 10,000 neurons, which is 0.11 USD at list price | 5 USD a month for the plan. Over the allowance so far: 0.06 USD, on 25 Nov UTC, as `over_allowance` in `pipeline/costs.py` counts it from the log |
| Addis AI: the narration voice and the listening check | Nothing so far. It runs on a sign-up credit of 3.17 USD (`pricing.json`) | 0 USD paid. 42 speech requests gave 277.0 s of audio: 0.15 USD at the list price of 0.000533 USD a second, taken from the credit. Twenty requests to its speech-to-text model, `addis-scribe`, add 0.023 USD at list price. The API reports its balance with every answer: 27.17 of the 500 ETB credit are used |

Two limits of these amounts. The Cloudflare figure is what the log adds up to, not a bill: no invoice is in the repository. And it leaves out the seven picture calls that were logged before the `cost_usd` field existed, 0.007 USD at list price.

Everything else ran on free tiers: the Gemini models and the Kaggle GPU. There the real limits are quota and GPU time, so most of this file is about measured time.

## Measured, per stage

The table between the markers is written by `make costs` from `runs.jsonl`: one line per model call, with the latency the pipeline measured and, for GPU work, the minutes the notebook measured itself. It is empty until real calls have been made.

<!-- costs:begin (written by `python -m pipeline costs --write`) -->
| Stage | Provider | Model | Calls | Failed | Total latency (s) | Mean latency (s) | GPU minutes | List price (USD) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| script | anthropic | `claude-opus-5-5` | 51 | 0 | 202.6 | 4.0 | 0.0 | 0.3885 |
| narration | addis | `addis-scribe` | 18 | 0 | 38.8 | 2.2 | 0.0 | 0.0229 |
| narration | addis | `addis-voices-2` | 42 | 0 | 327.4 | 7.8 | 0.0 | 0.1476 |
| narration | gemini | `gemini-3.5-flash-lite` | 157 | 16 | 897.8 | 5.7 | 0.0 | 0.0136 |
| narration | gemini | `gemini-3.8-flash-tts` | 19 | 1 | 140.4 | 7.4 | 0.0 | 0.0630 |
| keyframes | anthropic | `claude-opus-5-5` | 141 | 0 | 1091.6 | 7.7 | 0.0 | 3.0172 |
| keyframes | cloudflare | `@cf/black-forest-labs/flux-2-klein-4b` | 154 | 0 | 1768.1 | 11.5 | 0.0 | 0.1811 |
| keyframes | gemini | `gemini-3.5-flash-lite` | 16 | 4 | 66.2 | 4.1 | 0.0 | 0.0069 |
| keyframes | gemini | `gemini-3.8-flash` | 22 | 20 | 1072.7 | 48.8 | 0.0 | 0.0000 + 2 n/a |
| shots | kaggle | `Wan-AI/Wan2.2-TI2V-5B-Diffusers` | 6 | 2 | 3314.0 | 552.3 | 55.2 | 0.6444 |
| music | gemini | `gemini-3.5-flash-lite` | 9 | 3 | 28.3 | 3.1 | 0.0 | 0.0055 |
| music | kaggle | `acestep-v15-turbo` | 6 | 0 | 45.0 | 7.5 | 0.8 | 0.0087 |
| experiment | addis | `addis-scribe` | 2 | 0 | 6.5 | 3.3 | 0.0 | 0.0032 |
| experiment | anthropic | `claude-opus-5-5` | 70 | 12 | 315.8 | 4.5 | 0.0 | 0.7603 |
| experiment | gemini | `gemini-3.5-flash-lite` | 22 | 7 | 81.7 | 3.7 | 0.0 | 0.0137 |
| smoke | anthropic | `claude-opus-5-5` | 4 | 3 | 11.1 | 2.8 | 0.0 | 0.0002 |
| smoke | cloudflare | `@cf/black-forest-labs/flux-2-klein-4b` | 1 | 0 | 4.5 | 4.5 | 0.0 | 0.0003 |
| smoke | gemini | `gemini-3.5-flash-lite` | 2 | 0 | 3.9 | 2.0 | 0.0 | 0.0000 |
| smoke | gemini | `gemini-3.8-flash` | 2 | 0 | 180.0 | 90.0 | 0.0 | n/a |
| smoke | gemini | `gemini-3.8-flash-tts` | 1 | 0 | 4.7 | 4.7 | 0.0 | n/a |
| **Total** | | | 745 | 68 | 9601.3 | | 56.0 | 5.2772 + 5 n/a |

Source: `runs.jsonl`, 745 model calls. List price is what the calls would cost without the free tiers. Really paid: 4.2304 USD, for the calls to models that have no free tier. Everything else ran free. 5 call(s) are n/a and not in the sums: their price, or the usage it applies to, was not known when they were logged.
<!-- costs:end -->

The list-price column answers "what would the same calls cost without the free tier". It uses `pricing.json`, where a price is only filled in from the provider's own pricing page, with the date. Until then it shows n/a.

The sentence under the table is written by the command, and it says less than the table at the top of this file. Its amount is the Claude calls plus the part of the picture calls over the free daily allowance. It does not hold the 5 USD a month of the Cloudflare plan. And "ran free" there includes the calls to Addis AI, which ran on a credit.

## Limits, as read and as met

The brief warns that free tiers change often. One row per model: the limit as its provider states it for this project, and what the run log shows. Every line of the log so far lies in one quota day of the Gemini API, which runs from 11:00 to 11:00 East Africa Time.

| Model | Limit | What happened | Date |
|---|---|---|---|
| `gemini-3.8-flash` (text) | 5 requests a minute, 20 a day | Reached on the first afternoon: 16 answers of HTTP 503 "high demand", then HTTP 429 once the count passed 20. An answer took 42 to 144 s when one came. See F01 in `FAILURES.md`. | 2026-11-25 |
| `gemini-3.5-flash-lite` (text and listening) | 15 requests a minute, 500 a day | Not reached on either key: 206 requests in all, 176 answered in 1.4 to 53 s and 30 refused with HTTP 503. 160 of them came before the key was replaced and 46 after. A request that held many audio clips was refused every time, twelve times in a row (F04). | 2026-11-26 |
| `gemini-3.8-flash-tts` (speech), first key | 3 requests a minute, 10 a day | Reached: 10 requests between 13:22 and 23:16 on 25 Nov, all answered. One request for all eight lines gave 70 s of audio in 19 s, and a single line took 4.8 to 7.6 s. Ten a day is why the lines were first spoken in one request (E20). | 2026-11-25 |
| `gemini-3.8-flash-tts` (speech), second key | The same. It is a free-tier key too: the provider's message on a refused request says "limit: 10 requests per day on Free Tier" | 10 attempts between 00:06 and 00:15 on 26 Nov: 9 answered, 1 refused with HTTP 429 (F09). Not called since: the narration moved to Addis AI. | 2026-11-26 |
| `addis-voices-2` (speech, Addis AI) | Pay as you go: 0.032 USD a generated minute, given as an indicative price. A new account has a credit of 3.17 USD. No daily limit on requests is stated | 42 requests, none failed, 5.7 to 11.0 s each. 0.15 USD of the credit used, at list price. | 2026-11-26 |
| `addis-scribe` (speech to text, Addis AI) | Pay as you go: each answer reports 3.5 ETB per 1,000 characters written down, about 0.022 USD. Paid from the same credit. The documentation gives ten transcriptions at a time as the limit | 20 requests, none failed, 1.4 to 5.0 s each. 0.023 USD of the credit used, at list price. | 2026-11-26 |
| FLUX.2 klein 4B on Cloudflare Workers AI | 10,000 neurons a day are free: about 96 pictures of 1024 x 1024, fewer when reference pictures are sent along. On the Workers Paid plan, since about 23:50 on 25 Nov, the rest is billed at 0.011 USD per 1,000 neurons | Passed on 25 Nov UTC: 151 picture calls, 161% of the day's allowance at list price, 4.0 to 37 s each. By the log the allowance was passed at 23:56 East Africa Time, after the account had moved to the paid plan. | 2026-11-26 |
| Kaggle GPU | 30 hours a week | Not known today. `kaggle quota` said 1.13 hours when it was last read, which was written into this file at 23:24 on 25 Nov (commit `9935183`). Two more Wan jobs ran after that: one in which both clips failed in under a minute, and one that took 29.9 minutes to load the model and make two clips. Part of the time made nothing new: a job that was sent twice (F06), a job that was killed after its first clip (F07), and the job that failed. | 2026-11-25 |
| `claude-opus-5-5` (judge, subtitle check) | No free tier: 4 USD per million tokens in, 20 out | 211 answers in 2.7 to 34.1 s. A judged picture costs 0.012 to 0.030 USD, 0.021 on average: more when reference pictures are sent with it. 15 earlier attempts were refused for billing reasons and cost nothing (F03). | 2026-11-26 |

The Gemini limits are not in Google's documentation. They come from the rate-limit page of this project in Google AI Studio. The Cloudflare allowance is from its pricing page: 10,000 neurons a day, and 104.2 neurons for a 1024 x 1024 picture from this model. The Addis AI price is from its pricing page and its documentation. All of them are in `pricing.json`, where the pipeline reads them: it refuses a request that would go over a free daily limit and waits out a per-minute one. For the pictures it goes on over the allowance since the paid plan, and says once in the run that the calls are paid for from there.

### Two Gemini keys

By 23:16 on 25 Nov the first key had used its ten speech requests for the day. At about 00:10 on 26 Nov I replaced the Gemini key in `.env` with a second key. `pricing.json` records it in `counted_from`, so that the pipeline counts the day's use from that time. The second key is a free-tier key too. The provider's own message on a refused request says "limit: 10 requests per day on Free Tier". The full text is in F09 in `FAILURES.md`.

Speech requests in `runs.jsonl`, with 21:10 UTC on 25 Nov as the boundary, as `pricing.json` has it: 11 before it, all answered, and 9 after it, 8 answered and 1 refused. The boundary is approximate. The take of 21:06 UTC lies before it, but it was sent in the same run as the seven lines after it, and a run reads the key once. Counted by run, 10 requests went to the first key and 10 to the second: 9 answered, 1 refused.

Whether the provider's terms allow a second free key to be used when the first has reached its daily limit has not been checked.

## GPU time

From the job's own `results.json`, the run log (`provider: kaggle`) and `outputs/logs/kaggle_sessions.jsonl`.

| Job | GPU | Whole session | Model load | Per item | Peak GPU memory | Failed attempts |
|---|---|---|---|---|---|---|
| Score, ACE-Step 1.5 turbo, 3 candidates of 80 s | 2 x Tesla T4 on Kaggle | 229 s from push to done | 61.7 s | 9.2, 6.5 and 6.6 s | 6.4 GB | 2 before it: no internet, then a run that never left the queue (F02) |
| Score, second description, 3 candidates of 80 s | 2 x Tesla T4 on Kaggle | about 4 minutes from push to done | not kept | 10.1, 6.2 and 6.4 s | 6.4 GB | 1 before it: the job that was sent was an old one (F06) |
| Moving shots, Wan 2.2 TI2V-5B, 81 frames at 608 x 608, two clips in two jobs | 2 x Tesla T4 on Kaggle, one used | about 20 minutes a job once it had left the queue | 248.1 and 245.7 s | 820.7 and 890.4 s | 13.45 GB both times | the second clip of the first job was killed (F07) |
| Moving shots, two more clips in one job (s04 and s09), same settings | 2 x Tesla T4 on Kaggle | not kept | 246.4 s | 779.2 and 765.6 s | 13.46 and 13.45 GB | 1 before it: a job in which both clips failed, after 38.3 and 19.8 s (F07) |

The session time is mostly not generation: building ACE-Step's own Python environment and downloading the model take about three of the four minutes. The three candidates together took 22 seconds of GPU. At that speed a second set with another caption costs four minutes, so the score can be iterated like a prompt.

What the same GPU time costs when rented: one T4 is 0.35 USD an hour on demand at Google Cloud (its GPU pricing page, read on 2026-11-25, the GPU alone). The 22 seconds of generation on two T4s come to 0.004 USD, and the whole session of 229 seconds to 0.045 USD. The three lines of that run were logged before the price was read and carry no cost of their own. The log is not rewritten: the table works their price out from the GPU minutes they hold.

Kaggle's queue was the larger cost on the first evening: the two jobs of 20:22 and 20:30 waited 39 and about 45 minutes before they started. A clip from Wan 2.2 costs 0.15 to 0.17 USD at the list price of two rented T4s for the 12.8 to 14.8 minutes it takes, and a set of three scores 0.004 USD. The run log holds 55.2 minutes for the six Wan attempts and 0.75 minutes for the six scores. That is the time of the clips and scores alone, without loading the model, and it is not what Kaggle counts against the weekly quota.

## Frontier comparison

No access to a frontier model for pictures, video or music: those are behind paid billing that could not be attached. The one frontier model in reach was a text and vision model, Claude Opus 5.5, so the comparison was made where it could be: the keyframe judge. Same question, same 12 pictures (E17 in `EXPERIMENTS.md`).

| | `gemini-3.5-flash-lite`, free tier | `claude-opus-5-5`, paid |
|---|---|---|
| Seconds per answer | 1.9 to 9.1 | 3.6 to 9.6 |
| Failed attempts | 7 of 19, all HTTP 503 | none of 12 |
| List price for 12 pictures | 0.012 USD | 0.195 USD |
| Pictures with a border, of 9 | 8 found | 9 found |
| Different totals over 12 pictures | 5 | 9 |

Sixteen times the price bought one more border found, no failed calls, and notes that say what to change in the prompt. For a film of nine shots with two candidates each that is about 0.39 USD a pass, so it is the judge in use. Claude has cost 4.17 USD in all, by the run log at the time given at the top of this file: 3.02 USD for 141 judged pictures in the keyframes stage, 0.76 USD for the experiments E17, E19, E24 and E28, and 0.39 USD for 51 subtitle checks.
