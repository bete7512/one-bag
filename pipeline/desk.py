"""The author's desk: python -m pipeline desk -> one page on http://127.0.0.1:8765

Some of the film is not the pipeline's to decide, and not a coding agent's either: whether a line
is in the author's own words, which picture is the right one, which score, who the film is for.
Those answers live in storyboard.json, and giving them meant editing JSON by hand. This page shows
every shot with its picture, its candidates, its line and its recording, and saves each click and
each changed sentence into the storyboard.

What it cannot do, on purpose:

* It runs no stage and calls no model. It edits the storyboard and shows the plan, the one that
  `python -m pipeline plan` prints. Making the film stays a command.
* It does not change consent. `consent`, `real_person` and ETHICS.md are shown and never edited:
  a consent is written down by hand, with its date, by the person who received it.

How it saves. storyboard.json is written by hand, with small objects kept on one line, and a
`json.dumps` rewrite would reformat every line of it. So an edit changes only the text of the one
value: a small scanner finds where that value sits in the file, and a key that is missing is added
to its object the way the object is already written. Before anything is written, the change is made
on a copy and checked like any storyboard, the new text is parsed and compared with that copy, and
the file is replaced in one step. An edit that fails any of this is refused with the reason, and
the file stays as it was.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from . import cli
from .core import STAGES, Ctx, PipelineError, check_storyboard, consent_rows, ff, get_index, make_ctx, sha
from .keyframes import BORDER_SIDES, CUT_KEYS
from .site import CSS as SITE_CSS, e

# Everything the page may change, as paths into the storyboard. A shot is named by its id. Any other path is refused.
EDITABLE = (r"audience", r"intent", r"music\.chosen", r"music\.chosen_reason",
            r"shots\.s\d\d\.narration\.[a-z]{2,3}", r"shots\.s\d\d\.review\.confirmed", r"shots\.s\d\d\.keyframe\.pick")
# What the page may load besides itself: files the cache named, so a request cannot reach anything else on disk.
PICTURE = re.compile(r"/media/keyframes/([a-z0-9_]+__[0-9a-f]{16})\.jpg")
SOUND = re.compile(r"/media/(narration|music)/([a-z0-9_]+__[0-9a-f]{16}\.(?:wav|flac))")


class Refused(PipelineError):
    """An edit the desk does not make. The file is left as it was."""


# ----------------------------------------------------------------------------- one value in the text of the file

_scan = json.JSONDecoder().raw_decode  # (text, start) -> (the value that starts there, where it ends)


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _skip(text: str, i: int) -> int:
    while text[i] in " \t\n\r":
        i += 1
    return i


def _held(text: str, start: int) -> tuple[list[tuple[Any, int, int, int]], int]:
    """What the object or list that opens at `start` holds, and where it closes.

    One entry per member: (its key, or the item itself in a list, where the member starts, where its value starts, where its value ends).
    """
    held, named, i = [], text[start] == "{", _skip(text, start + 1)
    while text[i] not in "}]":
        begins, key = i, None
        if named:
            key, i = _scan(text, i)
            i = _skip(text, _skip(text, i) + 1)  # over the colon
        value, ends = _scan(text, i)
        held.append((key if named else value, begins, i, ends))
        i = _skip(text, ends)
        if text[i] == ",":
            i = _skip(text, i + 1)
    return held, i


def _named(step: str, n: int, item: Any) -> bool:
    """In a list, a step names the item with that id, or the item at that index."""
    return (isinstance(item, dict) and item.get("id") == step) or str(n) == step


def _insert(text: str, start: int, held: list, close: int, key: str, value: Any) -> str:
    """Add a member to the object that opens at `start`, written the way the object already is: on one line, or a member per line."""
    member = f"{_dump(key)}: {_dump(value)}"
    if not held:
        return text[:start + 1] + member + text[close:]
    begins, ends = held[-1][1], held[-1][3]
    if len(held) > 1:
        gap = text[held[-2][3]:begins].partition(",")[2]  # what stands between the comma and the last member
    else:
        gap = text[start + 1:begins]
        gap = gap if "\n" in gap else " "                # {"a": 1} grows to {"a": 1, "b": 2}
    return text[:ends] + "," + gap + member + text[ends:]


def edit_text(text: str, path: list[str], value: Any) -> str:
    """The text of a JSON file with one value changed and every other character left alone.

    `path` leads to the value: object keys, and in a list the id of an item or its index. A key that
    its object does not have yet is added before the closing brace.
    """
    at = _skip(text, 0)
    for depth, step in enumerate(path):
        here = ".".join(path[:depth]) or "the storyboard"
        if text[at] not in "{[":
            raise Refused(f"{here} holds no {step}")
        held, close = _held(text, at)
        if text[at] == "{":
            found = [member for member in held if member[0] == step]
            if not found:
                for key in reversed(path[depth + 1:]):
                    value = {key: value}
                return _insert(text, at, held, close, step, value)
        else:
            found = [member for n, member in enumerate(held) if _named(step, n, member[0])]
            if not found:
                raise Refused(f"{here} holds no {step}")
        at = found[-1][2]
    return text[:at] + _dump(value) + text[_scan(text, at)[1]:]


def set_in(data: Any, path: list[str], value: Any) -> None:
    """The same change on parsed data: what the file has to hold afterwards."""
    node = data
    for depth, step in enumerate(path):
        here, last = ".".join(path[:depth]) or "the storyboard", depth == len(path) - 1
        if isinstance(node, dict):
            if last:
                node[step] = value
            else:
                node = node.setdefault(step, {})
        elif isinstance(node, list) and any(_named(step, n, item) for n, item in enumerate(node)):
            at = [n for n, item in enumerate(node) if _named(step, n, item)][-1]
            if last:
                node[at] = value
            else:
                node = node[at]
        else:
            raise Refused(f"{here} holds no {step}")


# ----------------------------------------------------------------------------- one edit of the file


def stamp(text: str) -> str:
    """A short name for one state of the file. The page sends it back with every edit."""
    return sha(text)[:16]


def read_text(root: Path) -> str:
    # bytes, not read_text: the line endings of the file are not ours to change
    return (root / "storyboard.json").read_bytes().decode("utf-8")


def apply_edit(root: Path, path: str, value: Any, seen: str | None = None) -> dict:
    """Change one value of storyboard.json. Raises `Refused` with the reason, and then the file is as it was.

    `seen` is the stamp of the file the edit was made against. When the file has changed since, by hand
    or by a coding agent, the edit is refused: a line is never confirmed in a wording its author has not read.
    """
    if re.search(r"^characters(\.|$)|(^|\.)(consent|real_person)(\.|$)", path):
        raise Refused("Consent is not changed from this page. It is recorded by hand: a dated row in ETHICS.md, then the status in storyboard.json.")
    if not any(re.fullmatch(pattern, path) for pattern in EDITABLE):
        raise Refused(f"{path} is not edited from this page.")
    if isinstance(value, float):
        raise Refused(f"{path} takes a whole number, not {value}")
    if isinstance(value, str):
        value = value.strip()  # a stray space at the end of a line is a new line to the cache, and would cost a speech request

    file = root / "storyboard.json"
    text = read_text(root)
    if seen is not None and seen != stamp(text):
        raise Refused("storyboard.json has changed on disk since this page was loaded. Reload the page, then make the change again.")
    now, steps = json.loads(text), path.split(".")
    wanted = copy.deepcopy(now)
    set_in(wanted, steps, value)
    if wanted == now:
        return {"changed": False, "value": value, "seen": stamp(text)}
    errors = [f"[{code}] {msg}" for level, code, msg in check_storyboard(wanted, root) if level == "error"]
    if errors:
        raise Refused("The storyboard would not be valid: " + "; ".join(errors))
    new = edit_text(text, steps, value)
    if json.loads(new) != wanted:
        raise Refused(f"{path} could not be changed without touching something else in the file. Nothing was saved.")
    tmp = file.with_name(f"tmp-{uuid.uuid4().hex[:8]}-{file.name}")
    try:
        tmp.write_bytes(new.encode("utf-8"))
        shutil.copymode(file, tmp)
        os.replace(tmp, file)  # atomic: a reader never sees half a storyboard
    finally:
        tmp.unlink(missing_ok=True)
    return {"changed": True, "value": value, "seen": stamp(new)}


# ----------------------------------------------------------------------------- what the page shows


def plan_text(ctx: Ctx) -> str:
    """What `python -m pipeline plan` prints for this project: the storyboard's warnings, then every unit and whether the next run builds it."""
    lines = [f"  warning [{code}] {msg}" for level, code, msg in check_storyboard(ctx.sb, ctx.root) if level == "warning"]
    ctx = dataclasses.replace(ctx)
    ctx.say = lines.append  # the stages report through ctx.say: keep what they would print
    try:
        cli.run_stages(ctx, STAGES, plan_only=True)
    except PipelineError as err:
        lines.append(f"error: {err}")
    return "\n".join(lines)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def original(ctx: Ctx, units: dict, unit_id: str) -> str | None:
    """The file name, without its extension, of the kept original of one candidate. None when it is not drawn.

    Found the way `picture` in site.py finds it: under the hash of what was sent to the model. The
    keyframe cut from it is git-ignored, so a clean clone has the original and nothing else.
    """
    sent = {k: v for k, v in units.get(unit_id, {}).get("fingerprint", {}).items() if k not in CUT_KEYS}
    stem = f"{unit_id}__{sha(sent)[:16]}"
    return stem if sent and any((ctx.out / "keyframes" / "original").glob(f"{stem}.*")) else None


