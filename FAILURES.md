# Failures

What broke, what was tried, what fixed it. An entry is added the moment something breaks, while the error text is still on the screen.

## From real runs

None yet. Template:

```
### F__  <what broke>  (date)
Stage and model:
What happened:       (the exact error, and the runs.jsonl line)
What I tried:        (each attempt, in order)
What fixed it, or the workaround:
What it cost:        (time, quota, GPU minutes)
What I would do differently:
```

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
