"""Stage 3, keyframes: the still picture each shot starts from.

Order matters here:

1. Consent gate. A shot that shows a real person is not generated until that person's consent is
   recorded in ETHICS.md and in the storyboard. Until then the shot gets a plain card, so the cut
   still assembles.
2. Reference sheet first. Each character with a `reference_prompt` gets one sheet, and every shot
   that character is in is generated against it.
3. Candidates, then a judge. Each shot gets a few candidates with consecutive seeds. A vision model
   scores each one (character match, prompt adherence, artifacts, stray writing) and the best is
   kept. `keyframe.pick` in the storyboard overrides the judge: the human has the last word.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from . import providers
from .core import STAGE_VERSION, Ctx, PipelineError, Unit, ff, run_units, write_index

JUDGE_PROMPT = """You are checking a storyboard keyframe before GPU time is spent animating it.
The last image is the candidate keyframe. Any images before it are reference sheets of the characters.

Shot description: "{shot}"
Characters expected: {who}

Score each from 1 (bad) to 5 (good):
- character_match: does the person match the reference sheet (build, hair, clothes, bag)? Use 3 when no person or no reference is involved.
- prompt_adherence: does the picture show what the shot description asks for?
- artifacts: 5 means clean. Lower it for broken hands, faces or limbs, and for melted shapes.
Also set text_in_image to true if any writing or letter-like marks are visible.

Reply with JSON only: {{"character_match": n, "prompt_adherence": n, "artifacts": n, "text_in_image": true or false, "notes": "one short sentence"}}"""


def full_prompt(sb: dict, shot: dict) -> str:
    """Style block + what is in the shot + the fixed description of each character in it."""
    chars = {c["id"]: c for c in sb["characters"]}
    who = " ".join(chars[cid]["description"] for cid in shot["characters"])
    return " ".join(part for part in (sb["style"]["block"], shot["keyframe"]["prompt"], who) if part)


def cleared(ctx: Ctx, character: dict) -> bool:
    """Mock runs draw labelled colour cards, not people, so the gate only binds real providers."""
    return ctx.mock or not character["real_person"] or character["consent"]["status"] == "recorded"


def to_master(ctx: Ctx, raw: bytes, out: Path, width: int, height: int) -> None:
    """Store the provider's image at the master size as PNG, and keep the untouched original beside it."""
    originals = ctx.out / "keyframes" / "original"
    originals.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"^tmp-[0-9a-f]{8}-", "", out.stem)
    original = originals / f"{stem}.{providers.image_ext(raw)}"
    original.write_bytes(raw)  # provenance metadata (C2PA) lives in the original file, so it is never thrown away
    ff(["-i", str(original), "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{height}",
        "-frames:v", "1", str(out)])


def small_jpeg(ctx: Ctx, image: Path, side: int = 448) -> bytes:
    """A small copy for reference inputs (FLUX.2 on Workers AI wants them under 512x512) and for the judge."""
    tmp = ctx.out / "tmp" / f"small-{uuid.uuid4().hex[:8]}.jpg"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    ff(["-i", str(image), "-vf", f"scale={side}:{side}:force_original_aspect_ratio=decrease", "-frames:v", "1", "-q:v", "4", str(tmp)])
    data = tmp.read_bytes()
    tmp.unlink()
    return data


def judge_total(scores: dict, has_character: bool) -> float:
    def val(key: str) -> float:
        try:
            return min(5.0, max(1.0, float(scores.get(key, 3))))
        except (TypeError, ValueError):
            return 3.0

    if has_character:
        total = 0.4 * val("character_match") + 0.35 * val("prompt_adherence") + 0.25 * val("artifacts")
    else:
        total = 0.6 * val("prompt_adherence") + 0.4 * val("artifacts")
    return round(total - (1.5 if scores.get("text_in_image") is True else 0.0), 3)


def parse_scores(answer: str) -> dict:
    match = re.search(r"\{.*\}", answer, re.S)
    try:
        return json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        return {}