def web_picture(ctx: Ctx, stem: str, folder: Path) -> Path | None:
    """A web-sized copy of one kept original, cut like the film's keyframe: scaled, with `format.edge_trim` taken off each side."""
    source = next(iter(sorted((ctx.out / "keyframes" / "original").glob(f"{stem}.*"))), None)
    if source is None:
        return None
    trim, side = ctx.sb["format"].get("edge_trim", 0.0), 720
    out = folder / f"{stem}_{trim}.jpg"
    if not out.exists():
        grown = round(side * (1 + 2 * trim))
        tmp = out.with_name(f"tmp-{uuid.uuid4().hex[:8]}-{out.name}")
        ff(["-i", str(source), "-vf", f"scale={grown}:{grown}:force_original_aspect_ratio=increase:flags=lanczos,crop={side}:{side}",
            "-frames:v", "1", "-q:v", "4", str(tmp)])
        os.replace(tmp, out)
    return out


def area(path: str, text: str, label: str, lang: str = "en", rows: int = 2, more: str = "") -> str:
    """One sentence to edit: a text area bound to a path in the storyboard."""
    return (f"<label for='{e(path)}'>{e(label)}</label>"
            f"<textarea id='{e(path)}' data-path='{e(path)}' lang='{e(lang)}' rows='{rows}'{more}>{e(text)}</textarea>")


