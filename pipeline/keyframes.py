"""Stage 3, keyframes: the still picture each shot starts from.

Order matters here:

1. Consent gate. A shot that shows a real person is not generated until that person's consent is
   recorded in ETHICS.md and in the storyboard. Until then the shot gets a plain card, so the cut
   still assembles.
2. Reference sheet first. Each character with a `reference_prompt` gets one sheet, and every shot
   that character is in is generated against it.
3. Candidates, then two checks. Each shot gets a few candidates with consecutive seeds. A border
   check measures whether the picture fills the frame, and a vision model scores each candidate
   (character match, prompt adherence, artifacts, stray writing). The best full-frame candidate is
   kept. `keyframe.pick` in the storyboard overrides both: the human has the last word.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from . import providers
from .core import STAGE_VERSION, Cache, Ctx, PipelineError, Unit, ff, run_units, sha, write_index

JUDGE_VERSION = 2  # bump when the question changes, so old answers stop matching
LOOK_UNDER = 3     # a picked picture with a judge total under this is one for a person to look at. The final-cut check uses the same number
JUDGE_PROMPT = """This is a check of one frame of a short hand-painted film, before the frame is animated. Find what is wrong with it: a frame that passes here goes into the film.

The last image is the frame. Any images before it are reference sheets of the characters who should be in it.

What the frame should show: "{shot}"
Characters expected: {who}
The look the film is going for: "{style}"

