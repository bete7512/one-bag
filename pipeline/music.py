"""Stage 5, music: the score.

* placeholder: a soft drone made locally with FFmpeg. It is what plays under the radio cut, and
  under any cut made before a real score is chosen.
* acestep: candidates from ACE-Step 1.5, one per seed in `music.seeds`. They are generated as an
  exported GPU job and come back through `ingest`. `music.chosen` in the storyboard says which
  candidate is the score. Choosing is a human job: listen at low volume under the narration, pick
  one, and write down why in `music.chosen_reason` and EXPERIMENTS.md.

Each candidate that has come back is also described by a model that listens to it: is anyone
singing, which instruments, and the moments that would fight with a narrator. It prepares the
choice and does not make it, so it is an optional unit. A score with singing in it is the one
thing a film with a narrator cannot use, and it is cheaper to hear about it here than in the mix.

Candidates are kept as FLAC: the same sound as the WAV the model wrote, at half the size.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from . import kagglejob, providers
from .core import STAGE_VERSION, Ctx, PipelineError, Unit, ff, file_sha, run_units, write_index

HEAR_VERSION = 1  # bump when the question changes
HEAR_PROMPT = """This is a candidate score for a short film. It will play quietly under a narrator's voice. Listen to it and report as JSON:
- vocals: true if any singing, humming or spoken voice is heard.
- instruments: the instruments you hear, the most prominent first.
- tempo: "slow", "medium" or "fast".
- mood: three words.
- busy_moments: the moments that would fight with a narrator (a loud entrance, a busy melody, a sudden change), each as {"at_s": seconds from the start, "what": a few words}. An empty list if the music stays in the background throughout.
- notes: one sentence a film editor can act on."""


def placeholder(out: Path, seconds: float) -> None:
    """An open fifth with a slow swell: enough to judge the narration against, nothing to get attached to."""
    tones = []
    for freq in (110.0, 164.81, 220.6):
        tones += ["-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={seconds}"]
    graph = (f"[0:a][1:a][2:a]amix=inputs=3:normalize=0,tremolo=f=0.15:d=0.5,lowpass=f=900,volume=0.25,"
             f"afade=t=in:st=0:d=2,afade=t=out:st={max(0.0, seconds - 3):.2f}:d=3,aformat=channel_layouts=stereo[a]")
    ff([*tones, "-filter_complex", graph, "-map", "[a]", "-ar", "48000", "-c:a", "pcm_s16le", str(out)])


def to_flac(src: Path, dst: Path) -> None:
    ff(["-i", str(src), "-vn", "-ar", "48000", "-ac", "2", "-c:a", "flac", str(dst)])


def hear(ctx: Ctx, unit: str, audio: Path, tmp: Path) -> dict:
    """Have the text model listen to one candidate and say what is in it."""
    small = ctx.out / "tmp" / f"hear-{uuid.uuid4().hex[:8]}.mp3"  # the whole track at a size that fits in one request
    small.parent.mkdir(parents=True, exist_ok=True)
    ff(["-i", str(audio), "-vn", "-ac", "1", "-ar", "24000", "-b:a", "48k", str(small)])
    try:
        answer, _ = providers.text(ctx, "music", unit, HEAR_PROMPT, kind="describe_music", parts=[("audio/mp3", small.read_bytes())],
                                   json_mode=True, temperature=0.0)
    finally:
        small.unlink(missing_ok=True)
    found = re.search(r"\{.*\}", answer, re.S)
    try:
        heard = json.loads(found.group(0)) if found else {}
    except json.JSONDecodeError:
        heard = {}
    if not isinstance(heard.get("vocals"), bool):
        raise PipelineError(f"the description of {unit} did not come in the asked form: {answer[:120]}")
    tmp.write_text(json.dumps(heard, ensure_ascii=False), encoding="utf-8")
    return heard


def run(ctx: Ctx, state: dict, plan_only: bool = False) -> dict:
    sb = ctx.sb
    V, m = STAGE_VERSION["music"], sb["music"]

    cand_units = []
    for n, seed in enumerate(m["seeds"], start=1):
        fp = {"v": V, "caption": m["caption"], "bpm": m.get("bpm"), "keyscale": m.get("keyscale", ""),
              "duration_s": m["duration_s"], "seed": seed, "model": sb["models"]["music"]}
        cand_units.append(Unit("music", f"candidate_{n}", fp, "flac", None))
    cands = run_units(ctx, cand_units, plan_only)

    hear_units = []
    for u in cand_units:
        if cands[u.id].hit:
            fp = {"v": V, "hear": HEAR_VERSION, "audio": file_sha(cands[u.id].path), "model": sb["models"]["text"]}
            hear_units.append(Unit("music", f"{u.id}_heard", fp, "json",
                                   lambda tmp, unit=u.id, audio=cands[u.id].path: hear(ctx, f"{unit}_heard", audio, tmp), optional=True))
    heard = {uid.removesuffix("_heard"): res.meta for uid, res in run_units(ctx, hear_units, plan_only).items() if isinstance(res.meta.get("vocals"), bool)}
    for name, said in heard.items():
        if said["vocals"] and not plan_only:
            ctx.say(f"  look at {name}: a voice is heard in it. A score with singing fights the narrator.")

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
             "candidates": {u.id: (cands[u.id].path.name if cands[u.id].hit else None) for u in cand_units}, "heard": heard}
    state["music"] = index
    if not plan_only:
        write_index(ctx, "music", index)
    return index


def ingest(ctx: Ctx, src: Path) -> int:
    return kagglejob.ingest(ctx, "music", src, "flac", convert=to_flac)
