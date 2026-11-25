"""Shared plumbing for every stage: storyboard validation, cache, run log, retries, timeline, FFmpeg.

The ideas, in the order a reader needs them:

* storyboard.json is the only contract. `load_storyboard` validates it against the JSON Schema and
  then checks the things a schema cannot express (unknown character ids, consent rows, drafts).
* A stage is a list of `Unit`s. A unit is one thing to produce (one narration line, one keyframe)
  plus a `fingerprint`: every input that can change its output. `run_units` hashes the fingerprint,
  and regenerates the unit only when the hash is new. That is the whole cache.
* Every model call goes through `model_call`, which retries with backoff and writes one line per
  attempt to runs.jsonl: model, parameters, seed, latency, cost, status.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import textwrap
import time
import unicodedata
import uuid
import wave
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable

from . import pricing

ROOT = Path(__file__).resolve().parent.parent
STAGES = ["script", "narration", "keyframes", "shots", "music", "assemble"]
# Bump a stage's number when its logic changes in a way that changes its output, so old cache entries stop matching.
STAGE_VERSION = {"script": 1, "narration": 2, "keyframes": 1, "shots": 1, "music": 1, "assemble": 3}


class PipelineError(Exception):
    """A problem the user can fix. Printed without a traceback."""


class StoryboardError(PipelineError):
    pass


class ProviderError(Exception):
    """A failed model call. `retryable` says whether trying again can help."""

    def __init__(self, message: str, status: int | None = None, retryable: bool = False, retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after


# ----------------------------------------------------------------------------- context


@dataclass
class Ctx:
    root: Path
    sb: dict
    mock: bool = False
    lang: str = ""
    strict: bool = False
    run_id: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6])
    sleep: Callable[[float], None] = time.sleep
    quiet: bool = False
    pause_s: float = 0.0  # wait after each real model call, for free tiers with a low calls-per-minute limit
    _prices: dict | None = field(default=None, repr=False)
    _last_call: dict = field(default_factory=dict, repr=False)  # model -> time of its last request, for the per-minute limit
    _over_allowance: set = field(default_factory=set, repr=False)  # models already announced as over their free allowance in this run

    @property
    def prices(self) -> dict:
        """List prices from pricing.json, read once."""
        if self._prices is None:
            self._prices = pricing.load(self.root)
        return self._prices

    @property
    def out(self) -> Path:
        # Mock runs never share a folder or a log with real runs.
        return self.root / ("outputs_mock" if self.mock else "outputs")

    @property
    def runlog(self) -> Path:
        return self.out / "runs.mock.jsonl" if self.mock else self.root / "runs.jsonl"

    @property
    def narration_lang(self) -> str:
        return self.lang or self.sb["language"]["narration"]

    def say(self, msg: str) -> None:
        if not self.quiet:
            print(msg, flush=True)


def load_env(root: Path) -> None:
    """Read KEY=VALUE lines from .env into the environment. Real environment variables win."""
    env = root / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def make_ctx(root: Path | None = None, mock: bool | None = None, lang: str | None = None, strict: bool = False, quiet: bool = False) -> Ctx:
    root = Path(root or os.environ.get("HERITAGE_ROOT") or ROOT).resolve()
    load_env(root)
    if mock is None:
        mock = os.environ.get("HERITAGE_PROVIDER", "real") == "mock"
    sb, problems = load_storyboard(root, strict=strict)
    ctx = Ctx(root=root, sb=sb, mock=mock, lang=lang or "", strict=strict, quiet=quiet,
              pause_s=0.0 if mock else float(os.environ.get("HERITAGE_PAUSE_S", "0") or 0))
    for level, code, msg in problems:
        if level == "warning":
            ctx.say(f"  warning [{code}] {msg}")
    return ctx


# ----------------------------------------------------------------------------- storyboard

STRICT_CODES = {"draft", "unconfirmed", "consent_pending", "music_not_chosen", "shot_count", "subtitle_missing"}


def consent_rows(root: Path) -> dict[str, dict]:
    """Consent records in ETHICS.md: table rows whose first cell is an id like `consent-author`."""
    path = root / "ETHICS.md"
    rows: dict[str, dict] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and re.fullmatch(r"consent-[a-z0-9-]+", cells[0]):
            date = next((c for c in cells[1:] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c)), None)
            rows[cells[0]] = {"date": date, "cells": cells}
    return rows


def check_storyboard(sb: Any, root: Path) -> list[tuple[str, str, str]]:
    """Return (level, code, message) for every problem. level is 'error' or 'warning'."""
    import jsonschema

    problems: list[tuple[str, str, str]] = []
    schema = json.loads((root / "schema" / "storyboard.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(sb), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in err.absolute_path) or "(top level)"
        problems.append(("error", "schema", f"{where}: {err.message}"))
    if problems:
        return problems  # the checks below assume the shape is right

    fmt, shots = sb["format"], sb["shots"]
    ids = [s["id"] for s in shots]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(("error", "duplicate_id", f"shot id {dup} is used more than once"))
    names = [e["name"] for e in fmt["exports"]]
    if len(set(names)) != len(names):
        problems.append(("error", "duplicate_export", "export names must be unique"))
    if fmt["min_total_s"] > fmt["max_total_s"]:
        problems.append(("error", "format", "format.min_total_s is larger than format.max_total_s"))

    chars = {c["id"]: c for c in sb["characters"]}
    rows = consent_rows(root)
    for c in sb["characters"]:
        status, record = c["consent"]["status"], c["consent"].get("record")
        if c["real_person"] and status == "not_required":
            problems.append(("error", "consent", f"character {c['id']} is a real person: consent cannot be 'not_required'"))
        if status == "recorded":
            if not record:
                problems.append(("error", "consent", f"character {c['id']}: consent is 'recorded' but no record id is given"))
            elif record not in rows or not rows[record]["date"]:
                problems.append(("error", "consent", f"character {c['id']}: ETHICS.md has no dated row for {record}"))
        if c["real_person"] and status == "pending":
            problems.append(("warning", "consent_pending", f"consent for {c['id']} is pending: real providers will not generate shots with this person"))

    narr_lang, sub_lang = sb["language"]["narration"], sb["language"]["subtitles"]
    for s in shots:
        for cid in s["characters"]:
            if cid not in chars:
                problems.append(("error", "unknown_character", f"{s['id']}: character '{cid}' is not defined"))
        kf = s["keyframe"]
        n_cand = kf.get("candidates", sb.get("qa", {}).get("keyframe_candidates", 1))
        if kf.get("pick") and kf["pick"] > n_cand:
            problems.append(("error", "pick", f"{s['id']}: keyframe.pick is {kf['pick']} but there are only {n_cand} candidates"))
        if s["narration"] is not None:
            if narr_lang not in s["narration"]:
                problems.append(("error", "narration_missing", f"{s['id']}: no narration line for language '{narr_lang}'"))
            if sub_lang not in s["narration"]:
                problems.append(("warning", "subtitle_missing", f"{s['id']}: no '{sub_lang}' subtitle, it will be machine translated"))
        if s.get("review") and not s["review"]["confirmed"]:
            problems.append(("warning", "unconfirmed", f"{s['id']}: {s['review'].get('note', 'not confirmed yet')}"))

    for cue in sb["music"]["cues"]:
        if cue["at_shot"] not in ids:
            problems.append(("error", "cue", f"music cue points at unknown shot {cue['at_shot']}"))
    chosen = sb["music"]["chosen"]
    if chosen is None:
        problems.append(("warning", "music_not_chosen", "music.chosen is null: the placeholder plays until you choose a candidate"))
    elif chosen > len(sb["music"]["seeds"]):
        problems.append(("error", "music", f"music.chosen is {chosen} but there are only {len(sb['music']['seeds'])} seeds"))

    for key in ("audience", "intent"):
        if sb[key].strip().upper().startswith("DRAFT"):
            problems.append(("warning", "draft", f"{key} is still marked DRAFT"))
    if not 8 <= len(shots) <= 12:
        problems.append(("warning", "shot_count", f"{len(shots)} shots: the brief suggests eight to twelve"))
    floor = sum(s["min_duration_s"] for s in shots) + sb["end_card"]["duration_s"]
    if floor > fmt["max_total_s"]:
        problems.append(("error", "too_long", f"minimum durations already add up to {floor:.0f}s, over the {fmt['max_total_s']:.0f}s limit"))
    return problems


def load_storyboard(root: Path, strict: bool = False) -> tuple[dict, list[tuple[str, str, str]]]:
    path = root / "storyboard.json"
    try:
        sb = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise StoryboardError(f"{path} not found") from None
    except json.JSONDecodeError as e:
        raise StoryboardError(f"storyboard.json is not valid JSON: {e}") from None
    problems = check_storyboard(sb, root)
    if strict:
        problems = [("error" if code in STRICT_CODES else level, code, msg) for level, code, msg in problems]
    errors = [f"[{code}] {msg}" for level, code, msg in problems if level == "error"]
    if errors:
        raise StoryboardError("storyboard.json is not valid:\n  " + "\n  ".join(errors))
    return sb, problems


def shot_text(shot: dict, lang: str) -> str | None:
    return None if shot["narration"] is None else shot["narration"].get(lang)


# ----------------------------------------------------------------------------- hashing and cache


def sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def _flatten(d: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(d, dict):
        out: dict[str, Any] = {}
        for k, v in d.items():
            out.update(_flatten(v, f"{prefix}{k}."))
        return out
    return {prefix[:-1]: d}


@dataclass
class Unit:
    """One thing a stage produces. `fingerprint` holds every input that can change the output."""

    stage: str
    id: str
    fingerprint: dict
    ext: str
    produce: Callable[[Path], dict | None] | None = None  # None: made outside this machine (a GPU job)
    optional: bool = False  # a check that only measures: if it fails the run goes on, and the next run tries it again


@dataclass
class Result:
    unit: str
    path: Path | None
    key: str
    hit: bool
    reason: str
    meta: dict
    failed: str = ""  # why an optional unit could not be built this time


class Cache:
    """outputs/<stage>/<unit>__<key>.<ext> plus manifest.json. The key is the hash of the fingerprint."""

    def __init__(self, ctx: Ctx, stage: str):
        self.dir = ctx.out / stage
        self.path = self.dir / "manifest.json"
        self.data = {"units": {}, "entries": {}}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def file(self, unit: str, key: str, ext: str) -> Path:
        return self.dir / f"{unit}__{key}.{ext}"

    def explain(self, unit: Unit) -> str:
        """Say why a unit has to be rebuilt, by comparing with the fingerprint it was last built from."""
        last = self.data["units"].get(unit.id)
        if not last:
            return "new"
        old, new = _flatten(last["fingerprint"]), _flatten(unit.fingerprint)
        changed = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
        return "changed: " + ", ".join(changed[:4]) + (" ..." if len(changed) > 4 else "") if changed else "file missing"

    def entry(self, unit: str, key: str) -> dict | None:
        """What this unit left in the cache under this key.

        Two units can have the same fingerprint, for example the same line spoken in two shots. Each keeps
        its own entry: the first one under the key, any other under key:unit. A unit never reads another's result.
        """
        first = self.data["entries"].get(key)
        return first if first and first.get("unit") == unit else self.data["entries"].get(f"{key}:{unit}")

    def commit(self, unit: Unit, key: str, path: Path, meta: dict) -> None:
        entry = {"key": key, "file": path.name, "fingerprint": unit.fingerprint, "meta": meta, "created": now()}
        self.data["units"][unit.id] = entry
        first = self.data["entries"].get(key)
        slot = key if not first or first.get("unit") == unit.id else f"{key}:{unit.id}"
        self.data["entries"][slot] = {"unit": unit.id, "file": path.name, "meta": meta}
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)


def is_cached(ctx: Ctx, unit: Unit) -> bool:
    """Would `run_units` find this unit in the cache?"""
    cache, key = Cache(ctx, unit.stage), sha(unit.fingerprint)[:16]
    return cache.entry(unit.id, key) is not None and cache.file(unit.id, key, unit.ext).exists()


def run_units(ctx: Ctx, units: list[Unit], plan_only: bool = False) -> dict[str, Result]:
    """Build every unit whose fingerprint is new. Everything else is a cache hit and costs nothing."""
    results: dict[str, Result] = {}
    caches: dict[str, Cache] = {}
    for u in units:
        cache = caches.setdefault(u.stage, Cache(ctx, u.stage))
        key = sha(u.fingerprint)[:16]
        path = cache.file(u.id, key, u.ext)
        entry = cache.entry(u.id, key)
        if entry and path.exists():
            results[u.id] = Result(u.id, path, key, True, "cached", entry["meta"])
            ctx.say(f"  [{u.stage}] {u.id:<22} HIT")
            if not plan_only:  # a plan changes nothing, so it leaves nothing in the event log either
                log_event(ctx, stage=u.stage, unit=u.id, key=key, event="hit")
            continue
        reason = cache.explain(u)
        if plan_only or u.produce is None:
            note = "would build" if plan_only and u.produce else "waiting for an external job"
            results[u.id] = Result(u.id, None, key, False, reason, {})
            ctx.say(f"  [{u.stage}] {u.id:<22} MISS ({reason}) {note}")
            continue
        cache.dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"tmp-{uuid.uuid4().hex[:8]}-{path.name}")  # keeps the extension: ffmpeg picks the format from it
        t0 = time.time()
        failed = ""
        try:
            meta = u.produce(tmp) or {}
            os.replace(tmp, path)  # atomic: a stopped run never leaves a half-written file under the final name
        except PipelineError as e:
            if not u.optional:
                raise
            failed = str(e)
        finally:
            if tmp.exists():
                tmp.unlink()
        if failed:  # nothing is cached, so the next run tries again
            results[u.id] = Result(u.id, None, key, False, reason, {}, failed=failed)
            ctx.say(f"  [{u.stage}] {u.id:<22} FAILED, the run goes on without it: {failed[:160]}")
            log_event(ctx, stage=u.stage, unit=u.id, key=key, event="failed", reason=failed[:300])
            continue
        cache.commit(u, key, path, meta)
        results[u.id] = Result(u.id, path, key, False, reason, meta)
        ctx.say(f"  [{u.stage}] {u.id:<22} MISS ({reason}) built in {time.time() - t0:.1f}s")
        log_event(ctx, stage=u.stage, unit=u.id, key=key, event="built", reason=reason, seconds=round(time.time() - t0, 2))
    return results


# ----------------------------------------------------------------------------- logs


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def log_run(ctx: Ctx, **rec: Any) -> None:
    """One line per model call in runs.jsonl.

    `cost_usd` is what the call costs at list price (pricing.json). On a free tier nothing was paid
    for it. It is 0 for a failed attempt and for a mock call, and null when the price is not known.
    """
    rec = {"ts": now(), "run_id": ctx.run_id, **rec}
    rec["cost_usd"] = 0.0 if ctx.mock else pricing.cost_usd(rec, ctx.prices)
    _append(ctx.runlog, rec)


def log_event(ctx: Ctx, **rec: Any) -> None:
    """Cache hits and builds. Not model calls, so they live in their own file."""
    _append(ctx.out / "logs" / "events.jsonl", {"ts": now(), "run_id": ctx.run_id, **rec})


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


RETRY_WAITS = (10.0, 30.0, 90.0)  # seconds before attempts 2, 3 and 4, unless the provider says how long to wait


def day_start(reset: str) -> datetime:
    """When the provider's current quota day began, in UTC. Gemini counts from midnight Pacific time, Cloudflare from 00:00 UTC."""
    moment = datetime.now(timezone.utc)
    if reset == "pacific":
        try:
            from zoneinfo import ZoneInfo
            local = moment.astimezone(ZoneInfo("America/Los_Angeles"))
        except Exception:  # noqa: BLE001  no time zone data on this machine: Pacific standard time
            local = moment.astimezone(timezone(timedelta(hours=-8)))
        return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def free_tier_use(ctx: Ctx, model: str) -> dict | None:
    """What the run log says was used of a model's free allowance since its last reset. None when no limit is known.

    Every attempt is counted, failed ones too: the provider's own counter did the same on the day the limits were read.
    """
    limit = (ctx.prices.get(model) or {}).get("free_tier")
    if not limit:
        return None
    since = day_start(limit.get("reset", "utc")).strftime("%Y-%m-%dT%H:%M:%SZ")
    since = max(since, limit.get("counted_from", ""))  # an allowance belongs to a key: when the key is replaced, its count starts there
    today = [r for r in read_jsonl(ctx.runlog) if r.get("model") == model and r.get("ts", "") >= since]
    usd = sum(r["cost_usd"] if r.get("cost_usd") is not None else (pricing.cost_usd(r, ctx.prices) or 0.0) for r in today)
    next_reset = day_start(limit.get("reset", "utc")) + timedelta(days=1)
    return {"requests": len(today), "usd": round(usd, 6), "limit": limit, "resets": next_reset.astimezone().strftime("%H:%M on %d %b")}


