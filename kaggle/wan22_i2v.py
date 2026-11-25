"""Wan 2.2 TI2V-5B image-to-video job. Written for a Kaggle notebook with GPU T4 x2 and internet on.

STATUS: written from the docs, never run on a GPU by its author. It follows the Diffusers usage for
Wan-AI/Wan2.2-TI2V-5B-Diffusers as read on 25 Nov 2026. Treat the first run as an experiment and
write what happens into EXPERIMENTS.md and FAILURES.md.

Input:  the job folder made by `python -m pipeline film` (manifest.json + inputs/), attached to the
        notebook as a dataset. Set JOB_DIR if it is somewhere else.
Output: /kaggle/working/results/ with one mp4 per job plus results.json, and results.zip.
        Download results.zip, then on your machine: python -m pipeline ingest shots results.zip

Memory: the model card asks for a 24 GB GPU and a T4 has 16 GB. The denoising fits; decoding the
finished clip is what runs out of memory at 720p. So the storyboard's `video` settings start small
(480x832 area, 81 frames), the model parts are moved to the GPU one at a time, and the peak memory
of every clip is recorded, so the next settings come from a measurement and not a guess.

results.json is rewritten after every clip. If the session dies half way, what finished is kept.
"""
import json
import os
import subprocess
import sys
import time
import traceback
import uuid
import zipfile
from pathlib import Path


def find_job(stage: str) -> Path:
    if os.environ.get("JOB_DIR"):
        return Path(os.environ["JOB_DIR"])
    for manifest in sorted(Path("/kaggle/input").rglob("manifest.json")):
        if json.loads(manifest.read_text(encoding="utf-8")).get("stage") == stage:
            return manifest.parent
    raise SystemExit(f"No {stage} job found. Attach the job folder as a dataset, or set JOB_DIR.")


def main() -> None:
    job = find_job("shots")
    manifest = json.loads((job / "manifest.json").read_text(encoding="utf-8"))
    settings = manifest["settings"]
    out = Path(os.environ.get("OUT_DIR", "/kaggle/working/results"))
    out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", "/kaggle/temp/hf")  # the model is tens of GB: keep it off the small output disk

    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "diffusers", "transformers", "accelerate", "ftfy",
                    "imageio", "imageio-ffmpeg"], check=True)
    import numpy as np
    import torch
    from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
    from diffusers.utils import export_to_video, load_image

    gpus = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    print("GPUs:", gpus or "none: this job needs a GPU")
    t_load = time.time()
    vae = AutoencoderKLWan.from_pretrained(manifest["model"], subfolder="vae", torch_dtype=torch.float32)
    pipe = WanImageToVideoPipeline.from_pretrained(manifest["model"], vae=vae, torch_dtype=torch.bfloat16)
    pipe.enable_model_cpu_offload()  # one part of the model on the GPU at a time
    for saver in ("enable_tiling", "enable_slicing"):  # cheaper decoding, where this VAE supports it
        try:
            getattr(pipe.vae, saver)()
        except Exception as e:  # noqa: BLE001
            print(f"vae.{saver} not available: {type(e).__name__}")
    load_s = round(time.time() - t_load, 1)
    print(f"model loaded in {load_s}s")

    report = {"stage": "shots", "job_id": uuid.uuid4().hex, "model": manifest["model"], "gpu": ", ".join(gpus),
              "settings": settings, "model_load_s": load_s, "results": []}
    for n, j in enumerate(manifest["jobs"], start=1):
        rec = {"unit": j["unit"], "key": j["key"], "fingerprint": j["fingerprint"], "seed": j["seed"],
               "params": {k: settings[k] for k in ("max_area", "num_frames", "steps", "guidance")}}
        t0 = time.time()
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                torch.cuda.reset_peak_memory_stats(i)
        try:
            image = load_image(str(job / "inputs" / j["keyframe"]))
            aspect = image.height / image.width
            mod = pipe.vae_scale_factor_spatial * pipe.transformer.config.patch_size[1]
            height = round(np.sqrt(settings["max_area"] * aspect)) // mod * mod
            width = round(np.sqrt(settings["max_area"] / aspect)) // mod * mod
            frames = pipe(image=image.resize((width, height)), prompt=j["prompt"], negative_prompt=j.get("negative") or None,
                          height=height, width=width, num_frames=settings["num_frames"],
                          num_inference_steps=settings["steps"], guidance_scale=settings["guidance"],
                          generator=torch.Generator(device="cpu").manual_seed(j["seed"])).frames[0]
            name = f"{j['unit']}__{j['key']}.mp4"
            export_to_video(frames, str(out / name), fps=settings.get("fps", 24))
            rec.update(status="ok", file=name)
            rec["params"].update(width=width, height=height)
        except Exception as e:  # noqa: BLE001  one failed clip must not lose the others
            traceback.print_exc()
            rec.update(status="error", error=f"{type(e).__name__}: {e}"[:400])
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        rec["latency_s"] = round(time.time() - t0, 1)
        if torch.cuda.is_available():
            rec["peak_mem_gb"] = round(max(torch.cuda.max_memory_allocated(i) for i in range(torch.cuda.device_count())) / 2**30, 2)
        report["results"].append(rec)
        (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{n}/{len(manifest['jobs'])}] {j['unit']}: {rec['status']} in {rec['latency_s']}s, peak {rec.get('peak_mem_gb')} GB")

    archive = out.parent / "results.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as z:
        for f in sorted(out.iterdir()):
            z.write(f, f.name)
    print("done:", archive)


if __name__ == "__main__":
    main()
