"""GPU jobs that run somewhere else (a Kaggle notebook) and come back as files.

Wan 2.2 and ACE-Step need a GPU this machine does not have. So the pipeline does two things:

* `export_job` writes outputs/<stage>/kaggle_job/: a manifest of exactly what to generate (one
  entry per cache miss, with its cache key and the fingerprint the key was made from), the input
  files and the job script. The same folder is zipped, ready to attach to a notebook.
* `ingest` reads the job's results.json, checks every key against its fingerprint, puts the files
  into the cache and writes one run-log line per generation, with the latency and GPU memory that
  the job measured itself.

After an ingest the next run finds the files in the cache and uses them. Nothing else changes.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Callable

from .core import Cache, Ctx, PipelineError, Unit, log_run, media_info, now, sha


def export_job(ctx: Ctx, stage: str, model: str, settings: dict, jobs: list[dict], inputs: list[Path], script: str) -> Path:
    job_dir = ctx.out / stage / "kaggle_job"
    if job_dir.exists():
        shutil.rmtree(job_dir)
    (job_dir / "inputs").mkdir(parents=True)
    for src in inputs:
        shutil.copy2(src, job_dir / "inputs" / src.name)
    shutil.copy2(ctx.root / "kaggle" / script, job_dir / script)
    manifest = {"stage": stage, "created": now(), "model": model, "settings": settings, "jobs": jobs}
    (job_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    archive = shutil.make_archive(str(job_dir), "zip", job_dir)
    ctx.say(f"  [{stage}] {len(jobs)} GPU job(s) written to {Path(archive).relative_to(ctx.root)}. See kaggle/README.md, then run: "
            f"python -m pipeline ingest {stage} <results.zip>")
    return Path(archive)


def ingest(ctx: Ctx, stage: str, src: Path, ext: str, convert: Callable[[Path, Path], None] | None = None) -> int:
    """Bring finished GPU work into the cache. Returns how many files were accepted."""
    src = Path(src)
    if not src.exists():
        raise PipelineError(f"{src} does not exist")
    base = src
    if src.is_file():
        base = ctx.out / stage / "ingest_tmp"
        if base.exists():
            shutil.rmtree(base)
        with zipfile.ZipFile(src) as z:
            z.extractall(base)
    found = sorted(base.rglob("results.json"))
    if not found:
        raise PipelineError(f"no results.json inside {src}. Did the job finish?")
    results = json.loads(found[0].read_text(encoding="utf-8"))
    if results.get("stage") != stage:
        raise PipelineError(f"these results are for the {results.get('stage')} stage, not {stage}")
    folder = found[0].parent

    seen_path = ctx.out / stage / "ingested.json"
    seen = set(json.loads(seen_path.read_text(encoding="utf-8"))) if seen_path.exists() else set()
    cache, accepted = Cache(ctx, stage), 0
    for r in results["results"]:
        tag = f"{results.get('job_id', '?')}:{r['unit']}:{r['key']}"
        if tag in seen:
            continue  # the same results file ingested twice must not double the run log
        log_run(ctx, stage=stage, unit=r["unit"], provider="kaggle", model=results["model"], params=r.get("params", {}),
                seed=r.get("seed"), attempt=1, status=r["status"], latency_s=r.get("latency_s"),
                gpu=results.get("gpu"), gpu_minutes=round((r.get("latency_s") or 0) / 60, 2),
                peak_mem_gb=r.get("peak_mem_gb"), **({"error": r["error"][:400]} if r.get("error") else {}))
        seen.add(tag)
        if r["status"] != "ok":
            ctx.say(f"  [{stage}] {r['unit']:<22} FAILED on the GPU: {r.get('error', '')[:120]}")
            continue
        if sha(r["fingerprint"])[:16] != r["key"]:
            ctx.say(f"  [{stage}] {r['unit']:<22} skipped: its key does not match its fingerprint")
            continue
        produced = folder / r["file"]
        if not produced.exists():
            ctx.say(f"  [{stage}] {r['unit']:<22} skipped: {r['file']} is missing from the results")
            continue
        target = cache.file(r["unit"], r["key"], ext)
        target.parent.mkdir(parents=True, exist_ok=True)
        if convert:
            convert(produced, target)
        else:
            shutil.copy2(produced, target)
        info = media_info(target)
        meta = {"seconds": round(info["duration"], 3), "source": "kaggle", "latency_s": r.get("latency_s")}
        cache.commit(Unit(stage, r["unit"], r["fingerprint"], ext), r["key"], target, meta)
        accepted += 1
        ctx.say(f"  [{stage}] {r['unit']:<22} ingested ({info['duration']:.1f}s, made in {r.get('latency_s', 0):.0f}s on the GPU)")
    seen_path.write_text(json.dumps(sorted(seen)), encoding="utf-8")
    return accepted