def keep_within_free_tier(ctx: Ctx, model: str) -> None:
    """Called before every real request. Refuses a request the free tier would refuse, and waits out the per-minute limit.

    A daily allowance of ten speech requests is easy to spend by accident. A run that would go over it stops
    here with nothing sent, instead of finding out from the provider one failed call at a time.
    """
    use = free_tier_use(ctx, model)
    if not use:
        return
    limit = use["limit"]
    if limit.get("requests_per_day") and use["requests"] >= limit["requests_per_day"]:
        raise PipelineError(f"{model}: the free tier allows {limit['requests_per_day']} requests a day and the run log holds {use['requests']} "
                            f"since the last reset. Nothing was sent. The allowance resets at {use['resets']}.")
    if limit.get("usd_per_day") and use["usd"] >= limit["usd_per_day"]:
        if limit.get("then_paid_from") and now() >= limit["then_paid_from"]:  # the account pays for what goes over the allowance
            if model not in ctx._over_allowance:
                ctx._over_allowance.add(model)
                ctx.say(f"  {model}: over the free daily allowance (worth {limit['usd_per_day']} USD). From here each call is paid for at list price.")
        else:
            raise PipelineError(f"{model}: the free daily allowance (worth {limit['usd_per_day']} USD at list price) is used up. "
                                f"Nothing was sent. It resets at {use['resets']}.")
    if limit.get("requests_per_minute") and model in ctx._last_call:
        wait = 60.0 / limit["requests_per_minute"] - (time.time() - ctx._last_call[model])
        if wait > 0:
            ctx.sleep(wait)


