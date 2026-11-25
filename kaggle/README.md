# GPU jobs on Kaggle

Wan 2.2 (moving shots) and ACE-Step 1.5 (score) need a GPU. The pipeline prepares the job, a Kaggle notebook runs it, and the results come back into the cache.

Both job scripts were written from the model docs and had not been run on a GPU when they were written. Treat the first run as an experiment, and write down what happens.

## Once

1. Create a Kaggle account and verify it by phone (needed for GPU and internet in notebooks).

## Each time

1. On your machine: `python -m pipeline film`. It writes a job bundle for every clip or candidate that is not in the cache yet:
   - `outputs/shots/kaggle_job.zip` for Wan 2.2
   - `outputs/music/kaggle_job.zip` for ACE-Step
2. On Kaggle: **Datasets, New Dataset**, upload the zip. Kaggle unpacks it. Give it a name such as `heritage-shots-job`.
3. **Code, New Notebook.** Add the dataset as an input. In the settings choose **Accelerator: GPU T4 x2** and switch **Internet** on.
4. In one cell, run the script that is inside the dataset:
   ```
   !python /kaggle/input/heritage-shots-job/wan22_i2v.py
   ```
   For music: `!python /kaggle/input/heritage-music-job/acestep_music.py`
   Use **Save Version, Save and Run All** to let it run in the background and keep the output.
5. Download `/kaggle/working/results.zip` from the notebook's output.
6. On your machine:
   ```
   python -m pipeline ingest shots results.zip      # or: ingest music results.zip
   python -m pipeline film
   ```
   `ingest` checks every file against its cache key, copies it into the cache and writes one line per clip into `runs.jsonl` with the seconds and peak GPU memory that the notebook measured.

## What to expect

- The first video run downloads tens of GB of model files. That time is in `model_load_s` in `results.json`, apart from the per-clip latency.
- The model card asks for 24 GB and a T4 has 16 GB. The default settings in `storyboard.json` (`video`) are a draft size for that reason. If a clip runs out of memory, lower `num_frames` first, then `max_area`. Each change gives new cache keys, so nothing old is overwritten.
- `results.json` is rewritten after every clip. If the session times out, download what is there and ingest it.
- A change to a shot's keyframe, motion prompt or seed makes a new job for that shot only.

## With the Kaggle command line (optional)

`kernel-metadata.json` for a script kernel needs at least: `id`, `title`, `code_file`, `language: "python"`, `kernel_type: "script"`, `enable_gpu: "true"`, `enable_internet: "true"`, `machine_shape: "NvidiaTeslaT4"` and `dataset_sources`. Then `kaggle kernels push -p <folder>`, `kaggle kernels status <id>` and `kaggle kernels output <id> -p <folder>`. This path is not automated here, because it could not be tested.
