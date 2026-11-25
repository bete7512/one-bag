# Walkthrough video: outline (five minutes at most)

Record the screen with your voice. Rehearse once with a timer.

| Time | Show | Say |
|---|---|---|
| 0:00 | The film playing for ten seconds | What it is, who it is for, in two sentences. |
| 0:20 | `storyboard.json`, one shot | One file is the contract: the reason for the shot, its prompt and seed, its narration, its motion. |
| 0:50 | The diagram in `ARCHITECTURE.md` | Six stages. Each reads the storyboard and writes its own outputs. Speech and images are API calls, video and music are GPU jobs that come back through `ingest`, assembly is FFmpeg. |
| 1:40 | `pipeline/core.py`, the `Unit` class and `run_units` | Every unit has a fingerprint of its inputs. Same fingerprint, cache hit. That is why one changed shot costs one shot. |
| 2:20 | "One hard decision" in `ARCHITECTURE.md` | Two aspect ratios from one GPU budget: the options, what you chose, what it cost. Use your own words. |
| 3:00 | **Live.** Edit one narration line of one shot in `storyboard.json` and save | "I am changing one line of shot s04." |
| 3:15 | `python -m pipeline plan` | The plan names the one line and the units that depend on it. No model is called. |
| 3:35 | `python -m pipeline film` | Everything prints HIT except that shot. Pause the recording while it runs if you need to. |
| 4:10 | `tail -n 3 runs.jsonl` | Three new model calls: the subtitle checked against the new line, the line spoken, and the listening check. Nothing else. |
| 4:30 | `FAILURES.md`, one entry | One thing that broke and what you did about it. |
| 4:50 | The final-cut check output | Length, both ratios, loudness, end card: measured, not assumed. |

For the live part you may change a keyframe prompt instead. Then the new calls are that shot's candidates and their judge calls. You do not need to rerun Wan on camera: showing the log with only the new calls counts.