def radio(name: str, value: object, checked: bool, enabled: bool = True) -> str:
    return f"<input type='radio' name='{e(name)}' value='{e(value)}'{' checked' if checked else ''}{'' if enabled else ' disabled'}>"


def shot_card(ctx: Ctx, shot: dict, picked: dict, units: dict, spoken: dict, said: dict) -> str:
    """One shot: its picture and candidates from the keyframe index and manifest, its words, its recording, and what the author decides."""
    sb, sid, lang, sub = ctx.sb, shot["id"], ctx.narration_lang, ctx.sb["language"]["subtitles"]
    people = {c["id"]: c for c in sb["characters"]}

    # the picture: every candidate, and the one the film would use
    count = shot["keyframe"].get("candidates", sb.get("qa", {}).get("keyframe_candidates", 1))
    mine, auto = shot["keyframe"].get("pick"), picked.get("candidate")
    stems = {n: original(ctx, units, f"{sid}_c{n}") for n in range(1, count + 1)}
    tiles = []
    for n, stem in stems.items():
        view, caption = "", "not drawn yet"
        if stem:
            total = units.get(f"{sid}_c{n}_judge", {}).get("meta", {}).get("total")
            sides = picked.get("paper_sides", {}).get(str(n))
            bordered = " class='bad'" if sides is not None and sides >= BORDER_SIDES else ""
            view = f"<img loading='lazy' alt='candidate {n}' src='/media/keyframes/{stem}.jpg'>"
            caption = ("not judged" if total is None else f"judge {e(total)}") + " &middot; " + (
                "border not measured" if sides is None else f"<span{bordered}>bare paper on {e(sides)} of 4 sides</span>")
        tiles.append(f"<label class='cand{' pick' if n == (mine or auto) else ''}' data-n='{n}'>{view}"
                     f"{radio(f'pick-{sid}', n, mine == n, bool(stem))} Candidate {n}<br>{caption}</label>")
    tiles.append(f"<label class='free'>{radio(f'pick-{sid}', '', not mine)} No pick of mine: the border check and the judge choose</label>")
    use = stems.get(mine or auto)
    waiting = [c for c in shot["characters"] if people[c]["real_person"] and people[c]["consent"]["status"] != "recorded"]
    auto_by = f"the last run ({picked['picked_by']})" if picked.get("picked_by") else "the last run"
    by = f"Candidate {mine or auto}, picked by {'the author' if mine else auto_by}." if mine or auto else ""
    shown = f" src='/media/keyframes/{use}.jpg'" if use else " hidden"
    left = (f"<div class='pic'><img class='picked' alt='{e(shot['title'])}'{shown}>"
            f"<div class='empty'{' hidden' if use else ''}>{'waiting for a consent record' if waiting else 'not drawn yet'}</div>"
            f"<p class='meta by'>{e(by)}</p></div>")

    # the words, and the recording of them
    if shot["narration"] is None:
        words = "<p class='meta'>No words in this shot.</p>"
    else:
        line = shot["narration"].get(lang, "")
        given = said.get(sid, {}).get("text", line)  # the wording the last run was given to speak
        words = area(f"shots.{sid}.narration.{lang}", line, f"What the voice says ({lang})", lang, more=f" data-spoken='{e(given)}'")
        if sub != lang:
            words += area(f"shots.{sid}.narration.{sub}", shot["narration"].get(sub, ""), f"Subtitle ({sub})", sub)
        take = spoken.get(sid, {})
        if take.get("file") and (ctx.out / "narration" / take["file"]).exists():
            check = f" The listening check heard: {e(take['heard'])} (match {take['roundtrip']:.2f})." if take.get("roundtrip") is not None else ""
            words += (f"<audio controls preload='none' src='/media/narration/{e(take['file'])}'></audio>"
                      f"<p class='meta'>{take.get('seconds', 0):.1f} s.{check}</p>"
                      f"<p class='meta bad stale'{'' if given != line else ' hidden'}>This recording is of an earlier wording. The next run speaks the line again.</p>")

    review = shot.get("review") or {}
    note = f"<p class='meta'>To check: {e(review['note'])}</p>" if review.get("note") else ""
    return (f"<article class='shot' id='{e(sid)}' data-auto='{auto or ''}' data-auto-by='{e(auto_by)}'>{left}<div class='in'>"
            f"<h3>{e(sid)} &middot; {e(shot['title'])}</h3><p class='meta'>{e(shot['size'])}</p><p class='why'>{e(shot['reason'])}</p>{words}"
            f"<div class='cands' data-path='shots.{e(sid)}.keyframe.pick' data-saved='{mine or ''}'>{''.join(tiles)}</div>{note}"
            f"<label class='check' data-path='shots.{e(sid)}.review.confirmed'><input type='checkbox'{' checked' if review.get('confirmed') else ''}>"
            f" Confirmed by the author</label></div></article>")