def run(ctx: Ctx, state: dict, plan_only: bool = False) -> dict:
    sb = ctx.sb
    V, model = STAGE_VERSION["keyframes"], sb["models"]["image"]
    W, H = sb["format"]["master"]["width"], sb["format"]["master"]["height"]
    qa = sb.get("qa", {})
    chars = {c["id"]: c for c in sb["characters"]}

    # 1. reference sheets
    ref_units = []
    for c in sb["characters"]:
        if not c.get("reference_prompt") or not cleared(ctx, c):
            continue
        prompt = " ".join((sb["style"]["block"], c["reference_prompt"], c["description"]))
        fp = {"v": V, "prompt": prompt, "seed": c.get("seed", 0), "model": model, "w": W, "h": H}

        def produce(tmp: Path, cid: str = c["id"], prompt: str = prompt, seed: int = c.get("seed", 0)) -> dict:
            raw, meta = providers.image(ctx, "keyframes", f"ref_{cid}", prompt, width=W, height=H, seed=seed)
            to_master(ctx, raw, tmp, W, H)
            return {"seed_applied": meta.get("seed_applied")}

        ref_units.append(Unit("keyframes", f"ref_{c['id']}", fp, "png", produce))
    refs = run_units(ctx, ref_units, plan_only)

    # 2. candidates (or a plain card when consent is missing)
    units, plan = [], {}
    for s in sb["shots"]:
        blocked = [cid for cid in s["characters"] if not cleared(ctx, chars[cid])]
        if blocked:
            fp = {"v": V, "card": s["title"], "why": blocked, "w": W, "h": H}

            def card(tmp: Path, sid: str = s["id"]) -> dict:
                label = f"{sid} waiting for consent"
                draw = f"drawtext=text='{label}':fontsize=h/18:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2"
                src = ["-f", "lavfi", "-i", f"color=c=0x30343c:s={W}x{H}:d=1"]
                try:
                    ff([*src, "-vf", draw, "-frames:v", "1", str(tmp)])
                except PipelineError:
                    ff([*src, "-frames:v", "1", str(tmp)])
                return {}

            units.append(Unit("keyframes", f"{s['id']}_card", fp, "png", card))
            plan[s["id"]] = {"blocked": blocked}
            ctx.say(f"  [keyframes] {s['id']:<22} BLOCKED: consent not recorded for {', '.join(blocked)}")
            continue
        n = s["keyframe"].get("candidates", qa.get("keyframe_candidates", 1))
        prompt = full_prompt(sb, s)
        ref_ids = [f"ref_{cid}" for cid in s["characters"] if f"ref_{cid}" in refs]
        plan[s["id"]] = {"blocked": [], "n": n, "prompt": prompt, "refs": ref_ids}
        for i in range(1, n + 1):
            seed = s["keyframe"]["seed"] + i - 1
            fp = {"v": V, "prompt": prompt, "seed": seed, "model": model, "w": W, "h": H, "refs": [refs[r].key for r in ref_ids]}

            def produce(tmp: Path, sid: str = s["id"], i: int = i, prompt: str = prompt, seed: int = seed, ref_ids: list = ref_ids) -> dict:
                ref_bytes = [small_jpeg(ctx, refs[r].path) for r in ref_ids]
                raw, meta = providers.image(ctx, "keyframes", f"{sid}_c{i}", prompt, width=W, height=H, seed=seed, refs=ref_bytes)
                to_master(ctx, raw, tmp, W, H)
                return {"seed": seed, "seed_applied": meta.get("seed_applied")}

            units.append(Unit("keyframes", f"{s['id']}_c{i}", fp, "png", produce))
    made = run_units(ctx, units, plan_only)

    # 3. judge
    judged = {}
    if qa.get("judge"):  # in plan mode this only reads scores already in the cache, so the plan picks what the run picked
        judge_units = []
        for s in sb["shots"]:
            p = plan[s["id"]]
            if p["blocked"]:
                continue
            who = " ".join(chars[cid]["description"] for cid in s["characters"]) or "none"
            for i in range(1, p["n"] + 1):
                cand = made[f"{s['id']}_c{i}"]
                fp = {"v": V, "image": cand.key, "refs": [refs[r].key for r in p["refs"]], "shot": s["keyframe"]["prompt"],
                      "who": who, "model": sb["models"]["text"]}

                def produce(tmp: Path, sid: str = s["id"], i: int = i, cand=cand, p: dict = p, who: str = who, shot: str = s["keyframe"]["prompt"]) -> dict:
                    parts = [("image/jpeg", small_jpeg(ctx, refs[r].path)) for r in p["refs"]]
                    parts.append(("image/jpeg", small_jpeg(ctx, cand.path, side=768)))
                    answer, _ = providers.text(ctx, "keyframes", f"{sid}_c{i}_judge", JUDGE_PROMPT.format(shot=shot, who=who),
                                               kind="judge", parts=parts, json_mode=True, temperature=0.0)
                    scores = parse_scores(answer)
                    scores["total"] = judge_total(scores, bool(p["refs"]))
                    tmp.write_text(json.dumps(scores, ensure_ascii=False), encoding="utf-8")
                    return scores

                judge_units.append(Unit("keyframes", f"{s['id']}_c{i}_judge", fp, "json", produce))
        judged = run_units(ctx, judge_units, plan_only)

    # 4. pick
    index = {}
    for s in sb["shots"]:
        sid, p = s["id"], plan[s["id"]]
        if p["blocked"]:
            res = made[f"{sid}_card"]
            index[sid] = {"file": res.path.name if res.path else None, "key": res.key, "blocked": p["blocked"], "candidate": None}
            continue
        scores = {i: judged[f"{sid}_c{i}_judge"].meta for i in range(1, p["n"] + 1) if f"{sid}_c{i}_judge" in judged}
        pick, by = s["keyframe"].get("pick"), "human"
        if not pick:
            if len(scores) > 1:
                pick, by = max(scores, key=lambda i: scores[i].get("total", 0)), "judge"
            else:
                pick, by = 1, "only candidate" if p["n"] == 1 else "first candidate (judge off)"
        res = made[f"{sid}_c{pick}"]
        index[sid] = {"file": res.path.name if res.path else None, "key": res.key, "blocked": [], "candidate": pick,
                      "picked_by": by, "scores": {str(i): v for i, v in scores.items()}, "prompt": p["prompt"]}
        flagged = scores.get(pick, {})
        if flagged.get("text_in_image") or flagged.get("total", 5) < 3:
            ctx.say(f"  look at {sid}: judge total {flagged.get('total')}, text in image: {flagged.get('text_in_image')}. {flagged.get('notes', '')}")
    state["keyframes"] = index
    if not plan_only:
        write_index(ctx, "keyframes", index)
    return index
