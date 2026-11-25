"""One page to review the whole film by eye and ear: python -m pipeline review -> outputs/review.html

The pipeline measures what it can. A person still has to look at every keyframe (hands, faces,
is it the same young man?) and listen to every line. This page puts each shot's reason, words,
audio, candidates with their judge scores, and clip side by side, so that review takes minutes.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from .core import Ctx, get_index


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def run(ctx: Ctx) -> Path:
    sb, lang, e = ctx.sb, ctx.narration_lang, html.escape
    script = get_index(ctx, {}, "script", per_lang=True, required=False).get("lines", {})
    narration = get_index(ctx, {}, "narration", per_lang=True, required=False)
    keyframes = get_index(ctx, {}, "keyframes", required=False)
    shots = get_index(ctx, {}, "shots", per_lang=True, required=False)
    key_units = _load(ctx.out / "keyframes" / "manifest.json").get("units", {})
    film = _load(ctx.out / "assemble" / f"index.film.{lang}.json")
    qc = _load(ctx.out / "qc_report.json")

    parts = [f"<h1>{e(sb['title'])}: review sheet</h1>",
             f"<p><b>For:</b> {e(sb['audience'])}<br><b>They should feel:</b> {e(sb['intent'])}</p>"]
    if qc:
        failed = [c["check"] for c in qc["checks"] if c["level"] == "must" and not c["ok"]]
        parts.append(f"<p class='{'ok' if qc['passed'] else 'bad'}'>Final-cut check: {'passed' if qc['passed'] else 'FAILED: ' + e('; '.join(failed))}"
                     f" &middot; {qc['total_s']:.1f} s &middot; {qc.get('mix', {}).get('lufs', '?')} LUFS</p>")
    films = "".join(f"<figure><video controls preload='none' src='{e(fname)}'></video><figcaption>{e(name)}</figcaption></figure>"
                    for name, fname in film.get("files", {}).items())
    parts.append(f"<div class='row'>{films}</div>" if films else "")

    for s in sb["shots"]:
        sid = s["id"]
        review = s.get("review")
        flag = "" if not review or review["confirmed"] else f"<p class='bad'>Not confirmed: {e(review.get('note', ''))}</p>"
        block = [f"<section><h2>{sid} &middot; {e(s['title'])} <small>{e(s['size'])}, {e(s['motion']['backend'])}, {e(s['motion']['camera'])}</small></h2>",
                 f"<p><b>Why this shot:</b> {e(s['reason'])}</p>", flag]
        line, spoken = script.get(sid), narration.get(sid, {})
        if line:
            block.append(f"<p class='line'>{e(line['text'])}<br><i>{e(line['subtitle'] or '')}</i></p>")
            if spoken.get("file"):
                heard = f"<br>Listening check heard: {e(spoken['heard'])} (match {spoken['roundtrip']:.2f})" if spoken.get("roundtrip") is not None else ""
                block.append(f"<p><audio controls preload='none' src='narration/{e(spoken['file'])}'></audio> {spoken.get('seconds', 0):.1f} s{heard}</p>")
        picked = keyframes.get(sid, {})
        if picked.get("blocked"):
            block.append(f"<p class='bad'>No picture: consent not recorded for {e(', '.join(picked['blocked']))}.</p>")
        row = []
        for i in range(1, 5):
            unit = key_units.get(f"{sid}_c{i}")
            if not unit:
                continue
            score = key_units.get(f"{sid}_c{i}_judge", {}).get("meta", {})
            chosen = picked.get("candidate") == i
            sides = picked.get("paper_sides", {}).get(str(i), 0)
            caption = (f"candidate {i}" + (f" &middot; judge {score.get('total')}" if score else "")
                       + (f" &middot; <span class='bad'>paper border on {sides} sides</span>" if sides >= 2 else "")
                       + (f" &middot; <b>picked by {e(picked.get('picked_by', ''))}</b>" if chosen else ""))
            note = f"<br><small>{e(str(score.get('notes', '')))}</small>" if score.get("notes") else ""
            row.append(f"<figure class='{'pick' if chosen else ''}'><img loading='lazy' src='keyframes/{e(unit['file'])}'><figcaption>{caption}{note}</figcaption></figure>")
        clip = shots.get(sid, {})
        if clip.get("file"):
            row.append(f"<figure><video controls preload='none' src='shots/{e(clip['file'])}'></video><figcaption>clip: {e(clip['source'])}</figcaption></figure>")
        block.append("<div class='row'>" + "".join(row) + "</div></section>")
        parts += block

    css = ("body{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#222}"
           "section{border-top:1px solid #ddd;padding:1rem 0}h2 small{font-weight:normal;color:#666;font-size:.75em}"
           ".row{display:flex;gap:12px;flex-wrap:wrap}figure{margin:0;width:240px}img,video{width:100%;border-radius:6px;background:#eee}"
           "figcaption{font-size:.85em;color:#555}.pick img{outline:4px solid #2a7}.bad{color:#b00020}.ok{color:#176}.line{font-size:1.15em}")
    page = f"<!doctype html><html lang='en'><meta charset='utf-8'><title>{e(sb['title'])} review</title><style>{css}</style><body>" + "\n".join(p for p in parts if p) + "</body></html>"
    out = ctx.out / "review.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    ctx.say(f"  wrote {out.relative_to(ctx.root)}: open it in a browser")
    return out