def score(ctx: Ctx) -> str:
    """The score: one choice per seed, open once that candidate has come back from the GPU job, and the reason for the choice."""
    music, units = ctx.sb["music"], _load(ctx.out / "music" / "manifest.json").get("units", {})
    chosen = music["chosen"]
    rows = [f"<label class='free'>{radio('chosen', '', chosen is None)} None yet: the placeholder plays</label>"]
    for n, seed in enumerate(music["seeds"], start=1):
        name = units.get(f"candidate_{n}", {}).get("file")
        ready = bool(name) and (ctx.out / "music" / name).exists()
        rows.append(f"<label class='free'>{radio('chosen', n, chosen == n, ready)} Candidate {n}, seed {seed}{'' if ready else ': not generated yet'}</label>"
                    + (f"<audio controls preload='none' src='/media/music/{e(name)}'></audio>" if ready else ""))
    return (f"<div data-path='music.chosen' data-saved='{'' if chosen is None else chosen}'>{''.join(rows)}</div>"
            + area("music.chosen_reason", music.get("chosen_reason", ""), "Why this one"))


def consent(ctx: Ctx) -> str:
    """Who is in the film and where their consent stands. A table, with nothing in it to click."""
    dated = consent_rows(ctx.root)
    rows = []
    for c in ctx.sb["characters"]:
        record = c["consent"].get("record")
        date = dated.get(record, {}).get("date")
        where = "" if not record else f"<code>{e(record)}</code>, " + (f"dated {e(date)} in ETHICS.md" if date else "no dated row in ETHICS.md")
        rows.append(f"<tr><td>{e(c.get('label', c['id']))}</td><td>{'yes' if c['real_person'] else 'no'}</td>"
                    f"<td>{e(c['consent']['status'])}</td><td>{where}</td></tr>")
    return "<table><tr><th>Who</th><th>A real person</th><th>Consent</th><th>Record</th></tr>" + "".join(rows) + "</table>"


