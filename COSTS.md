# Costs

Money spent: to fill in after the real runs (the plan is zero, on free tiers). The real limits are quota and GPU time, so this file is about measured time.

## Measured, per stage

The table between the markers is written by `make costs` from `runs.jsonl`: one line per model call, with the latency the pipeline measured and, for GPU work, the minutes the notebook measured itself. It is empty until real calls have been made.

<!-- costs:begin (written by `python -m pipeline costs --write`) -->
| Stage | Provider | Model | Calls | Failed | Total latency (s) | Mean latency (s) | GPU minutes | List price (USD) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| smoke | cloudflare | `@cf/black-forest-labs/flux-2-klein-4b` | 1 | 0 | 4.5 | 4.5 | 0.0 | n/a |
| smoke | gemini | `gemini-3.8-flash` | 2 | 0 | 180.0 | 90.0 | 0.0 | n/a |
| smoke | gemini | `gemini-3.8-flash-tts` | 1 | 0 | 4.7 | 4.7 | 0.0 | n/a |
| **Total** | | | 4 | 0 | 189.2 | | 0.0 | n/a |

Source: `runs.jsonl`, 4 model calls. 4 call(s) have no checked price in `pricing.json`, so their list price is n/a.
<!-- costs:end -->

The list-price column answers "what would the same calls cost without the free tier". It uses `pricing.json`, where a price is only filled in from the provider's own pricing page, with the date. Until then it shows n/a.

## Free-tier limits I actually found

The brief warns that free tiers change often. One row per provider, filled in from what I saw, not from what a blog said.

| Provider | Limit as advertised | What I actually hit | Date |
|---|---|---|---|
| Gemini API (text) | | No limit hit in 2 smoke calls, both answered on the first attempt. Slow: 138.4 s and 41.6 s for a one-word answer (8 tokens in, 1 out). | 2026-11-25 |
| Gemini API (speech) | | No limit hit in 1 smoke call, answered on the first attempt in 4.7 s for a one-word line. | 2026-11-25 |
| Cloudflare Workers AI | 10,000 neurons a day (to confirm) | No limit hit in 1 smoke call: one 512 x 512 image in 4.5 s on the first attempt, seed accepted. | 2026-11-25 |
| Kaggle GPU | about 30 hours a week (to confirm) | | |

## GPU time

To fill in from the ingested job results: seconds per clip, clips per hour, peak memory per clip, and how many attempts failed. The run log holds all of it (`provider: kaggle`).

## Frontier comparison

No frontier access so far. If the cohort's organisation key opens, the plan is one shot generated both ways, with cost and latency side by side and a blind preference test (`python -m pipeline blindtest`).
