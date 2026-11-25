"""ACE-Step 1.5 score candidates. Written for a Kaggle or Colab notebook with a GPU and internet on.

STATUS: written from the docs, never run on a GPU by its author. It follows docs/en/INFERENCE.md of
ACE-Step-1.5 as read on 25 Nov 2026. Treat the first run as an experiment and write what happens
into EXPERIMENTS.md and FAILURES.md.

Input:  the job folder made by `python -m pipeline film` (manifest.json), attached as a dataset.
Output: /kaggle/working/results/ with one wav per seed plus results.json, and results.zip.
        Download results.zip, then on your machine: python -m pipeline ingest music results.zip

One candidate per seed, same caption, so the candidates differ only by the seed. The planner
language model is switched off (thinking=False): the storyboard already gives tempo and length,
and the caption is used exactly as written, which keeps the experiment readable.
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


def find_job(stage: str) -> Path:
    if os.environ.get("JOB_DIR"):
        return Path(os.environ["JOB_DIR"])
    for manifest in sorted(Path("/kaggle/input").rglob("manifest.json")):
        if json.loads(manifest.read_text(encoding="utf-8")).get("stage") == stage:
            return manifest.parent
    raise SystemExit(f"No {stage} job found. Attach the job folder as a dataset, or set JOB_DIR.")


def main() -> None:
    job = find_job("music")
    manifest = json.loads((job / "manifest.json").read_text(encoding="utf-8"))
    s = manifest["settings"]
    out = Path(os.environ.get("OUT_DIR", "/kaggle/working/results"))
    out.mkdir(parents=True, exist_ok=True)
    repo = Path(os.environ.get("ACESTEP_DIR", "/kaggle/working/ACE-Step-1.5"))
    if not repo.exists():
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(repo)], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", str(repo)], check=True)
    sys.path.insert(0, str(repo))

    import torch
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler

    gpus = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    print("GPUs:", gpus or "none: this job needs a GPU")
    t_load = time.time()
    dit = AceStepHandler()
    dit.initialize_service(project_root=str(repo), config_path=manifest["model"], device="cuda")
    llm = LLMHandler()  # not initialised on purpose: thinking=False below means the planner is not used
    load_s = round(time.time() - t_load, 1)

    report = {"stage": "music", "job_id": uuid.uuid4().hex, "model": manifest["model"], "gpu": ", ".join(gpus),
              "settings": s, "model_load_s": load_s, "results": []}
    for n, j in enumerate(manifest["jobs"], start=1):
        rec = {"unit": j["unit"], "key": j["key"], "fingerprint": j["fingerprint"], "seed": j["seed"],
               "params": {"duration_s": s["duration_s"], "bpm": s.get("bpm"), "keyscale": s.get("keyscale", ""),
                          "inference_steps": 8, "shift": 3.0, "thinking": False}}
        t0 = time.time()
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        try:
            params = GenerationParams(caption=s["caption"], instrumental=True, duration=float(s["duration_s"]),
                                      bpm=s.get("bpm"), keyscale=s.get("keyscale") or "", inference_steps=8, shift=3.0,
                                      seed=j["seed"], thinking=False)
            config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[j["seed"]], audio_format="wav")
            scratch = out / f"scratch_{j['unit']}"
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
        if torch.cuda.is_available():
            rec["peak_mem_gb"] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
        report["results"].append(rec)
        (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{n}/{len(manifest['jobs'])}] {j['unit']} (seed {j['seed']}): {rec['status']} in {rec['latency_s']}s")

    archive = out.parent / "results.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as z:
        for f in sorted(p for p in out.iterdir() if p.is_file()):
            z.write(f, f.name)
    print("done:", archive)


if __name__ == "__main__":
    main()
