"""ACE-Step 1.5 score candidates. Runs on a Kaggle GPU with internet on.

How it is started: `python -m pipeline kaggle music` uploads the job folder (this script and
manifest.json) as a private dataset, pushes a small launcher that runs this file, waits, downloads
results.zip and ingests it. By hand it is one notebook cell:
    !python /kaggle/input/heritage-music-job/acestep_music.py

Input:  manifest.json, written by the music stage: the caption, tempo, length, and one job per seed.
Output: /kaggle/working/results/ with one wav per seed plus results.json, and results.zip.

One candidate per seed, same caption, so the candidates differ only by the seed. The planner
language model is switched off (thinking=False): the storyboard already gives tempo and length,
and the caption is used exactly as written, which keeps the experiment readable.

Three things follow the upstream project as read on 25 Nov 2026 (docs/en/INFERENCE.md, pyproject.toml
and cli.py of ACE-Step-1.5), and are the reason for the shape of this file:

* ACE-Step pins its own Python (3.11 or 3.12) and its own torch build, and Kaggle's Python is newer.
  So the script first builds the project's locked environment with `uv sync`, then runs itself
  again inside it.
* An instrumental track is asked for with the lyrics "[Instrumental]". The `instrumental` flag
  alone is not read by the generation code.
* `initialize_service` reports a failed load in its return value instead of raising.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import uuid
import zipfile
from pathlib import Path

REPO_URL = "https://github.com/ACE-Step/ACE-Step-1.5.git"
SCRATCH = Path(os.environ.get("SCRATCH_DIR", "/kaggle/temp"))  # not part of the notebook's saved output


def find_job(stage: str) -> Path:
    if os.environ.get("JOB_DIR"):
        return Path(os.environ["JOB_DIR"])
    for manifest in sorted(Path("/kaggle/input").rglob("manifest.json")):
        if json.loads(manifest.read_text(encoding="utf-8")).get("stage") == stage:
            return manifest.parent
    raise SystemExit(f"No {stage} job found. Attach the job folder as a dataset, or set JOB_DIR.")


def enter_project_environment(repo: Path) -> None:
    """Build ACE-Step's own environment, then run this script again inside it. Returns only inside it."""
    if os.environ.get("ACESTEP_ENV") == "1":
        return
    if not repo.exists():
        repo.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(1, 4):  # the network of a fresh session can take a moment
            if subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(repo)]).returncode == 0:
                break
            if attempt == 3:
                raise SystemExit("Cannot reach github.com from this session. Is internet switched on for the notebook? "
                                 "Kaggle only allows it for accounts with a verified phone number.")
            time.sleep(20)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "uv"], check=True)
    t0 = time.time()
    if subprocess.run([sys.executable, "-m", "uv", "sync", "--frozen"], cwd=repo).returncode != 0:
        subprocess.run([sys.executable, "-m", "uv", "sync"], cwd=repo, check=True)  # no lock file upstream: resolve now
    print(f"environment built in {time.time() - t0:.0f}s", flush=True)
    python = repo / ".venv" / "bin" / "python"
    again = subprocess.run([str(python), os.path.abspath(__file__)], env={**os.environ, "ACESTEP_ENV": "1"})
    raise SystemExit(again.returncode)


def main() -> None:
    job = find_job("music")
    manifest = json.loads((job / "manifest.json").read_text(encoding="utf-8"))
    s = manifest["settings"]
    out = Path(os.environ.get("OUT_DIR", "/kaggle/working/results"))
    repo = Path(os.environ.get("ACESTEP_DIR", str(SCRATCH / "ACE-Step-1.5")))
    enter_project_environment(repo)
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(repo))

    import torch
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler

    gpus = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    print("GPUs:", gpus or "none: this job needs a GPU", flush=True)
    if not gpus:
        raise SystemExit("No GPU in this session. Switch the accelerator to GPU T4 x2 and run again.")
    t_load = time.time()
    dit = AceStepHandler()
    status, loaded = dit.initialize_service(project_root=str(repo), config_path=manifest["model"], device="cuda")
    if not loaded:
        raise SystemExit(f"ACE-Step did not load: {status}")
    llm = LLMHandler()  # not initialised on purpose: thinking=False below means the planner is not used
    load_s = round(time.time() - t_load, 1)
    print(f"model loaded in {load_s}s", flush=True)

    report = {"stage": "music", "job_id": uuid.uuid4().hex, "job_created": manifest.get("created"),
              "model": manifest["model"], "gpu": ", ".join(gpus),
              "settings": s, "model_load_s": load_s, "results": []}
    for n, j in enumerate(manifest["jobs"], start=1):
        rec = {"unit": j["unit"], "key": j["key"], "fingerprint": j["fingerprint"], "seed": j["seed"],
               "params": {"duration_s": s["duration_s"], "bpm": s.get("bpm"), "keyscale": s.get("keyscale", ""),
                          "inference_steps": 8, "shift": 3.0, "thinking": False, "lyrics": "[Instrumental]"}}
        t0 = time.time()
        torch.cuda.reset_peak_memory_stats()
        try:
            params = GenerationParams(caption=s["caption"], lyrics="[Instrumental]", instrumental=True, duration=float(s["duration_s"]),
                                      bpm=s.get("bpm"), keyscale=s.get("keyscale") or "", inference_steps=8, shift=3.0,
                                      seed=j["seed"], thinking=False)
            config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[j["seed"]], audio_format="wav")
            scratch = SCRATCH / f"acestep_{j['unit']}"
            result = generate_music(dit, llm, params, config, save_dir=str(scratch))
            if not result.success:
                raise RuntimeError(str(result.error))
            name = f"{j['unit']}__{j['key']}.wav"
            shutil.copy2(result.audios[0]["path"], out / name)
            shutil.rmtree(scratch, ignore_errors=True)
            rec.update(status="ok", file=name)
        except Exception as e:  # noqa: BLE001  one failed candidate must not lose the others
            traceback.print_exc()
            rec.update(status="error", error=f"{type(e).__name__}: {e}"[:400])
        rec["latency_s"] = round(time.time() - t0, 1)
        rec["peak_mem_gb"] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
        report["results"].append(rec)
        (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{n}/{len(manifest['jobs'])}] {j['unit']} (seed {j['seed']}): {rec['status']} in {rec['latency_s']}s", flush=True)

    archive = out.parent / "results.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as z:
        for f in sorted(p for p in out.iterdir() if p.is_file()):
            z.write(f, f.name)
    print("done:", archive, flush=True)


if __name__ == "__main__":
    main()
