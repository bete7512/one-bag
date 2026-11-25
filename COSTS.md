# Costs

Money spent: only on Claude Opus 5.5, the picture judge and the subtitle check, which has no free tier. The amount is in the line under the table, from the run log. Everything else ran on free tiers, where the real limits are quota and GPU time, so most of this file is about measured time.

## Measured, per stage

The table between the markers is written by `make costs` from `runs.jsonl`: one line per model call, with the latency the pipeline measured and, for GPU work, the minutes the notebook measured itself. It is empty until real calls have been made.

<!-- costs:begin (written by `python -m pipeline costs --write`) -->
| Stage | Provider | Model | Calls | Failed | Total latency (s) | Mean latency (s) | GPU minutes | List price (USD) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| script | anthropic | `claude-opus-5-5` | 16 | 0 | 63.8 | 4.0 | 0.0 | 0.1195 |
| narration | gemini | `gemini-3.5-flash-lite` | 64 | 13 | 395.7 | 6.2 | 0.0 | 0.0038 |
| narration | gemini | `gemini-3.8-flash-tts` | 5 | 0 | 42.1 | 8.4 | 0.0 | 0.0224 |
| keyframes | anthropic | `claude-opus-5-5` | 64 | 0 | 442.7 | 6.9 | 0.0 | 1.3009 |
| keyframes | cloudflare | `@cf/black-forest-labs/flux-2-klein-4b` | 80 | 0 | 929.3 | 11.6 | 0.0 | 0.0950 |
| keyframes | gemini | `gemini-3.5-flash-lite` | 16 | 4 | 66.2 | 4.1 | 0.0 | 0.0069 |
| keyframes | gemini | `gemini-3.8-flash` | 22 | 20 | 1072.7 | 48.8 | 0.0 | 0.0000 + 2 n/a |
| shots | kaggle | `Wan-AI/Wan2.2-TI2V-5B-Diffusers` | 1 | 0 | 820.7 | 820.7 | 13.7 | 0.1596 |
| music | gemini | `gemini-3.5-flash-lite` | 9 | 3 | 28.3 | 3.1 | 0.0 | 0.0055 |
| music | kaggle | `acestep-v15-turbo` | 6 | 0 | 45.0 | 7.5 | 0.8 | 0.0087 |
| experiment | anthropic | `claude-opus-5-5` | 44 | 12 | 194.6 | 4.4 | 0.0 | 0.4638 |
| experiment | gemini | `gemini-3.5-flash-lite` | 22 | 7 | 81.7 | 3.7 | 0.0 | 0.0137 |
| smoke | anthropic | `claude-opus-5-5` | 4 | 3 | 11.1 | 2.8 | 0.0 | 0.0002 |
| smoke | cloudflare | `@cf/black-forest-labs/flux-2-klein-4b` | 1 | 0 | 4.5 | 4.5 | 0.0 | 0.0003 |
| smoke | gemini | `gemini-3.5-flash-lite` | 2 | 0 | 3.9 | 2.0 | 0.0 | 0.0000 |
| smoke | gemini | `gemini-3.8-flash` | 2 | 0 | 180.0 | 90.0 | 0.0 | n/a |
| smoke | gemini | `gemini-3.8-flash-tts` | 1 | 0 | 4.7 | 4.7 | 0.0 | n/a |
| **Total** | | | 359 | 62 | 4387.0 | | 14.4 | 2.2003 + 5 n/a |

Source: `runs.jsonl`, 359 model calls. List price is what the calls would cost without the free tiers. Really paid: 1.8843 USD, for the calls to models that have no free tier. Everything else ran free. 5 call(s) are n/a and not in the sums: their price, or the usage it applies to, was not known when they were logged.
<!-- costs:end -->

The list-price column answers "what would the same calls cost without the free tier". It uses `pricing.json`, where a price is only filled in from the provider's own pricing page, with the date. Until then it shows n/a.

## Free-tier limits, as read and as met

The brief warns that free tiers change often. One row per model: the limit as its provider states it for this project, and what the run log shows.

