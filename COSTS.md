# Costs

Money spent: to fill in after the real runs (the plan is zero, on free tiers). The real limits are quota and GPU time, so this file is about measured time.

## Measured, per stage

The table between the markers is written by `make costs` from `runs.jsonl`: one line per model call, with the latency the pipeline measured and, for GPU work, the minutes the notebook measured itself. It is empty until real calls have been made.

<!-- costs:begin (written by `python -m pipeline costs --write`) -->
<!-- costs:end -->

The list-price column answers "what would the same calls cost without the free tier". It uses `pricing.json`, where a price is only filled in from the provider's own pricing page, with the date. Until then it shows n/a.

## Free-tier limits I actually found

The brief warns that free tiers change often. One row per provider, filled in from what I saw, not from what a blog said.

| Provider | Limit as advertised | What I actually hit | Date |
|---|---|---|---|
| Gemini API (text) | | | |
| Gemini API (speech) | | | |
| Cloudflare Workers AI | 10,000 neurons a day (to confirm) | | |
| Kaggle GPU | about 30 hours a week (to confirm) | | |

## GPU time

To fill in from the ingested job results: seconds per clip, clips per hour, peak memory per clip, and how many attempts failed. The run log holds all of it (`provider: kaggle`).

## Frontier comparison

No frontier access so far. If the cohort's organisation key opens, the plan is one shot generated both ways, with cost and latency side by side and a blind preference test (`python -m pipeline blindtest`).
