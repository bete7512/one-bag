# Costs

Money spent: to fill in after the real runs (the plan is zero, on free tiers). The real limits are quota and GPU time, so this file is about measured time.

## Measured, per stage

The table between the markers is written by `make costs` from `runs.jsonl`: one line per model call, with the latency the pipeline measured and, for GPU work, the minutes the notebook measured itself. It is empty until real calls have been made.

<!-- costs:begin (written by `python -m pipeline costs --write`) -->
| Stage | Provider | Model | Calls | Failed | Total latency (s) | Mean latency (s) | GPU minutes | List price (USD) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| keyframes | cloudflare | `@cf/black-forest-labs/flux-2-klein-4b` | 12 | 0 | 90.9 | 7.6 | 0.0 | 0.0138 |
| keyframes | gemini | `gemini-3.5-flash-lite` | 16 | 4 | 66.2 | 4.1 | 0.0 | 0.0069 |
| keyframes | gemini | `gemini-3.8-flash` | 22 | 20 | 1072.7 | 48.8 | 0.0 | 0.0000 + 2 n/a |
| experiment | gemini | `gemini-3.5-flash-lite` | 3 | 0 | 7.4 | 2.5 | 0.0 | 0.0017 |
| smoke | cloudflare | `@cf/black-forest-labs/flux-2-klein-4b` | 1 | 0 | 4.5 | 4.5 | 0.0 | 0.0003 |
| smoke | gemini | `gemini-3.8-flash` | 2 | 0 | 180.0 | 90.0 | 0.0 | n/a |
| smoke | gemini | `gemini-3.8-flash-tts` | 1 | 0 | 4.7 | 4.7 | 0.0 | n/a |
| **Total** | | | 57 | 24 | 1426.4 | | 0.0 | 0.0227 + 5 n/a |

Source: `runs.jsonl`, 57 model calls. List price is what the calls would cost without the free tier: nothing was paid. 5 call(s) are n/a and not in the sums: their price, or the usage it applies to, was not known when they were logged.
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

The Gemini limits are not in Google's documentation. They come from the rate-limit page of this project in Google AI Studio. The Cloudflare allowance is from its pricing page: 10,000 neurons a day, and 104.2 neurons for a 1024 x 1024 picture from this model. All of them are in `pricing.json` under `free_tier`, where the pipeline reads them: it refuses a request that would go over a daily limit and waits out a per-minute one.

## GPU time

To fill in from the ingested job results: seconds per clip, clips per hour, peak memory per clip, and how many attempts failed. The run log holds all of it (`provider: kaggle`).

## Frontier comparison

No frontier access so far. If the cohort's organisation key opens, the plan is one shot generated both ways, with cost and latency side by side and a blind preference test (`python -m pipeline blindtest`).
