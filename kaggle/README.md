# GPU jobs on Kaggle

Wan 2.2 (moving shots) and ACE-Step 1.5 (score) need a GPU. The pipeline prepares the job, Kaggle runs it on a free GPU, and the results come back into the cache.

## From the command line

Once:

1. Create a Kaggle account and verify its phone number. Kaggle gives notebooks no internet without it, and the jobs download their models.
2. Open kaggle.com/settings/api, press "Generate New Token", and put the text into `.env` as `KAGGLE_API_TOKEN=...`.
3. Install the tool into the project environment: `.venv/bin/pip install kaggle six`. Version 2.2.5 imports `six` without installing it.

Each time:

```
python -m pipeline stage music        # writes the job folder for what is missing from the cache
python -m pipeline kaggle run music   # upload, push, wait, fetch, ingest
python -m pipeline film               # uses what came back
```

`kaggle run` does four things, and each can be watched on kaggle.com:

1. It uploads the job folder (`manifest.json`, the job script, the keyframes) as a private dataset, `heritage-music-job` or `heritage-shots-job`.
2. It pushes a private script, `heritage-music` or `heritage-shots`, on a GPU T4 x2 with internet on. The script is a small launcher that runs the job script from the dataset, and only for the job it was pushed for.
3. It polls until the run ends.
4. It downloads the output and ingests it: every file is checked against its cache key and copied into the cache, and `runs.jsonl` gets one line per file with the seconds and the peak GPU memory that the job measured.

`python -m pipeline kaggle run shots --no-wait` returns after the push. Later: `kaggle status shots`, `kaggle logs shots`, `kaggle fetch shots`.

## By hand, in a notebook

1. On Kaggle: **Datasets, New Dataset**, upload `outputs/music/kaggle_job.zip` (or the one in `outputs/shots/`). Name it `heritage-music-job`.
2. **Code, New Notebook.** Add the dataset as an input. In the settings choose **Accelerator: GPU T4 x2** and switch **Internet** on.
3. Find where the dataset is mounted and run the script from there in one cell:
   ```
   !find /kaggle/input -name acestep_music.py
   !python /kaggle/input/datasets/<your-name>/heritage-music-job/acestep_music.py
   ```
4. Download `/kaggle/working/results.zip` from the notebook's output, then `python -m pipeline ingest music results.zip`.

## What to expect

- Kaggle runs Python 3.13. ACE-Step pins Python 3.11 or 3.12 and its own torch build, so its job script first builds the project's own environment with `uv`, then runs itself inside it.
- A dataset is mounted at `/kaggle/input/datasets/<owner>/<name>/`. The job scripts search for their manifest and do not assume a path.
- The first video run downloads tens of GB of model files. That time is in `model_load_s` in `results.json`, apart from the per-clip latency.
- The Wan model card asks for 24 GB and a T4 has 16 GB. The `video` settings in `storyboard.json` are a draft size for that reason, and the transformer runs in float16 on a T4. If a clip runs out of memory, lower `num_frames` first, then `max_area`. Each change gives new cache keys, so nothing old is overwritten.
- `results.json` is rewritten after every clip. If the session times out, fetch what is there.
- A change to a shot's keyframe, motion prompt or seed makes a new job for that shot only.
- The free quota is 30 GPU hours a week. `kaggle quota` shows what is left.

What happened on the real runs is in `FAILURES.md` and `COSTS.md`.