def model_call(ctx: Ctx, *, stage: str, unit: str, provider: str, model: str, params: dict, seed: int | None,
               fn: Callable[[], tuple[Any, dict]], attempts: int = 4) -> tuple[Any, dict]:
    """Run one model call with retries. Every attempt, failed or not, is one line in the run log."""
    for attempt in range(1, attempts + 1):
        if not ctx.mock:
            keep_within_free_tier(ctx, model)
            ctx._last_call[model] = time.time()
        t0 = time.time()
        base = {"stage": stage, "unit": unit, "provider": provider, "model": model, "params": params, "seed": seed, "attempt": attempt}
        try:
            out, meta = fn()
        except ProviderError as e:
            log_run(ctx, **base, status="error", http_status=e.status, latency_s=round(time.time() - t0, 3), error=str(e)[:1500])
            if not e.retryable or attempt == attempts:
                raise PipelineError(f"{provider} call for {unit} failed: {str(e)[:300]}") from None
            wait = min(e.retry_after or RETRY_WAITS[min(attempt, len(RETRY_WAITS)) - 1], 90.0)
            ctx.say(f"  [{stage}] {unit}: {str(e)[:200]} Waiting {wait:.0f}s, then attempt {attempt + 1} of {attempts}.")
            ctx.sleep(wait)
            continue
        log_run(ctx, **base, status="ok", latency_s=round(time.time() - t0, 3), **meta)
        if ctx.pause_s:
            ctx.sleep(ctx.pause_s)
        return out, meta
    raise AssertionError("unreachable")


