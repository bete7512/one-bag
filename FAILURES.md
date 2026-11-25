# Failures

What broke, what was tried, what fixed it. An entry is added the moment something breaks, while the error text is still on the screen.

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

1. The same stage again, after two changes to the pipeline: waits of 10, 30 and 90 seconds between attempts, and the judge made optional so a failed score no longer stops the stage. The run finished this time, without the scores: 12 more attempts in twenty minutes, none answered (run `20261125T105827Z-7dbbde`). The last two failed differently: `HTTP 429 You exceeded your current quota`.
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

Status: open. The likely cause is an account whose phone number is not verified: Kaggle gives such accounts no internet in notebooks. To be confirmed by verifying the phone and running the same job again.

What the run did prove: Kaggle's Python is 3.13 (the job script builds ACE-Step's own environment for that reason), and a dataset is mounted at `/kaggle/input/datasets/<owner>/<name>/`, not at `/kaggle/input/<name>/`. The job scripts search for their manifest instead of assuming a path, so this cost nothing.

### F03  The Claude API key had no credit  (25 Nov 2026)

Stage and model: experiment E17, the keyframe judge on `claude-opus-5-5`, through the Anthropic SDK.

What happened: each of the 12 calls was refused at once:

```
HTTP 400 {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.'}}
```

The key itself was accepted: the refusal is about billing, not about who is calling. The 12 attempts are in `runs.jsonl` under run `20261125T120616Z-8a8230`, each with `cost_usd` 0. A rejected request is not retried, so nothing was spent on waiting either.

What was done: nothing was changed to get around it. The comparison of the two judge models stays unmeasured, and E17 says so. The first step of that experiment, the new question on the free model, did run and is what the pipeline uses. `models.judge` in the storyboard stays unset, so the judge is the free model.

Status: open. With credit on the account, `python experiments/e17_judges.py` runs the missing step: it skips every answer it already has.

## From the offline build (coding agent, 25 Nov 2026)

These happened while the pipeline was first written, before any real model call. They are kept because each one changed the code.

### B1  The build machine could not reach any model provider
What happened: the sandbox the coding agent worked in could reach GitHub and PyPI only. Requests to the Gemini API, Cloudflare, Kaggle and Hugging Face all failed to connect.
What was done: every provider got an offline stand-in (`--mock`): beeps the length of the line for speech, labelled colour cards for images, fixed answers for text. The whole pipeline and the tests run on them. Mock output goes to `outputs_mock/` and a separate log, so it can never be mistaken for a real run.
What it means: the code for real calls follows the provider docs but had not touched a real model when it was written. The README status table tracks what has since.

### B2  The speech API in the docs was not the one expected
What happened: the Gemini speech page (25 Nov 2026) documents the Interactions API (`/v1beta/interactions`, style as a `speech_metadata` annotation, audio in `steps[].content[]`), not the older `generateContent` call with `speechConfig`.
What was done: the client was written for the documented call, and the response parser searches the JSON for the audio wherever it sits, so either shape is read.
Still open: no seed parameter is documented for speech, so two takes of one line may differ. Logged as `seed: null`.

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