CSS = """
[hidden]{display:none!important}.shots{grid-template-columns:1fr}.shot{display:grid;grid-template-columns:minmax(0,340px) minmax(0,1fr);align-items:start}
.shot .by{padding:8px 16px;margin:0}label{display:block;font:13px/1.4 system-ui,sans-serif;color:var(--soft);margin:12px 0 4px}
textarea{display:block;width:100%;font:inherit;color:var(--ink);background:#120f0c;border:1px solid var(--line);border-radius:8px;padding:8px 10px;resize:vertical}
textarea:focus{outline:none;border-color:var(--teal)}textarea.unsaved{border-color:var(--amber)}textarea.refused{border-color:var(--bad)}
input{accent-color:var(--amber)}.bad,.shot .meta.bad{color:var(--bad)}.cands{display:flex;flex-wrap:wrap;gap:4px 12px;margin:14px 0 10px}
.cand{width:150px;margin:0}.cand img{border-radius:8px;border:2px solid var(--line);margin-bottom:4px}.cand.pick img{border-color:var(--amber)}
.free{flex-basis:100%;margin:6px 0 0}.check{font-size:15px;color:var(--ink);margin-top:14px}
.plan{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;font:13px/1.5 ui-monospace,Menlo,Consolas,monospace;
white-space:pre-wrap;color:var(--soft);max-height:560px;overflow:auto}.plan .miss{color:var(--amber)}
#status{position:fixed;right:16px;bottom:16px;max-width:440px;background:var(--card);border:1px solid var(--teal);border-radius:10px;padding:10px 14px;
font:14px/1.4 system-ui,sans-serif}#status.bad{border-color:var(--bad);color:var(--bad)}#status:empty{display:none}
@media(max-width:760px){.shot{grid-template-columns:1fr}}
"""

# Every control saves itself when it changes: one small JSON request per edit, sent one after the other
# so that each carries the stamp the one before it returned.
SCRIPT = """
const note = document.getElementById('status'), plan = document.getElementById('plan');
let seen = document.body.dataset.seen, saves = Promise.resolve(), asked = 0;

function tell(text, kind) { note.textContent = text; note.className = kind; }

function showPlan() {
  const mine = ++asked;
  fetch('/plan').then(reply => reply.text()).then(text => {
    if (mine !== asked) return;
    plan.replaceChildren(...text.split('\\n').map(line => {
      const row = document.createElement('span');
      row.textContent = line + '\\n';
      if (/MISS|BLOCKED|warning|error:/.test(line)) row.className = 'miss';
      return row;
    }));
  }).catch(() => { plan.textContent = 'The plan could not be read. Is the desk still running?'; });
}

function showPick(card) {
  const mine = card.querySelector('.cands').dataset.saved, n = mine || card.dataset.auto;
  const tile = n ? card.querySelector('.cand[data-n="' + n + '"] img') : null, big = card.querySelector('.picked');
  card.querySelectorAll('.cand').forEach(cand => cand.classList.toggle('pick', cand.dataset.n === n));
  big.hidden = !tile;
  card.querySelector('.pic .empty').hidden = Boolean(tile);
  if (tile) big.src = tile.src;
  card.querySelector('.by').textContent = n ? 'Candidate ' + n + ', picked by ' + (mine ? 'the author' : card.dataset.autoBy) + '.' : '';
}

function undo(box, field) {
  if (box.type === 'checkbox') box.checked = !box.checked;
  else if (box.type === 'radio') field.querySelector('input[value="' + field.dataset.saved + '"]').checked = true;
  else box.className = 'refused';
}

document.addEventListener('input', event => { if (event.target.tagName === 'TEXTAREA') event.target.className = 'unsaved'; });

document.addEventListener('change', event => {
  const box = event.target, field = box.closest('[data-path]');
  if (!field) return;
  const value = box.type === 'checkbox' ? box.checked : box.type === 'radio' ? (box.value === '' ? null : Number(box.value)) : box.value;
  saves = saves.then(() => fetch('/edit', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                          body: JSON.stringify({path: field.dataset.path, value: value, seen: seen})}))
    .then(reply => reply.json())
    .then(reply => {
      if (!reply.ok) throw new Error(reply.error);
      seen = reply.seen;
      if (box.type === 'radio') {
        field.dataset.saved = box.value;
        if (field.className === 'cands') showPick(field.closest('.shot'));
      } else if (box.tagName === 'TEXTAREA') {
        box.value = reply.value;
        box.className = '';
        const old = 'spoken' in box.dataset ? box.closest('.shot').querySelector('.stale') : null;
        if (old) old.hidden = reply.value === box.dataset.spoken;
      }
      tell('Saved ' + field.dataset.path + '.', '');
      showPlan();
    })
    .catch(problem => { undo(box, field); tell('Not saved. ' + problem.message, 'bad'); });
});

showPlan();
"""