# ----------------------------------------------------------------------------- timeline and subtitles


def plan_timeline(sb: dict, narration_s: dict[str, float]) -> dict:
    """Picture follows the voice: a shot lasts as long as its narration needs, never less than its minimum."""
    fmt = sb["format"]
    fps, lead, tail = fmt["fps"], fmt.get("lead_in_s", 0.4), fmt.get("tail_s", 0.5)
    t, shots = 0.0, []
    for s in sb["shots"]:
        nd = narration_s.get(s["id"], 0.0)
        frames = round(max(s["min_duration_s"], lead + nd + tail if nd else 0.0) * fps)
        dur = frames / fps
        shots.append({"id": s["id"], "start": round(t, 4), "duration": round(dur, 4), "frames": frames,
                      "narration_start": round(t + lead, 4) if nd else None, "narration_s": round(nd, 3)})
        t += dur
    end = round(sb["end_card"]["duration_s"] * fps) / fps
    return {"fps": fps, "shots": shots, "end_card_start": round(t, 4), "end_card_s": end, "total_s": round(t + end, 4)}


MIN_CUE_S = 1.5   # a subtitle cue stays up at least this long
READ_CPS = 20     # and long enough to be read at this many characters a second
SNAP_S = 0.7      # a sentence end that is worked out from the text moves to a measured pause this near to it
_SENTENCE = re.compile(r".+?(?:[.!?:\u1362\u1366\u1367]+[\"'\u201d\u2019\u00bb)]*(?=\s)|$)", re.S)


