# Costs

Money spent: only on Claude Opus 5.5, the picture judge and the subtitle check, which has no free tier. The amount is in the line under the table, from the run log. Everything else ran on free tiers, where the real limits are quota and GPU time, so most of this file is about measured time.

## Measured, per stage

The table between the markers is written by `make costs` from `runs.jsonl`: one line per model call, with the latency the pipeline measured and, for GPU work, the minutes the notebook measured itself. It is empty until real calls have been made.

<!-- costs:begin (written by `python -m pipeline costs --write`) -->
| Stage | Provider | Model | Calls | Failed | Total latency (s) | Mean latency (s) | GPU minutes | List price (USD) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| script | anthropic | `claude-opus-5-5` | 8 | 0 | 32.8 | 4.1 | 0.0 | 0.0590 |
| keyframes | cloudflare | `@cf/black-forest-labs/flux-2-klein-4b` | 12 | 0 | 90.9 | 7.6 | 0.0 | 0.0138 |
| keyframes | gemini | `gemini-3.5-flash-lite` | 16 | 4 | 66.2 | 4.1 | 0.0 | 0.0069 |
| keyframes | gemini | `gemini-3.8-flash` | 22 | 20 | 1072.7 | 48.8 | 0.0 | 0.0000 + 2 n/a |
| music | gemini | `gemini-3.5-flash-lite` | 5 | 2 | 15.3 | 3.1 | 0.0 | 0.0026 |
| music | kaggle | `acestep-v15-turbo` | 3 | 0 | 22.3 | 7.4 | 0.4 | n/a |
| experiment | anthropic | `claude-opus-5-5` | 24 | 12 | 78.0 | 3.3 | 0.0 | 0.1947 |
| experiment | gemini | `gemini-3.5-flash-lite` | 22 | 7 | 81.7 | 3.7 | 0.0 | 0.0137 |
| smoke | anthropic | `claude-opus-5-5` | 4 | 3 | 11.1 | 2.8 | 0.0 | 0.0002 |
| smoke | cloudflare | `@cf/black-forest-labs/flux-2-klein-4b` | 1 | 0 | 4.5 | 4.5 | 0.0 | 0.0003 |
| smoke | gemini | `gemini-3.8-flash` | 2 | 0 | 180.0 | 90.0 | 0.0 | n/a |
| smoke | gemini | `gemini-3.8-flash-tts` | 1 | 0 | 4.7 | 4.7 | 0.0 | n/a |
| **Total** | | | 120 | 48 | 1660.2 | | 0.4 | 0.2911 + 8 n/a |

Source: `runs.jsonl`, 120 model calls. List price is what the calls would cost without the free tiers. Really paid: 0.2538 USD, for the calls to models that have no free tier. Everything else ran free. 8 call(s) are n/a and not in the sums: their price, or the usage it applies to, was not known when they were logged.
<!-- costs:end -->

The list-price column answers "what would the same calls cost without the free tier". It uses `pricing.json`, where a price is only filled in from the provider's own pricing page, with the date. Until then it shows n/a.

## Free-tier limits, as read and as met

The brief warns that free tiers change often. One row per model: the limit as its provider states it for this project, and what the run log shows.

| Model | Limit on the free tier | What happened | Date |
|---|---|---|---|
| `gemini-3.8-flash` (text) | 5 requests a minute, 20 a day | Reached on the first afternoon: 16 answers of HTTP 503 "high demand", then HTTP 429 once the count passed 20. An answer took 42 to 144 s when one came. See F01 in `FAILURES.md`. | 2026-11-25 |
| `gemini-3.5-flash-lite` (text) | 15 requests a minute, 500 a day | Not reached. 15 answers in 1.8 to 9.8 s. 4 attempts got HTTP 503 and passed on the next attempt. | 2026-11-25 |
| `gemini-3.8-flash-tts` (speech) | 3 requests a minute, 10 a day | Not reached: one smoke call so far, 4.7 s. Ten a day is why the narration is spoken in one request for all lines. | 2026-11-25 |
| FLUX.2 klein 4B on Cloudflare Workers AI | 10,000 neurons a day, about 96 pictures of 1024 x 1024 | Not reached: 13 pictures, 6 to 10 s each. | 2026-11-25 |
| Kaggle GPU | 30 hours a week | 0 hours used when checked with `kaggle quota`. | 2026-11-25 |
| `claude-opus-5-5` (judge, subtitle check) | No free tier: 4 USD per million tokens in, 20 out | 21 answers in 2.7 to 9.6 s, about 0.016 USD for a judged picture. 15 earlier attempts were refused for billing reasons and cost nothing (F03). | 2026-11-25 |

The Gemini limits are not in Google's documentation. They come from the rate-limit page of this project in Google AI Studio. The Cloudflare allowance is from its pricing page: 10,000 neurons a day, and 104.2 neurons for a 1024 x 1024 picture from this model. All of them are in `pricing.json` under `free_tier`, where the pipeline reads them: it refuses a request that would go over a daily limit and waits out a per-minute one.

## GPU time

From the job's own `results.json`, the run log (`provider: kaggle`) and `outputs/logs/kaggle_sessions.jsonl`.

| Job | GPU | Whole session | Model load | Per item | Peak GPU memory | Failed attempts |
|---|---|---|---|---|---|---|
| Score, ACE-Step 1.5 turbo, 3 candidates of 80 s | 2 x Tesla T4 on Kaggle | 229 s from push to done | 61.7 s | 9.2, 6.5 and 6.6 s | 6.4 GB | 2 before it: no internet, then a run that never left the queue (F02) |

The session time is mostly not generation: building ACE-Step's own Python environment and downloading the model take about three of the four minutes. The three candidates together took 22 seconds of GPU. At that speed a second set with another caption costs four minutes, so the score can be iterated like a prompt.

No clip has been made with Wan 2.2 yet.

## Frontier comparison

No access to a frontier model for pictures, video or music: those are behind paid billing that could not be attached. The one frontier model in reach was a text and vision model, Claude Opus 5.5, so the comparison was made where it could be: the keyframe judge. Same question, same 12 pictures (E17 in `EXPERIMENTS.md`).

| | `gemini-3.5-flash-lite`, free tier | `claude-opus-5-5`, paid |
|---|---|---|
| Seconds per answer | 1.9 to 9.1 | 3.6 to 9.6 |
| Failed attempts | 7 of 19, all HTTP 503 | none of 12 |
| List price for 12 pictures | 0.012 USD | 0.195 USD |
| Pictures with a border, of 9 | 8 found | 9 found |
| Different totals over 12 pictures | 5 | 9 |

Sixteen times the price bought one more border found, no failed calls, and notes that say what to change in the prompt. For a film of ten shots that is about 0.40 USD a pass, so it is the judge in use.