def page(ctx: Ctx, seen: str) -> str:
    """The whole desk as one HTML page, from the storyboard and from what the last run left in the outputs folder."""
    sb, lang = ctx.sb, ctx.narration_lang
    keyframes = get_index(ctx, {}, "keyframes", required=False)
    narration = get_index(ctx, {}, "narration", per_lang=True, required=False)
    said = get_index(ctx, {}, "script", per_lang=True, required=False).get("lines", {})
    units = _load(ctx.out / "keyframes" / "manifest.json").get("units", {})
    cards = "".join(shot_card(ctx, shot, keyframes.get(shot["id"], {}), units, narration, said) for shot in sb["shots"])
    mock = "<span class='tag wait'>mock outputs: nothing shown here comes from a real model</span>" if ctx.mock else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(sb['title'])}: the author's desk</title><style>{SITE_CSS}{CSS}</style></head><body data-seen="{e(seen)}">
<header><h1>{e(sb['title'])}</h1>
<p class="lead">The author's desk: the answers only the author can give, by clicking instead of editing JSON.</p>
<p class="notice">This page edits <code>storyboard.json</code> and shows <a href="#next">the plan</a>: it runs no stage and calls no model.</p>
<p>{mock}<span class='tag'>narrated in {e(lang)}, subtitles in {e(sb['language']['subtitles'])}</span></p></header>

<h2>Who it is for</h2>
{area('audience', sb['audience'], 'Audience: who watches, and where', rows=3)}
{area('intent', sb['intent'], 'Intent: what they should feel or understand at the end', rows=3)}

<h2>Shot by shot</h2>
<p class="soft">A sentence is saved when you leave its box, a tick or a choice at once. The picture with the amber edge is the one the film uses.</p>
<div class="shots">{cards}</div>

<h2>The score</h2>
<p class="soft">One candidate per seed. Listen to them at low volume under the voice, choose one and say why.</p>
{score(ctx)}

<h2>Consent</h2>
<p class="soft">Shown here, never changed here. A consent is recorded by hand: a dated row in <code>ETHICS.md</code>, then the status in the storyboard.</p>
{consent(ctx)}

<h2 id="next">What the next run would do</h2>
<p class="soft">The output of <code>python -m pipeline plan</code> for the storyboard as it is now, worked out again after each save. MISS is what the next run builds, and why.</p>
<pre id="plan" class="plan">Working out the plan.</pre>