# Ethiopic letters that are written differently and said the same: the script may use one and a listener another
_SAME_SOUND = {src + i: dst + i for src, dst in ((0x1210, 0x1200), (0x1280, 0x1200), (0x1220, 0x1230), (0x12D0, 0x12A0), (0x1340, 0x1338)) for i in range(8)}


def fold(text: str) -> str:
    """Lower case, no punctuation, single spaces, one spelling for letters that sound the same: so only the words are compared."""
    kept = "".join(" " if unicodedata.category(ch)[0] in "PSZ" else ch for ch in text.lower().translate(_SAME_SOUND))
    return re.sub(r"\s+", " ", kept).strip()


def sentences(text: str) -> list[str]:
    """A line as its sentences. A full stop, a question mark, an exclamation mark and a colon end one, in Latin and in
    Ethiopic script, and a closing quotation mark stays with its sentence. A comma and a semicolon do not."""
    return [m.group(0).strip() for m in _SENTENCE.finditer(text.strip()) if m.group(0).strip()]


def wrap_cue(text: str, max_chars: int = 40) -> list[str]:
    """The lines of one cue. Two lines are broken where they come out nearest in length, and rather after a
    punctuation mark, so that no line is a single left-over word."""
    lines = textwrap.wrap(text, width=max_chars, break_long_words=False) or [""]
    if len(lines) != 2:
        return lines
    words, best = text.split(), None
    for i in range(1, len(words)):
        first, second = " ".join(words[:i]), " ".join(words[i:])
        if len(first) <= max_chars and len(second) <= max_chars:
            score = abs(len(first) - len(second)) - (8 if first[-1] in ".,!?:;\"\u201d" else 0)
            if best is None or score < best[0]:
                best = (score, [first, second])
    return best[1] if best else lines


