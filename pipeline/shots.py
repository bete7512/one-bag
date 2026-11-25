"""Stage 4, shots: turn each keyframe into a moving clip at the master size.

Two ways to move a picture:

* kenburns: a slow pan or zoom over the still, made locally by FFmpeg. Deterministic, free, fast.
* wan: Wan 2.2 image-to-video on a GPU. It runs as an exported job (see kagglejob.py) and comes
  back through `ingest`.

A shot that asks for `wan` uses its Wan clip when one is in the cache. Until then it falls back to
Ken Burns, so a full film can always be assembled, and the index says which shots are fallbacks.
"""
from __future__ import annotations

from pathlib import Path

from . import kagglejob
from .core import STAGE_VERSION, Ctx, Unit, ff, get_index, plan_timeline, run_units, write_index

VIDEO_DEFAULTS = {"max_area": 480 * 832, "num_frames": 81, "steps": 30, "guidance": 5.0}
EASE = "(1-cos(PI*on/{last}))/2"  # slow start, slow stop


def camera_filter(camera: str, frames: int, fps: int, w: int, h: int) -> str:
    """FFmpeg zoompan expressions for one camera move. The still is enlarged first so the move is smooth."""
    p = EASE.format(last=max(1, frames - 1))
    cx, cy = "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"
    moves = {
        "push_in": (f"1+0.12*{p}", cx, cy),
        "pull_out": (f"1.12-0.12*{p}", cx, cy),
        "pan_right": ("1.14", f"(iw-iw/zoom)*{p}", cy),
        "pan_left": ("1.14", f"(iw-iw/zoom)*(1-{p})", cy),
        "tilt_down": ("1.14", cx, f"(ih-ih/zoom)*{p}"),
        "tilt_up": ("1.14", cx, f"(ih-ih/zoom)*(1-{p})"),
        "static": ("1", "0", "0"),
    }
    z, x, y = moves[camera]
    return (f"scale={3 * w}:{3 * h}:flags=lanczos,zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},format=yuv420p")


def kenburns(keyframe: Path, out: Path, camera: str, frames: int, fps: int, w: int, h: int) -> None:
    ff(["-i", str(keyframe), "-vf", camera_filter(camera, frames, fps, w, h), "-frames:v", str(frames),
        "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-an", str(out)])


def run(ctx: Ctx, state: dict, plan_only: bool = False) -> dict:
    sb = ctx.sb
    V, fmt = STAGE_VERSION["shots"], sb["format"]
    W, H, fps = fmt["master"]["width"], fmt["master"]["height"], fmt["fps"]
    keyframes = get_index(ctx, state, "keyframes")
    narration = get_index(ctx, state, "narration", per_lang=True, required=False)
    timeline = {t["id"]: t for t in plan_timeline(sb, {k: v["seconds"] for k, v in narration.items()})["shots"]}
    video = {**VIDEO_DEFAULTS, **sb.get("video", {})}
    key_dir = ctx.out / "keyframes"

    wan_units, kb_units, jobs, job_inputs = [], [], [], []
    for s in sb["shots"]:
        sid, kf, frames = s["id"], keyframes[s["id"]], timeline[s["id"]]["frames"]
        if s["motion"]["backend"] == "wan" and not kf.get("blocked"):
            seed = s["motion"].get("seed", s["keyframe"]["seed"])
            fp = {"v": V, "keyframe": kf["key"], "prompt": s["motion"]["prompt"], "negative": sb["style"].get("negative", ""),
                  "seed": seed, "model": sb["models"]["video"], **video}
            wan_units.append(Unit("shots", f"{sid}_wan", fp, "mp4", None))
        fp = {"v": V, "keyframe": kf["key"], "camera": s["motion"]["camera"], "frames": frames, "fps": fps, "w": W, "h": H}

        def produce(tmp: Path, kf: dict = kf, camera: str = s["motion"]["camera"], frames: int = frames) -> dict:
            kenburns(key_dir / kf["file"], tmp, camera, frames, fps, W, H)
            return {"seconds": round(frames / fps, 3), "source": "kenburns"}

        kb_units.append(Unit("shots", f"{sid}_kenburns", fp, "mp4", produce))

    wan = run_units(ctx, wan_units, plan_only)
    have_wan = {uid.split("_")[0] for uid, res in wan.items() if res.hit}
    kb = run_units(ctx, [u for u in kb_units if u.id.split("_")[0] not in have_wan], plan_only)

    index = {}
    for s in sb["shots"]:
        sid = s["id"]
        if sid in have_wan:
            res, source = wan[f"{sid}_wan"], "wan"
        else:
            res = kb[f"{sid}_kenburns"]
            source = "kenburns_fallback" if f"{sid}_wan" in wan else "kenburns"
        index[sid] = {"file": res.path.name if res.path else None, "key": res.key, "source": source,
                      "seconds": res.meta.get("seconds", timeline[sid]["duration"])}
        if f"{sid}_wan" in wan and sid not in have_wan and keyframes[sid]["file"]:
            unit = next(u for u in wan_units if u.id == f"{sid}_wan")
            jobs.append({"unit": unit.id, "key": wan[unit.id].key, "fingerprint": unit.fingerprint, "shot": sid,
                         "keyframe": keyframes[sid]["file"], "prompt": s["motion"]["prompt"],
                         "negative": sb["style"].get("negative", ""), "seed": unit.fingerprint["seed"]})
            job_inputs.append(key_dir / keyframes[sid]["file"])
    if jobs and not plan_only:
        kagglejob.export_job(ctx, "shots", sb["models"]["video"], {**video, "fps": fps}, jobs, job_inputs, "wan22_i2v.py")
    state["shots"] = index
    if not plan_only:
        write_index(ctx, "shots", index, per_lang=True)
    return index


def ingest(ctx: Ctx, src: Path) -> int:
    return kagglejob.ingest(ctx, "shots", src, "mp4")
