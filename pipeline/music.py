"""Stage 5, music: the score.

* placeholder: a soft drone made locally with FFmpeg. It is what plays under the radio cut, and
  under any cut made before a real score is chosen.
* acestep: candidates from ACE-Step 1.5, one per seed in `music.seeds`. They are generated as an
  exported GPU job and come back through `ingest`. `music.chosen` in the storyboard says which
  candidate is the score. Choosing is a human job: listen at low volume under the narration, pick
  one, and write down why in `music.chosen_reason` and EXPERIMENTS.md.
"""
from __future__ import annotations

from pathlib import Path

from . import kagglejob
from .core import STAGE_VERSION, Ctx, Unit, ff, run_units, write_index


def placeholder(out: Path, seconds: float) -> None:
    """An open fifth with a slow swell: enough to judge the narration against, nothing to get attached to."""
    tones = []
    for freq in (110.0, 164.81, 220.6):
        tones += ["-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={seconds}"]
    graph = (f"[0:a][1:a][2:a]amix=inputs=3:normalize=0,tremolo=f=0.15:d=0.5,lowpass=f=900,volume=0.25,"
             f"afade=t=in:st=0:d=2,afade=t=out:st={max(0.0, seconds - 3):.2f}:d=3,aformat=channel_layouts=stereo[a]")
    ff([*tones, "-filter_complex", graph, "-map", "[a]", "-ar", "48000", "-c:a", "pcm_s16le", str(out)])


def to_wav(src: Path, dst: Path) -> None:
    ff(["-i", str(src), "-vn", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(dst)])


def run(ctx: Ctx, state: dict, plan_only: bool = False) -> dict:
    sb = ctx.sb
    V, m = STAGE_VERSION["music"], sb["music"]

    cand_units = []
    for n, seed in enumerate(m["seeds"], start=1):
        fp = {"v": V, "caption": m["caption"], "bpm": m.get("bpm"), "keyscale": m.get("keyscale", ""),
              "duration_s": m["duration_s"], "seed": seed, "model": sb["models"]["music"]}
        cand_units.append(Unit("music", f"candidate_{n}", fp, "wav", None))
    cands = run_units(ctx, cand_units, plan_only)

    fp = {"v": V, "placeholder": "drone-v1", "seconds": m["duration_s"]}
    ph = run_units(ctx, [Unit("music", "placeholder", fp, "wav", lambda tmp: placeholder(tmp, m["duration_s"]) or {"seconds": m["duration_s"]})], plan_only)["placeholder"]

    chosen = m["chosen"]
    if chosen and cands[f"candidate_{chosen}"].hit:
        res, source = cands[f"candidate_{chosen}"], "acestep"
    else:
        res, source = ph, "placeholder"
        if chosen:
            ctx.say(f"  [music] candidate {chosen} is chosen but not ingested yet: the placeholder plays")
    missing = [u for u in cand_units if not cands[u.id].hit]
    if missing and not plan_only:
        jobs = [{"unit": u.id, "key": cands[u.id].key, "fingerprint": u.fingerprint, "seed": u.fingerprint["seed"]} for u in missing]
        settings = {"caption": m["caption"], "bpm": m.get("bpm"), "keyscale": m.get("keyscale", ""), "duration_s": m["duration_s"]}
        kagglejob.export_job(ctx, "music", sb["models"]["music"], settings, jobs, [], "acestep_music.py")

    index = {"file": res.path.name if res.path else None, "key": res.key, "source": source, "chosen": chosen,
             "seconds": res.meta.get("seconds", m["duration_s"]),
             "candidates": {u.id: (cands[u.id].path.name if cands[u.id].hit else None) for u in cand_units}}
    state["music"] = index
    if not plan_only:
        write_index(ctx, "music", index)
    return index


def ingest(ctx: Ctx, src: Path) -> int:
    return kagglejob.ingest(ctx, "music", src, "wav", convert=to_wav)