def sentence_ends(weights: list[float], duration: float, pauses: list | None = None) -> list[tuple[float, float]]:
    """Where each sentence of a spoken line ends, in seconds from the start of the line, as (the voice stops, the voice goes on).

    The speaking time is shared out by `weights`, the number of letters in each sentence, and the measured pauses
    are put back where they fall. An end that comes out within SNAP_S of a measured pause is that pause.
    """
    silences = sorted((float(a), float(b)) for a, b in (pauses or []) if 0.1 < a and b < duration - 0.1)
    speech = max(0.1, duration - sum(b - a for a, b in silences))
    total, said, ends, free, last = sum(weights) or 1, 0.0, [], list(silences), 0.0
    for w in weights[:-1]:
        said += speech * w / total
        at = said                                   # from speaking time to time in the audio: the pauses before it are added
        for a, b in silences:
            if a < at:
                at += b - a
        near = [(max(a - at, at - b, 0.0), a, b) for a, b in free if b > last and max(a - at, at - b, 0.0) <= SNAP_S]
        if near:
            _, a, b = min(near)
            stop, go = a, b
            free = [p for p in free if p[0] >= b]
        else:
            stop = go = at
        stop = min(max(stop, last + 0.2), duration)
        go = min(max(go, stop), duration)
        ends.append((stop, go))
        last = go
    return [*ends, (duration, duration)]


GAP_COST = 0.7    # in the match of script words to heard words: the cost of a word with no partner