Report these as JSON:
- elements: each thing the description asks for, one entry per thing as {{"name": ..., "visible": true or false}}. Visible means really in the frame, not implied.
- border: true if the picture does not reach all four edges of the frame: a white or paper margin, a drawn frame, rounded corners, a vignette, or ragged unpainted edges.
- text_in_image: true if any writing, letters or numbers are visible, garbled ones included.
- wrong_setting: what, if anything, places the scene somewhere other than the description says (buildings, vehicles, clothes). An empty string if nothing does.
- anatomy: broken hands, faces or limbs, or melted shapes. An empty string if there are none.
- character_match: 1 to 5, how well the person matches the reference sheet in build, hair, clothes and bag. Use 3 when there is no person or no sheet.
- prompt_adherence: 1 to 5. Give 5 only if every element is visible and nothing contradicts the description.
- artifacts: 1 to 5. Give 5 only if the frame is clean.
- notes: one short sentence a director can act on."""
JUDGE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["elements", "border", "text_in_image", "wrong_setting", "anatomy", "character_match", "prompt_adherence", "artifacts", "notes"],
    "properties": {
        "elements": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["name", "visible"],
                                                "properties": {"name": {"type": "string"}, "visible": {"type": "boolean"}}}},
        "border": {"type": "boolean"}, "text_in_image": {"type": "boolean"},
        "wrong_setting": {"type": "string"}, "anatomy": {"type": "string"},
        "character_match": {"type": "integer"}, "prompt_adherence": {"type": "integer"}, "artifacts": {"type": "integer"},
        "notes": {"type": "string"}},
}


def full_prompt(sb: dict, shot: dict) -> str:
    """Style block + what is in the shot + the fixed description of each character in it."""
    chars = {c["id"]: c for c in sb["characters"]}
    who = " ".join(chars[cid]["description"] for cid in shot["characters"])
    return " ".join(part for part in (sb["style"]["block"], shot["keyframe"]["prompt"], who) if part)


def cleared(ctx: Ctx, character: dict) -> bool:
    """Mock runs draw labelled colour cards, not people, so the gate only binds real providers."""
    return ctx.mock or not character["real_person"] or character["consent"]["status"] == "recorded"


def draw(ctx: Ctx, unit: str, raw_fp: dict, tmp: Path, *, prompt: str, seed: int, refs: list[bytes] | None = None, trim: float = 0.0) -> dict:
    """One generated picture at the master size.

    The model's untouched answer is kept in keyframes/original/ under a hash of what was sent to the
    model (`raw_fp`), and the master is cut from that file by FFmpeg. So the model is called only when
    no original exists yet: changing the cut (the size, the edge trim) costs no model call. Provenance
    metadata (C2PA) lives in the original file, which is never altered.

    `trim` is the share of each side cut away. Painted pictures often come back with a ragged paper
    edge that is too thin for the border check and still shows as a light line in the film.
    """
    raw_key = sha(raw_fp)[:16]
    folder = ctx.out / "keyframes" / "original"
    kept = sorted(folder.glob(f"{unit}__{raw_key}.*")) if folder.exists() else []
    if kept:
        original = kept[0]
        earlier = [entry["meta"] for entry in Cache(ctx, "keyframes").data["entries"].values() if entry["meta"].get("original") == original.name]
        seed_applied = next((meta.get("seed_applied") for meta in earlier if meta.get("seed_applied") is not None), None)
    else:
        raw, meta = providers.image(ctx, "keyframes", unit, prompt, width=raw_fp["w"], height=raw_fp["h"], seed=seed, refs=refs or [])
        folder.mkdir(parents=True, exist_ok=True)
        original = folder / f"{unit}__{raw_key}.{providers.image_ext(raw)}"
        original.write_bytes(raw)
        seed_applied = meta.get("seed_applied")
    width, height = raw_fp["w"], raw_fp["h"]
    grown = f"{round(width * (1 + 2 * trim))}:{round(height * (1 + 2 * trim))}"
    ff(["-i", str(original), "-vf", f"scale={grown}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{height}",
        "-frames:v", "1", str(tmp)])
    return {"seed": seed, "seed_applied": seed_applied, "original": original.name}


def small_jpeg(ctx: Ctx, image: Path, side: int = 448) -> bytes:
    """A small copy for reference inputs (FLUX.2 on Workers AI wants them under 512x512) and for the judge."""
    tmp = ctx.out / "tmp" / f"small-{uuid.uuid4().hex[:8]}.jpg"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    ff(["-i", str(image), "-vf", f"scale={side}:{side}:force_original_aspect_ratio=decrease", "-frames:v", "1", "-q:v", "4", str(tmp)])
    data = tmp.read_bytes()
    tmp.unlink()
    return data


# A painted look invites the model to paint a framed picture on a page. Cropped to a film frame, the
# margin shows as a white band. Paper is bright and has no colour: every channel above PAPER_MIN and
# the channels within PAPER_SPREAD of each other. A pale blue sky or a yellow wall does not qualify.
PAPER_MIN, PAPER_SPREAD = 185, 28
PAPER_STRIP = 4 / 256   # how much of each side is measured: its outer 1.6%
PAPER_SIDE = 0.6        # a side is bare paper when this share of its strip is
BORDER_SIDES = 2        # this many bare sides make a border. One alone can be a white sky or a pale road.


def paper_edges(ctx: Ctx, image: Path) -> int:
    """How many of the four sides of a picture are bare paper. Measured, no model involved."""
    side = 256
    band = max(1, round(side * PAPER_STRIP))
    tmp = ctx.out / "tmp" / f"edges-{uuid.uuid4().hex[:8]}.rgb"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    ff(["-i", str(image), "-vf", f"scale={side}:{side}:flags=area", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", str(tmp)])
    px = tmp.read_bytes()
    tmp.unlink()

    def paper(x: int, y: int) -> bool:
        at = 3 * (y * side + x)
        r, g, b = px[at], px[at + 1], px[at + 2]
        return min(r, g, b) > PAPER_MIN and max(r, g, b) - min(r, g, b) < PAPER_SPREAD

    strips = ([(x, y) for y in range(band) for x in range(side)],                  # top
              [(x, y) for y in range(side - band, side) for x in range(side)],     # bottom
              [(x, y) for x in range(band) for y in range(side)],                  # left
              [(x, y) for x in range(side - band, side) for y in range(side)])     # right
    return sum(1 for cells in strips if sum(paper(x, y) for x, y in cells) / len(cells) >= PAPER_SIDE)


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
    # what a film frame cannot have costs more than a point of taste
    total -= 1.5 if scores.get("text_in_image") is True else 0.0
    total -= 1.5 if scores.get("border") is True else 0.0
    total -= 1.0 if str(scores.get("wrong_setting") or "").strip() else 0.0
    total -= 1.0 if str(scores.get("anatomy") or "").strip() else 0.0
    return round(total, 3)


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
    judge_model = sb["models"].get("judge") or sb["models"]["text"]  # the judge may be a stricter model than the other checks
    trim = sb["format"].get("edge_trim", 0.0)
    cut = {"trim": trim} if trim else {}  # part of a picture's fingerprint, but not of what the model is sent

    # 1. reference sheets
    ref_units = []
    for c in sb["characters"]:
        if not c.get("reference_prompt") or not cleared(ctx, c):
            continue
        prompt = " ".join((sb["style"]["block"], c["reference_prompt"], c["description"]))
        raw_fp = {"v": V, "prompt": prompt, "seed": c.get("seed", 0), "model": model, "w": W, "h": H}  # what the model is sent

        def produce(tmp: Path, cid: str = c["id"], prompt: str = prompt, seed: int = c.get("seed", 0), raw_fp: dict = raw_fp) -> dict:
            return draw(ctx, f"ref_{cid}", raw_fp, tmp, prompt=prompt, seed=seed, trim=trim)

        ref_units.append(Unit("keyframes", f"ref_{c['id']}", {**raw_fp, **cut}, "png", produce))
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
        # a shot can ask to be drawn from its words alone: the reference pulls every picture toward one centred figure (F05)
        ref_ids = [f"ref_{cid}" for cid in s["characters"] if f"ref_{cid}" in refs] if s["keyframe"].get("reference", True) else []
        plan[s["id"]] = {"blocked": [], "n": n, "prompt": prompt, "refs": ref_ids}
        for i in range(1, n + 1):
            seed = s["keyframe"]["seed"] + i - 1
            # the references are named by their untouched originals, so a change to the cut does not redraw every character shot
            raw_fp = {"v": V, "prompt": prompt, "seed": seed, "model": model, "w": W, "h": H,
                      "refs": [refs[r].meta.get("original", refs[r].key) for r in ref_ids]}

            def produce(tmp: Path, sid: str = s["id"], i: int = i, prompt: str = prompt, seed: int = seed, ref_ids: list = ref_ids,
                        raw_fp: dict = raw_fp) -> dict:
                ref_bytes = [small_jpeg(ctx, ctx.out / "keyframes" / "original" / refs[r].meta["original"] if refs[r].meta.get("original")
                                        else refs[r].path) for r in ref_ids]
                return draw(ctx, f"{sid}_c{i}", raw_fp, tmp, prompt=prompt, seed=seed, refs=ref_bytes, trim=trim)

            units.append(Unit("keyframes", f"{s['id']}_c{i}", {**raw_fp, **cut}, "png", produce))
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
                fp = {"v": V, "judge": JUDGE_VERSION, "image": cand.key, "refs": [refs[r].key for r in p["refs"]], "shot": s["keyframe"]["prompt"],
                      "who": who, "style": sb["style"]["block"], "model": judge_model}

                def produce(tmp: Path, sid: str = s["id"], i: int = i, cand=cand, p: dict = p, who: str = who, shot: str = s["keyframe"]["prompt"]) -> dict:
                    parts = [("image/jpeg", small_jpeg(ctx, refs[r].path)) for r in p["refs"]]
                    parts.append(("image/jpeg", small_jpeg(ctx, cand.path, side=768)))
                    answer, _ = providers.text(ctx, "keyframes", f"{sid}_c{i}_judge", JUDGE_PROMPT.format(shot=shot, who=who, style=sb["style"]["block"]),
                                               kind="judge", parts=parts, json_mode=True, schema=JUDGE_SCHEMA, temperature=0.0, model=judge_model)
                    scores = parse_scores(answer)
                    scores["total"] = judge_total(scores, bool(p["refs"]))
                    tmp.write_text(json.dumps(scores, ensure_ascii=False), encoding="utf-8")
                    return scores

                # optional: the judge measures. If the model cannot be reached the pictures are still there, and a person picks.
                judge_units.append(Unit("keyframes", f"{s['id']}_c{i}_judge", fp, "json", produce, optional=True))
        judged = run_units(ctx, judge_units, plan_only)

    # 4. pick
    index = {}
    for s in sb["shots"]:
        sid, p = s["id"], plan[s["id"]]
        if p["blocked"]:
            res = made[f"{sid}_card"]
            index[sid] = {"file": res.path.name if res.path else None, "key": res.key, "blocked": p["blocked"], "candidate": None}
            continue
        numbers = range(1, p["n"] + 1)
        scores = {i: judged[f"{sid}_c{i}_judge"].meta for i in numbers
                  if f"{sid}_c{i}_judge" in judged and judged[f"{sid}_c{i}_judge"].meta.get("total") is not None}
        unscored = [i for i in numbers if i not in scores] if qa.get("judge") else []
        sides = {i: paper_edges(ctx, made[f"{sid}_c{i}"].path) for i in numbers if made[f"{sid}_c{i}"].path}

        def margin(i: int) -> int:
            """0 for a picture that fills its frame, otherwise how many of its sides are bare paper."""
            return sides.get(i, 0) if sides.get(i, 0) >= BORDER_SIDES else 0

        least = min(margin(i) for i in numbers)
        full_frame = [i for i in numbers if margin(i) == least]  # the candidates with the least margin: the judge chooses among these
        pick, by = s["keyframe"].get("pick"), "human"
        if not pick:
            if p["n"] == 1:
                pick, by = 1, "only candidate"
            elif not qa.get("judge"):
                pick, by = full_frame[0], "first full-frame candidate (judge off)"
            elif unscored:  # a pick between a scored and an unscored picture would not be a comparison
                pick, by = full_frame[0], "first full-frame candidate (judge incomplete)"
            else:
                pick, by = max(full_frame, key=lambda i: scores[i]["total"]), "judge"
        res = made[f"{sid}_c{pick}"]
        index[sid] = {"file": res.path.name if res.path else None, "key": res.key, "blocked": [], "candidate": pick,
                      "picked_by": by, "scores": {str(i): v for i, v in scores.items()}, "unscored": unscored,
                      "paper_sides": {str(i): n for i, n in sides.items()}, "border": sides.get(pick, 0) >= BORDER_SIDES, "prompt": p["prompt"]}
        flagged = scores.get(pick, {})
        if flagged.get("text_in_image") or flagged.get("total", 5) < LOOK_UNDER:
            ctx.say(f"  look at {sid}: judge total {flagged.get('total')}, text in image: {flagged.get('text_in_image')}. {flagged.get('notes', '')}")
        if unscored and not plan_only:
            ctx.say(f"  look at {sid}: the judge has not scored candidate {', '.join(map(str, unscored))}. The next run tries again.")
        if index[sid]["border"]:
            ctx.say(f"  look at {sid}: the picked picture has bare paper on {sides[pick]} of its 4 sides. It will show as a white band in the film.")
    state["keyframes"] = index
    if not plan_only:
        write_index(ctx, "keyframes", index)
    return index
