"""Wan 2.2 TI2V-5B image-to-video job. Runs on a Kaggle GPU (T4 x2) with internet on.

How it is started: `python -m pipeline kaggle shots` uploads the job folder (this script,
manifest.json and the keyframes) as a private dataset, pushes a small launcher that runs this file,
waits, downloads results.zip and ingests it. By hand it is one notebook cell:
    !python /kaggle/input/heritage-shots-job/wan22_i2v.py

Input:  manifest.json, written by the shots stage, and the keyframe of every clip to make.
Output: /kaggle/working/results/ with one mp4 per job plus results.json, and results.zip.

Memory is the problem this file is built around. The model card asks for a 24 GB GPU and a T4 has
16 GB. What is done about it, each point from the Diffusers and PyTorch documentation as read on
25 Nov 2026:

* The transformer runs in float16 on a T4. A T4 has no fast attention path for bfloat16, and the
  fallback works in float32, which needs several GB more than the card has. Newer GPUs keep the
  documented bfloat16. Float16 is not the documented setting for this model, so every clip is
  checked for blank or not-a-number frames, and the data type is written into results.json.
* The prompt is encoded first and the text encoder is then moved off the GPU, before the keyframe
  is encoded and the transformer loaded. Left to itself, the pipeline keeps the text encoder there.
* The storyboard's `video` settings start small (480x832 area, 81 frames), decoding is tiled, and
  the peak memory of every clip is recorded, so the next settings come from a measurement.

results.json is rewritten after every clip. If the session dies half way, what finished is kept.
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

SCRATCH = Path(os.environ.get("SCRATCH_DIR", "/kaggle/temp"))  # not part of the notebook's saved output
DIFFUSERS = "diffusers==0.43.0"  # pinned: tiled decoding for this VAE needs 0.36 or newer


def find_job(stage: str) -> Path:
    if os.environ.get("JOB_DIR"):
        return Path(os.environ["JOB_DIR"])
    for manifest in sorted(Path("/kaggle/input").rglob("manifest.json")):
        if json.loads(manifest.read_text(encoding="utf-8")).get("stage") == stage:
            return manifest.parent
    raise SystemExit(f"No {stage} job found. Attach the job folder as a dataset, or set JOB_DIR.")


def find_input(job: Path, name: str) -> Path:
    """The keyframe may sit in inputs/ or next to the manifest, depending on how the folder was uploaded."""
    for path in (job / "inputs" / name, job / name, *sorted(job.rglob(name))):
        if path.exists():
            return path
    raise FileNotFoundError(f"{name} is not in the job folder {job}")


def main() -> None:
    job = find_job("shots")
    manifest = json.loads((job / "manifest.json").read_text(encoding="utf-8"))
    settings = manifest["settings"]
    out = Path(os.environ.get("OUT_DIR", "/kaggle/working/results"))
    out.mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(SCRATCH / "hf"))  # the model is tens of GB: keep it off the small output disk
    print(f"scratch disk free: {shutil.disk_usage(SCRATCH).free / 2**30:.0f} GB", flush=True)

    subprocess.run([sys.executable, "-m", "pip", "install", "-q", DIFFUSERS, "transformers", "accelerate", "ftfy",
                    "imageio", "imageio-ffmpeg"], check=True)
    import numpy as np
    import torch
    from diffusers import AutoencoderKLWan, WanImageToVideoPipeline, WanTransformer3DModel
    from diffusers.utils import export_to_video, load_image

    gpus = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    print("GPUs:", gpus or "none: this job needs a GPU", flush=True)
    if not gpus:
        raise SystemExit("No GPU in this session. Switch the accelerator to GPU T4 x2 and run again.")
    dtype = torch.bfloat16 if torch.cuda.get_device_capability(0)[0] >= 8 else torch.float16
    t_load = time.time()
    vae = AutoencoderKLWan.from_pretrained(manifest["model"], subfolder="vae", torch_dtype=torch.float32)
    transformer = WanTransformer3DModel.from_pretrained(manifest["model"], subfolder="transformer", torch_dtype=dtype)
    pipe = WanImageToVideoPipeline.from_pretrained(manifest["model"], vae=vae, transformer=transformer, torch_dtype=torch.bfloat16)
    pipe.enable_model_cpu_offload()
    for saver in ("enable_tiling", "enable_slicing"):  # cheaper decoding, where this VAE supports it
        try:
            getattr(pipe.vae, saver)()
        except Exception as e:  # noqa: BLE001
            print(f"vae.{saver} not available: {type(e).__name__}", flush=True)
    load_s = round(time.time() - t_load, 1)
    print(f"model loaded in {load_s}s, transformer in {dtype}", flush=True)

    report = {"stage": "shots", "job_id": uuid.uuid4().hex, "job_created": manifest.get("created"),
              "model": manifest["model"], "gpu": ", ".join(gpus),
              "settings": settings, "model_load_s": load_s, "results": []}
    for n, j in enumerate(manifest["jobs"], start=1):
        rec = {"unit": j["unit"], "key": j["key"], "fingerprint": j["fingerprint"], "seed": j["seed"],
               "params": {**{k: settings[k] for k in ("max_area", "num_frames", "steps", "guidance")}, "dtype": str(dtype).replace("torch.", "")}}
        t0 = time.time()
        for i in range(torch.cuda.device_count()):
            torch.cuda.reset_peak_memory_stats(i)
        try:
            image = load_image(str(find_input(job, j["keyframe"])))
            aspect = image.height / image.width
            mod = pipe.vae_scale_factor_spatial * pipe.transformer.config.patch_size[1]
            height = round(np.sqrt(settings["max_area"] * aspect)) // mod * mod
            width = round(np.sqrt(settings["max_area"] / aspect)) // mod * mod
            with torch.no_grad():
                embeds, negative_embeds = pipe.encode_prompt(prompt=j["prompt"], negative_prompt=j.get("negative") or None,
                                                             do_classifier_free_guidance=settings["guidance"] > 1, max_sequence_length=512)
            pipe.maybe_free_model_hooks()  # the text encoder leaves the GPU before anything else is loaded
            frames = pipe(image=image.resize((width, height)), prompt_embeds=embeds, negative_prompt_embeds=negative_embeds,
                          height=height, width=width, num_frames=settings["num_frames"],
                          num_inference_steps=settings["steps"], guidance_scale=settings["guidance"],
                          generator=torch.Generator(device="cpu").manual_seed(j["seed"])).frames[0]
            pixels = np.asarray(frames, dtype=np.float32)
            if not np.isfinite(pixels).all() or float(pixels.std()) < 0.01:
                raise RuntimeError(f"the clip is blank or not a number ({dtype}): this data type does not suit the model on this GPU")
            name = f"{j['unit']}__{j['key']}.mp4"
            export_to_video(frames, str(out / name), fps=settings.get("fps", 24))
            rec.update(status="ok", file=name)
            rec["params"].update(width=width, height=height)
        except Exception as e:  # noqa: BLE001  one failed clip must not lose the others
            traceback.print_exc()
            rec.update(status="error", error=f"{type(e).__name__}: {e}"[:400])
            pipe.maybe_free_model_hooks()  # after an error nothing is moved off the GPU by itself
            torch.cuda.empty_cache()
        rec["latency_s"] = round(time.time() - t0, 1)
        rec["peak_mem_gb"] = round(max(torch.cuda.max_memory_allocated(i) for i in range(torch.cuda.device_count())) / 2**30, 2)
        report["results"].append(rec)
        (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{n}/{len(manifest['jobs'])}] {j['unit']}: {rec['status']} in {rec['latency_s']}s, peak {rec.get('peak_mem_gb')} GB", flush=True)

    archive = out.parent / "results.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as z:
        for f in sorted(p for p in out.iterdir() if p.is_file()):
            z.write(f, f.name)
    print("done:", archive, flush=True)


if __name__ == "__main__":
    main()