<footer>Served by <code>python -m pipeline desk</code> from {e(ctx.root)}. Stop it with Ctrl+C in its terminal.</footer>
<div id="status" role="status"></div>
<script>{SCRIPT}</script>
</body></html>
"""


# ----------------------------------------------------------------------------- the server


class Desk(ThreadingHTTPServer):
    """The server, and what its handler needs: which project, mock or real, and one lock so that saves and plans take turns."""

    daemon_threads = True

    def __init__(self, ctx: Ctx, port: int):
        self.root, self.out, self.mock, self.lang, self.say = ctx.root, ctx.out, ctx.mock, ctx.lang, ctx.say
        self.lock = threading.Lock()
        self.cuts = Path(tempfile.mkdtemp(prefix="heritage-desk-"))  # web-sized pictures, gone when the desk stops
        super().__init__(("127.0.0.1", port), Handler)  # this machine only. Last, because a port that is taken closes the server at once

    def project(self) -> Ctx:
        """The project as it is on disk now: the storyboard may have changed since the last request, here or in an editor."""
        return make_ctx(root=self.root, mock=self.mock, lang=self.lang or None, quiet=True)

    def handle_error(self, request: Any, client_address: Any) -> None:
        if not isinstance(sys.exc_info()[1], ConnectionError):  # a browser that stopped waiting, on a reload for example, is not an error
            super().handle_error(request, client_address)

    def server_close(self) -> None:
        super().server_close()
        shutil.rmtree(self.cuts, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    server: Desk

    def log_message(self, *args: Any) -> None:
        pass  # a line per request is noise. Each save is printed instead.

    def answer(self, status: int, body: bytes | str, kind: str = "text/plain; charset=utf-8", keep: bool = False) -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=86400" if keep else "no-store")
        self.end_headers()
        self.wfile.write(data)

    def local(self) -> bool:
        """Refuse a request that reached this machine under another host name: a page from elsewhere must not drive the desk."""
        if self.headers.get("Host", "").rsplit(":", 1)[0] in ("127.0.0.1", "localhost"):
            return True
        self.answer(403, "The desk answers on 127.0.0.1 only.")
        return False

    def do_GET(self) -> None:
        if not self.local():
            return
        desk, path = self.server, urlsplit(self.path).path
        picture, sound = PICTURE.fullmatch(path), SOUND.fullmatch(path)
        try:
            if path == "/":
                seen = stamp(read_text(desk.root))
                self.answer(200, page(desk.project(), seen), "text/html; charset=utf-8")
            elif path == "/plan":
                with desk.lock:
                    self.answer(200, plan_text(desk.project()))
            elif picture:
                cut = web_picture(desk.project(), picture[1], desk.cuts)
                if cut:
                    self.answer(200, cut.read_bytes(), "image/jpeg", keep=True)
                else:
                    self.answer(404, "not drawn yet")
            elif sound and (desk.out / sound[1] / sound[2]).exists():
                self.answer(200, (desk.out / sound[1] / sound[2]).read_bytes(), "audio/flac" if sound[2].endswith(".flac") else "audio/wav", keep=True)
            else:
                self.answer(404, "not found")
        except PipelineError as err:  # a storyboard broken by hand, or no FFmpeg: say so in the browser
            self.answer(500, f"{err}\n\nFix it, then reload this page.")

    def do_POST(self) -> None:
        if not self.local():
            return
        # JSON only: a form on another site cannot send it, so nothing but this page can save
        if urlsplit(self.path).path != "/edit" or self.headers.get_content_type() != "application/json":
            return self.answer(404, "not found")
        try:
            edit = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            path, value, seen = str(edit["path"]), edit["value"], str(edit["seen"])
        except (ValueError, KeyError, TypeError):
            return self.answer(400, json.dumps({"ok": False, "error": "An edit is a JSON object with path, value and seen."}), "application/json")
        try:
            with self.server.lock:
                result = apply_edit(self.server.root, path, value, seen=seen)
        except Refused as err:
            return self.answer(409, json.dumps({"ok": False, "error": str(err)}), "application/json")
        if result["changed"]:
            self.server.say(f"  saved {path}")
        self.answer(200, json.dumps({"ok": True, **result}, ensure_ascii=False), "application/json")


def run(ctx: Ctx, port: int = 8765) -> None:
    """Serve the desk until Ctrl+C."""
    try:
        server = Desk(ctx, port)
    except OSError as err:
        raise PipelineError(f"cannot listen on 127.0.0.1:{port}: {err.strerror}. Choose another port with --port.") from None
    ctx.say(f"  the author's desk is at http://127.0.0.1:{server.server_address[1]}/  (Ctrl+C stops it)")
    ctx.say("  it edits storyboard.json and shows the plan. It runs no stage and calls no model.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        ctx.say("  the desk is closed")
    finally:
        server.server_close()