| Model | Limit on the free tier | What happened | Date |
|---|---|---|---|
| `gemini-3.8-flash` (text) | 5 requests a minute, 20 a day | Reached on the first afternoon: 16 answers of HTTP 503 "high demand", then HTTP 429 once the count passed 20. An answer took 42 to 144 s when one came. See F01 in `FAILURES.md`. | 2026-11-25 |
| `gemini-3.5-flash-lite` (text and listening) | 15 requests a minute, 500 a day | Not reached: 109 requests on the first day, 83 answered in 1.4 to 53 s and 26 refused with HTTP 503. A request that held many audio clips was refused every time, twelve times in a row (F04). | 2026-11-25 |
| `gemini-3.8-flash-tts` (speech) | 3 requests a minute, 10 a day | Not reached: 6 of the 10 used on the first day. One request for all eight lines gave 70 s of audio in 19 s, four single lines took 4.8 to 6.7 s each. Ten a day is why the lines are first spoken in one request (E20). | 2026-11-25 |
| FLUX.2 klein 4B on Cloudflare Workers AI | 10,000 neurons a day, about 96 pictures of 1024 x 1024, fewer when reference pictures are sent along | Not reached, but close: 81 pictures on the first day, 87% of the day's allowance, 4.5 to 28 s each. | 2026-11-25 |
| Kaggle GPU | 30 hours a week | 0 hours used when checked with `kaggle quota`. | 2026-11-25 |
| `claude-opus-5-5` (judge, subtitle check) | No free tier: 4 USD per million tokens in, 20 out | 113 answers in 2.7 to 12.4 s. A judged picture costs 0.013 to 0.028 USD, 0.020 on average: more when reference pictures are sent with it. 15 earlier attempts were refused for billing reasons and cost nothing (F03). | 2026-11-25 |

The Gemini limits are not in Google's documentation. They come from the rate-limit page of this project in Google AI Studio. The Cloudflare allowance is from its pricing page: 10,000 neurons a day, and 104.2 neurons for a 1024 x 1024 picture from this model. All of them are in `pricing.json` under `free_tier`, where the pipeline reads them: it refuses a request that would go over a daily limit and waits out a per-minute one.

## GPU time

From the job's own `results.json`, the run log (`provider: kaggle`) and `outputs/logs/kaggle_sessions.jsonl`.

| Job | GPU | Whole session | Model load | Per item | Peak GPU memory | Failed attempts |
|---|---|---|---|---|---|---|
| Score, ACE-Step 1.5 turbo, 3 candidates of 80 s | 2 x Tesla T4 on Kaggle | 229 s from push to done | 61.7 s | 9.2, 6.5 and 6.6 s | 6.4 GB | 2 before it: no internet, then a run that never left the queue (F02) |
| Score, second description, 3 candidates of 80 s | 2 x Tesla T4 on Kaggle | about 4 minutes from push to done | not kept | 10.1, 6.2 and 6.4 s | 6.4 GB | 1 before it: the job that was sent was an old one (F06) |
| Moving shot, Wan 2.2 TI2V-5B, 81 frames at 608 x 608 | 2 x Tesla T4 on Kaggle, one used | about 20 minutes once it had left the queue | 248.1 s | 820.7 s | 13.45 GB | the second clip of the same job was killed (F07) |

The session time is mostly not generation: building ACE-Step's own Python environment and downloading the model take about three of the four minutes. The three candidates together took 22 seconds of GPU. At that speed a second set with another caption costs four minutes, so the score can be iterated like a prompt.

What the same GPU time costs when rented: one T4 is 0.35 USD an hour on demand at Google Cloud (its GPU pricing page, read on 2026-11-25, the GPU alone). The 22 seconds of generation on two T4s come to 0.004 USD, and the whole session of 229 seconds to 0.045 USD. The three lines of that run were logged before the price was read and carry no cost of their own. The log is not rewritten: the table works their price out from the GPU minutes they hold.

Kaggle's queue was the larger cost on the first evening: the two jobs of 20:22 and 20:30 waited 39 and about 45 minutes before they started. A clip from Wan 2.2 costs 0.16 USD at the list price of two rented T4s for the 13.7 minutes it takes, and a set of three scores 0.004 USD.

## Frontier comparison

No access to a frontier model for pictures, video or music: those are behind paid billing that could not be attached. The one frontier model in reach was a text and vision model, Claude Opus 5.5, so the comparison was made where it could be: the keyframe judge. Same question, same 12 pictures (E17 in `EXPERIMENTS.md`).

| | `gemini-3.5-flash-lite`, free tier | `claude-opus-5-5`, paid |
|---|---|---|
| Seconds per answer | 1.9 to 9.1 | 3.6 to 9.6 |
| Failed attempts | 7 of 19, all HTTP 503 | none of 12 |
| List price for 12 pictures | 0.012 USD | 0.195 USD |
| Pictures with a border, of 9 | 8 found | 9 found |
| Different totals over 12 pictures | 5 | 9 |

Sixteen times the price bought one more border found, no failed calls, and notes that say what to change in the prompt. For a film of nine shots with two candidates each that is about 0.37 USD a pass, so it is the judge in use. Claude cost 1.88 USD in all on the first day: four passes over the pictures, the counts for E17 and E19, and the subtitle checks.