def sentence_ends_heard(spoken: str, words: list[dict], duration: float) -> list[tuple[float, float]] | None:
    """Where each sentence of a spoken line ends, from the words a listening model heard and the time of each.

    The words of the script are matched to the heard words in order, by how alike they are, so a word that was
    misheard, dropped or split in two moves nothing. A sentence ends where its last matched word ends, and the
    next begins where the following heard word begins. None when some sentence has no matched word at all.
    """
    said = [fold(s).split() for s in sentences(spoken)]
    script = [w for s in said for w in s]
    heard = [fold(w.get("text", "")) for w in words]
    if not script or not heard:
        return None
    n, m = len(script), len(heard)
    cost = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        cost[i][0] = i * GAP_COST
    for j in range(1, m + 1):
        cost[0][j] = j * GAP_COST
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            alike = SequenceMatcher(None, script[i - 1], heard[j - 1]).ratio()
            cost[i][j] = min(cost[i - 1][j - 1] + 1 - alike, cost[i - 1][j] + GAP_COST, cost[i][j - 1] + GAP_COST)
    partner, i, j = {}, n, m  # script word -> heard word, read back from the end
    while i > 0 and j > 0:
        alike = SequenceMatcher(None, script[i - 1], heard[j - 1]).ratio()
        if abs(cost[i][j] - (cost[i - 1][j - 1] + 1 - alike)) < 1e-9:
            partner[i - 1] = j - 1
            i, j = i - 1, j - 1
        elif abs(cost[i][j] - (cost[i - 1][j] + GAP_COST)) < 1e-9:
            i -= 1
        else:
            j -= 1
    ends, first = [], 0
    for k, sentence in enumerate(said):
        mine = [partner[x] for x in range(first, first + len(sentence)) if x in partner]
        first += len(sentence)
        if not mine:
            return None
        if k == len(said) - 1:
            ends.append((duration, duration))
            break
        last = max(mine)
        stop = min(float(words[last]["end"]), duration)
        go = min(float(words[last + 1]["start"]), duration) if last + 1 < m else stop
        if go < stop:  # the times of two neighbouring words overlap a little: the change is in the middle
            stop = go = (stop + go) / 2
        if ends and stop < ends[-1][1] + 0.1:
            return None
        ends.append((round(stop, 3), round(go, 3)))
    return ends


def subtitle_cues(text: str, start: float, duration: float, max_chars: int = 40, max_lines: int = 2,
                  pauses: list | None = None, spoken: str | None = None, words: list | None = None) -> list[tuple[float, float, list[str]]]:
    """Split one narration line into cues of at most two lines of 40 characters, each on screen while it is said.

    The subtitle is taken sentence by sentence. `spoken` is the line as it is narrated: when it has as many sentences
    as the subtitle, each subtitle sentence gets the time of its spoken sentence. That time comes from `words`, the
    words a listening model heard with the time of each. Without them it is worked out from the number of letters
    said and from `pauses`, the silences measured inside the line, and without `spoken` from the subtitle's own letters.
    Sentences share a cue until the cue is up for MIN_CUE_S and can be read at READ_CPS, as long as they fit in two
    lines. A colon always ends a cue, so what follows it is not shown before it is said.
    """
    def letters(t: str) -> int:
        return max(1, sum(ch.isalnum() for ch in t))

    subs = sentences(text) or [text.strip()]
    said = sentences(spoken) if spoken else []
    ends = sentence_ends_heard(spoken, words, duration) if words and len(said) == len(subs) else None
    if not ends:
        ends = sentence_ends([letters(x) for x in (said if len(said) == len(subs) else subs)], duration, pauses)
    spans, begin = [], 0.0  # per sentence: (text, it comes up, the voice stops, the next one comes up)
    for sentence, (stop, go) in zip(subs, ends):
        lines = textwrap.wrap(sentence, width=max_chars, break_long_words=False) or [""]
        parts = [" ".join(lines[i:i + max_lines]) for i in range(0, len(lines), max_lines)]
        share, t = sum(letters(x) for x in parts), begin
        for n, part in enumerate(parts):  # a sentence too long for one cue is shown in parts, its time shared by their length
            last_part = n == len(parts) - 1
            upto = stop if last_part else t + (stop - begin) * letters(part) / share
            spans.append((part, t, upto, go if last_part else upto))
            t = upto
        begin = max(go - 0.08, stop) if go > stop else go  # after a pause the next cue comes up just before the voice starts again
    groups: list[list] = []
    for span in spans:
        cur = groups[-1] if groups else None
        if cur:
            shown = " ".join(x[0] for x in cur)
            long_enough = cur[-1][2] - cur[0][1] >= max(MIN_CUE_S, len(shown) / READ_CPS)
            fits = len(textwrap.wrap(f"{shown} {span[0]}", width=max_chars, break_long_words=False)) <= max_lines
            if fits and not long_enough and not shown.endswith(":"):
                cur.append(span)
                continue
        groups.append([span])
    cues = []
    for i, group in enumerate(groups):
        first = 0.0 if i == 0 else cues[-1][1] - start
        until = duration if i == len(groups) - 1 else (max(group[-1][3] - 0.08, group[-1][2]) if group[-1][3] > group[-1][2] else group[-1][3])
        cues.append((round(start + first, 3), round(start + max(until, first + 0.2), 3), wrap_cue(" ".join(x[0] for x in group), max_chars)))
    return cues


