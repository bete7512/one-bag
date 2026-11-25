"""The film's public page: python -m pipeline site -> site/index.html

One static page, built from what is in the repository and nothing else: the storyboard, the kept
model outputs, the run log, the failure and experiment journals. So it cannot say more than the
repository shows. Before the film exists it says so and shows the work so far. It needs no server
and no key, and a GitHub workflow publishes it on every push.

Pictures and sound are made web-sized by FFmpeg at build time, from the same originals the film
is cut from.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

from . import pricing
from .narration import LANGUAGE_NAMES
from .core import STAGES, Ctx, ff, get_index, now, read_jsonl, sha

CSS = """
:root{--ink:#f2ece1;--soft:#b9ae9d;--bg:#17130f;--card:#221c16;--line:#3a3027;--amber:#e0a34a;--teal:#5fb3a8;--bad:#e2725b}
*{box-sizing:border-box}html{background:var(--bg)}
body{font:17px/1.6 Georgia,'Noto Serif','Times New Roman',serif;color:var(--ink);max-width:1080px;margin:0 auto;padding:0 20px 80px}
h1{font-size:56px;line-height:1.05;margin:64px 0 8px;letter-spacing:-.5px}h2{font-size:28px;margin:64px 0 12px;color:var(--amber)}
h3{font-size:19px;margin:0 0 4px}p{margin:0 0 14px}a{color:var(--teal)}small,.soft{color:var(--soft)}
.lead{font-size:22px;color:var(--soft);max-width:720px}.tag{display:inline-block;font:13px/1 system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;
border:1px solid var(--line);border-radius:999px;padding:6px 10px;margin:0 6px 6px 0;color:var(--soft)}.tag.ok{color:var(--teal);border-color:var(--teal)}
.tag.wait{color:var(--amber);border-color:var(--amber)}.films{display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start;margin-top:20px}
.films figure{margin:0}.films video{display:block;border-radius:10px;background:#000;max-width:100%}.films .v video{height:560px}.films .h video{width:640px}
figcaption{font:14px/1.4 system-ui,sans-serif;color:var(--soft);margin-top:6px}.notice{border-left:3px solid var(--amber);padding:10px 16px;background:var(--card);border-radius:0 8px 8px 0}
.shots{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:22px}.shot{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.shot img,.shot .empty{display:block;width:100%;aspect-ratio:1;object-fit:cover;background:#120f0c}.shot .empty{display:flex;align-items:center;justify-content:center;color:var(--soft);
font:14px system-ui,sans-serif;text-align:center;padding:20px}.shot .in{padding:14px 16px 16px}.shot .meta{font:13px/1.4 system-ui,sans-serif;color:var(--soft);margin-bottom:8px}
.am{font-size:19px;margin:10px 0 2px}.en{color:var(--soft);font-style:italic;margin:0 0 8px}.why{font-size:15px}audio{width:100%;height:34px;margin-top:6px}
table{border-collapse:collapse;width:100%;font:15px/1.45 system-ui,sans-serif;margin:8px 0 14px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--soft);font-weight:600}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}code{font:14px ui-monospace,Menlo,Consolas,monospace;background:var(--card);padding:1px 5px;border-radius:4px}
.flow{display:flex;flex-wrap:wrap;gap:8px;align-items:stretch;font:14px/1.35 system-ui,sans-serif;margin:14px 0}.flow div{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:10px 12px;flex:1 1 150px}.flow b{display:block;color:var(--amber);margin-bottom:2px}ul{padding-left:20px;margin:0 0 14px}li{margin-bottom:6px}
footer{margin-top:72px;padding-top:18px;border-top:1px solid var(--line);font:14px/1.5 system-ui,sans-serif;color:var(--soft)}
@media(max-width:640px){h1{font-size:40px}.films .v video{height:auto;width:100%}.films .h video{width:100%}}
"""

STAGE_NOTES = {
    "script": "Settles the words. A missing subtitle is translated by a model, everything else is written by hand.",
    "narration": "All lines in one speech request, cut into one file per shot. Each line is transcribed back and compared with the script.",
    "keyframes": "A reference sheet for each character, two candidates per shot, a measured border check and a judge. A person has the last word.",
    "shots": "Each still becomes a moving clip: a slow pan or zoom made here, or image-to-video on a rented GPU.",
    "music": "An original score, generated as three candidates. One is chosen by ear, under the voice.",
    "assemble": "FFmpeg cuts picture to voice, ducks the score, burns in subtitles, normalises loudness and exports both shapes.",
}


def e(text: object) -> str:
    return html.escape(str(text))


def said(text: str) -> str:
    """A sentence from the storyboard. One that is still marked DRAFT is shown as a draft, without the marker."""
    if not text.strip().upper().startswith("DRAFT"):
        return e(text)
    head, colon, tail = text.partition(":")  # "DRAFT, confirm or rewrite: the sentence" or just "DRAFT, the sentence"
    plain = tail.strip() if colon and len(head) < 40 else re.sub(r"^\s*DRAFT[\s,.;-]*", "", text, flags=re.I)
    return f"{e(plain[:1].upper() + plain[1:])} <small>(a draft, not yet confirmed by the author)</small>"


def repo_url(ctx: Ctx) -> str | None:
    if os.environ.get("GITHUB_REPOSITORY"):
        return f"https://github.com/{os.environ['GITHUB_REPOSITORY']}"
    try:
        url = subprocess.run(["git", "config", "--get", "remote.origin.url"], cwd=ctx.root, capture_output=True, text=True).stdout.strip()
    except OSError:
        return None
    url = re.sub(r"^git@github\.com:", "https://github.com/", url)
    return re.sub(r"\.git$", "", url) if url.startswith("https://github.com/") else None


def journal(path: Path, prefix: str) -> list[tuple[str, str]]:
    """Entries of a journal file: (id, title) for every `### F01  title  (date)` heading."""
    if not path.exists():
        return []
    found = re.findall(rf"^### ({prefix}\d+)\s+(.+?)\s*$", path.read_text(encoding="utf-8"), re.M)
    return [(ident, title) for ident, title in found]


def picture(ctx: Ctx, sid: str, key: dict, media: Path) -> str | None:
    """A web-sized copy of a shot's picked keyframe, or None when the shot has no picture yet.

    It is cut from the model's untouched original, the way the film's keyframe is: the original is found
    under the hash of what was sent to the model, which the stage's manifest holds for the picked candidate.
    """
    if not key or key.get("blocked") or not key.get("candidate"):
        return None
    folder = ctx.out / "keyframes"
    unit_id = f"{sid}_c{key['candidate']}"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8")) if (folder / "manifest.json").exists() else {"units": {}}
    sent = {k: v for k, v in manifest["units"].get(unit_id, {}).get("fingerprint", {}).items() if k != "trim"}
    source = next(iter(sorted((folder / "original").glob(f"{unit_id}__{sha(sent)[:16]}.*"))), None) if sent else None
    if source is None:
        return None
    trim = ctx.sb["format"].get("edge_trim", 0.0)
    side = 720
    grown = round(side * (1 + 2 * trim))
    ff(["-i", str(source), "-vf", f"scale={grown}:{grown}:force_original_aspect_ratio=increase:flags=lanczos,crop={side}:{side}",
        "-frames:v", "1", "-q:v", "4", str(media / f"{sid}.jpg")])
    return f"media/{sid}.jpg"


def measured(ctx: Ctx) -> tuple[str, dict]:
    """A table of what the run log holds, one row per model."""
    runs = read_jsonl(ctx.runlog)
    rows: dict = defaultdict(lambda: {"calls": 0, "failed": 0, "seconds": 0.0, "usd": 0.0, "gpu": 0.0})
    for r in runs:
        row = rows[(r.get("provider", "?"), r.get("model", "?"))]
        row["calls"] += 1
        row["failed"] += r.get("status") != "ok"
        row["seconds"] += r.get("latency_s") or 0.0
        row["gpu"] += r.get("gpu_minutes") or 0.0
        cost = r.get("cost_usd")
        row["usd"] += (cost if cost is not None else pricing.cost_usd(r, ctx.prices)) or 0.0
    body = "".join(f"<tr><td>{e(provider)}</td><td><code>{e(model)}</code></td><td class='n'>{row['calls']}</td><td class='n'>{row['failed']}</td>"
                   f"<td class='n'>{row['seconds'] / max(1, row['calls']):.1f}</td><td class='n'>{row['gpu']:.1f}</td><td class='n'>{row['usd']:.4f}</td></tr>"
                   for (provider, model), row in sorted(rows.items()))
    total = {"calls": len(runs), "failed": sum(r.get("status") != "ok" for r in runs), "usd": sum(row["usd"] for row in rows.values())}
    table = ("<table><tr><th>Provider</th><th>Model</th><th class='n'>Calls</th><th class='n'>Failed</th><th class='n'>Mean seconds</th>"
             "<th class='n'>GPU minutes</th><th class='n'>List price, USD</th></tr>" + body + "</table>")
    return table, total


def run(ctx: Ctx) -> Path:
    sb, lang, sub = ctx.sb, ctx.narration_lang, ctx.sb["language"]["subtitles"]
    out = ctx.root / ("site_mock" if ctx.mock else "site")
    media = out / "media"
    if out.exists():
        shutil.rmtree(out)
    media.mkdir(parents=True)

    keyframes = get_index(ctx, {}, "keyframes", required=False)
    narration = get_index(ctx, {}, "narration", per_lang=True, required=False)
    shots = get_index(ctx, {}, "shots", per_lang=True, required=False)
    film_path = ctx.out / "assemble" / f"index.film.{lang}.json"
    film = json.loads(film_path.read_text(encoding="utf-8")) if film_path.exists() else {}
    qc_path = ctx.out / "qc_report.json"
    qc = json.loads(qc_path.read_text(encoding="utf-8")) if qc_path.exists() else {}
    repo = repo_url(ctx)

    # ---- the film, or an honest notice
    drafts = [k for k in ("audience", "intent") if sb[k].strip().upper().startswith("DRAFT")]
    unconfirmed = [s["id"] for s in sb["shots"] if s.get("review") and not s["review"]["confirmed"]]
    players = []
    for exp in sb["format"]["exports"]:
        name = film.get("files", {}).get(exp["name"])
        if name and (ctx.out / name).exists():
            shutil.copy2(ctx.out / name, media / name)
            css = "v" if exp["height"] > exp["width"] else "h"
            players.append(f"<figure class='{css}'><video controls preload='metadata' playsinline src='media/{e(name)}'></video>"
                           f"<figcaption>{e(exp['name'])}, {exp['width']} x {exp['height']}</figcaption></figure>")
    finished = bool(players) and qc.get("passed") and not drafts and not unconfirmed
    tags = [f"<span class='tag {'ok' if finished else 'wait'}'>{'finished' if finished else 'work in progress'}</span>",
            "<span class='tag'>made with AI</span>", f"<span class='tag'>narrated in {e(LANGUAGE_NAMES.get(lang, lang))}, subtitles in {e(LANGUAGE_NAMES.get(sub, sub))}</span>"]
    if film.get("total_s"):
        tags.append(f"<span class='tag'>{film['total_s']:.0f} seconds</span>")
    if players and not finished:
        why = [f"{len(unconfirmed)} lines are not confirmed by the author" if unconfirmed else "", "the audience and intent are still a draft" if drafts else "",
               "the final-cut check has not passed" if not qc.get("passed") else ""]
        notice = "<p class='notice'>This cut is not final: " + ", ".join(w for w in why if w) + ".</p>"
    elif not players:
        notice = ("<p class='notice'>The film is not made yet. This page is built from the repository, so it shows exactly how far the work has come: "
                  "the storyboard, the pictures that exist, and what has been measured.</p>")
    else:
        notice = ""
    radio = ctx.out / "radio_cut.mp4"
    if radio.exists() and not players:
        shutil.copy2(radio, media / radio.name)
        players.append(f"<figure class='v'><video controls preload='metadata' playsinline src='media/{radio.name}'></video>"
                       "<figcaption>the radio cut: the narration over placeholder music, before any picture</figcaption></figure>")

    # ---- shot by shot
    people = {c["id"]: c for c in sb["characters"]}
    cards = []
    for s in sb["shots"]:
        sid = s["id"]
        img = picture(ctx, sid, keyframes.get(sid, {}), media)
        if img:
            top = f"<img loading='lazy' alt='{e(s['title'])}' src='{img}'>"
        else:  # said from the storyboard as it is now, not from the last run
            waiting = [c for c in s["characters"] if people[c]["real_person"] and people[c]["consent"]["status"] != "recorded"]
            top = f"<div class='empty'>{'waiting for a consent record' if waiting else 'not drawn yet'}</div>"
        clip = shots.get(sid, {}).get("source", s["motion"]["backend"])
        motion = {"wan": "moving clip from Wan 2.2", "kenburns": "pan and zoom over the still", "kenburns_fallback": "pan and zoom, until its Wan clip is made"}.get(clip, clip)
        words = ""
        if s["narration"]:
            words = f"<p class='am' lang='{e(lang)}'>{e(s['narration'].get(lang, ''))}</p><p class='en'>{e(s['narration'].get(sub, ''))}</p>"
            spoken = narration.get(sid, {})
            if spoken.get("file") and (ctx.out / "narration" / spoken["file"]).exists():
                ff(["-i", str(ctx.out / "narration" / spoken["file"]), "-c:a", "aac", "-b:a", "96k", str(media / f"{sid}.m4a")])
                words += f"<audio controls preload='none' src='media/{sid}.m4a'></audio>"
            if s.get("review") and not s["review"]["confirmed"]:
                words += "<p class='meta'>Draft line, not yet confirmed by the author.</p>"
        cards.append(f"<article class='shot'>{top}<div class='in'><h3>{e(sid)} &middot; {e(s['title'])}</h3>"
                     f"<p class='meta'>{e(s['size'])} &middot; {e(motion)}</p>{words}<p class='why'>{e(s['reason'])}</p></div></article>")

    # ---- how it is made, what was measured, what broke
    models = sb["models"]
    stage_models = {"script": models["text"], "narration": models["tts"], "keyframes": models["image"], "shots": models["video"],
                    "music": models["music"], "assemble": "FFmpeg"}
    flow = "".join(f"<div><b>{n}. {e(name)}</b>{e(stage_models[name].split('/')[-1])}<br><span class='soft'>{e(STAGE_NOTES[name])}</span></div>"
                   for n, name in enumerate(STAGES, start=1))
    table, total = measured(ctx)
    paid = sum((r.get("cost_usd") or 0.0) for r in read_jsonl(ctx.runlog) if (ctx.prices.get(r.get("model")) or {}).get("paid"))
    paid_line = f"Really paid: {paid:.2f} USD, for the one model that has no free tier." if paid else "Nothing was paid."
    failures, experiments = journal(ctx.root / "FAILURES.md", "F"), journal(ctx.root / "EXPERIMENTS.md", "E")
    link = (lambda name: f"<a href='{repo}/blob/main/{name}'>{name}</a>") if repo else (lambda name: f"<code>{name}</code>")
    recorded = sorted({c["consent"]["record"] for c in sb["characters"] if c["real_person"] and c["consent"]["status"] == "recorded"})
    pending = sorted({c["id"] for c in sb["characters"] if c["real_person"] and c["consent"]["status"] != "recorded"})

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(sb['title'])}: a heritage short made by a pipeline</title><style>{CSS}</style></head><body>
<header><h1>{e(sb['title'])}</h1>
<p class="lead">A short film about one night, narrated in the language it happened in. It is not edited by hand: a pipeline turns one storyboard file into the film.</p>
<p>{''.join(tags)}</p></header>
{notice}
<div class="films">{''.join(players)}</div>

<h2>Who it is for</h2>
<p><b>Audience.</b> {said(sb['audience'])}</p>
<p><b>What they should feel.</b> {said(sb['intent'])}</p>

<h2>Shot by shot</h2>
<p class="soft">Every shot has a reason, written before its picture was made. The words under each picture are what the voice says, and what the subtitle shows.</p>
<div class="shots">{''.join(cards)}</div>

<h2>How it is made</h2>
<p>One file, {link('storyboard.json')}, is the contract: every shot, its reason, its prompts and seeds, its line, and the models to use. Six stages read it. Each piece of work is stored under a hash of its inputs, so changing one shot rebuilds that shot and nothing else.</p>
<div class="flow">{flow}</div>
<p>The details are in {link('ARCHITECTURE.md')}, and the one command is <code>make film</code>.</p>

<h2>What it took</h2>
<p>Every attempt to call a model is one line in {link('runs.jsonl')}: {total['calls']} attempts so far, {total['failed']} of them failed. The list price of all of it is {total['usd']:.2f} USD. Most of the film is made on free tiers, so that price says what the same work costs without them. {paid_line}</p>
{table}
<p>The limits of those free tiers, and what happened at each, are in {link('COSTS.md')}.</p>

<h2>What broke, and what was tried</h2>
<p>{len(failures)} failures and {len(experiments)} experiments are written up so far, each with its evidence.</p>
<ul>{''.join(f'<li><b>{e(i)}</b> {e(t)}</li>' for i, t in failures) or '<li>No failure logged yet.</li>'}</ul>
<p>From {link('FAILURES.md')}.</p>
<ul>{''.join(f'<li><b>{e(i)}</b> {e(t)}</li>' for i, t in experiments) or '<li>No experiment run yet.</li>'}</ul>
<p>From {link('EXPERIMENTS.md')}.</p>

<h2>Made with AI, with consent</h2>
<p>The pictures, the voice and the music are generated by AI models, and the film ends with a card that says so. No photo of a real person and no recording of a real voice is used. The people in the story appear as drawn characters, and only after their consent was recorded: {len(recorded)} consent record{'s' if len(recorded) != 1 else ''} so far{', none missing' if not pending else ', ' + str(len(pending)) + ' character(s) still waiting'}. A shot that shows someone whose consent is missing is not generated at all. Consent, licences and the labelling plan are in {link('ETHICS.md')}.</p>

<footer>{e(sb['end_card']['lines'][-1])}. Built {now()[:10]} from {f"<a href='{repo}'>the repository</a>" if repo else 'the repository'} by <code>python -m pipeline site</code>.</footer>
</body></html>
"""
    (out / "index.html").write_text(page, encoding="utf-8")
    ctx.say(f"  wrote {(out / 'index.html').relative_to(ctx.root)}: open it in a browser")
    return out