# ----------------------------------------------------------------------------- media helpers


def need_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise PipelineError(f"{name} is not installed or not on PATH. Install FFmpeg (https://ffmpeg.org/download.html) and try again.")


def ff(args: list[str], cwd: Path | None = None) -> None:
    """Run ffmpeg quietly. On failure, raise with the end of its error output."""
    need_tool("ffmpeg")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args]
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise PipelineError("ffmpeg failed:\n" + p.stderr.strip()[-900:] + "\ncommand: ffmpeg " + " ".join(args)[:600])


def ff_capture(args: list[str]) -> str:
    """Run ffmpeg for its measurements (loudness). Returns stderr."""
    need_tool("ffmpeg")
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise PipelineError("ffmpeg failed:\n" + p.stderr.strip()[-900:])
    return p.stderr


def media_info(path: Path) -> dict:
    need_tool("ffprobe")
    p = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise PipelineError(f"ffprobe cannot read {path}: {p.stderr.strip()[-300:]}")
    data = json.loads(p.stdout)
    info: dict[str, Any] = {"duration": float(data["format"].get("duration", 0.0))}
    for st in data["streams"]:
        if st["codec_type"] == "video" and "width" not in info:
            num, den = (st.get("avg_frame_rate") or "0/1").split("/")
            info.update(width=st["width"], height=st["height"], vcodec=st["codec_name"], pix_fmt=st.get("pix_fmt"),
                        fps=float(num) / float(den) if float(den) else 0.0,
                        r_frame_rate=st.get("r_frame_rate"), avg_frame_rate=st.get("avg_frame_rate"))
        if st["codec_type"] == "audio" and "acodec" not in info:
            info.update(acodec=st["codec_name"], sample_rate=int(st.get("sample_rate", 0)), channels=st.get("channels"))
    return info


def wav_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError):
        return media_info(path)["duration"]


def loudness(path: Path, seconds: float | None = None) -> dict:
    """Integrated loudness (LUFS) and true peak (dBTP), measured the way the platforms do (EBU R128)."""
    head = ["-t", f"{seconds:.3f}"] if seconds else []
    err = ff_capture([*head, "-i", str(path), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"])
    summary = err[err.rfind("Summary:"):]
    i = re.search(r"I:\s*(-?[\d.]+) LUFS", summary)
    tp = re.search(r"Peak:\s*(-?[\d.]+|-inf) dBFS", summary)
    if not i:
        raise PipelineError(f"could not measure loudness of {path}")
    return {"lufs": float(i.group(1)), "true_peak_db": float(tp.group(1)) if tp and tp.group(1) != "-inf" else -99.0}


# ----------------------------------------------------------------------------- stage indexes
# Each stage writes outputs/<stage>/index.json: what it produced, under which cache key. The next
# stage reads that file, or the copy passed along in `state` during one run (which also works for
# `plan`, where nothing is written).


def index_path(ctx: Ctx, stage: str, per_lang: bool = False) -> Path:
    return ctx.out / stage / (f"index.{ctx.narration_lang}.json" if per_lang else "index.json")


def write_index(ctx: Ctx, stage: str, data: dict, per_lang: bool = False) -> None:
    path = index_path(ctx, stage, per_lang)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def get_index(ctx: Ctx, state: dict, stage: str, per_lang: bool = False, required: bool = True) -> dict:
    if stage in state:
        return state[stage]
    path = index_path(ctx, stage, per_lang)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if required:
        raise PipelineError(f"the {stage} stage has not run yet. Run: python -m pipeline stage {stage}")
    return {}


def estimate_seconds(text: str) -> float:
    """Rough speaking time, used only before the real narration exists."""
    letters = sum(1 for ch in text if ch.isalnum())
    return round(max(1.0, letters / (14.0 if text.isascii() else 6.0)), 2)


def rel(ctx: Ctx, path: Path) -> str:
    try:
        return path.resolve().relative_to(ctx.root).as_posix()
    except ValueError:
        return str(path)
