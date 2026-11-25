"""Final-cut check: is this film what the brief asks for?

Deterministic measurements on the exported files, so "done" is a fact and not a feeling:
length, both aspect ratios, constant frame rate, codecs, loudness and true peak, subtitle line
lengths, the AI end card. "must" checks decide pass or fail. "note" checks are things a person
should look at before release (fallback shots, a placeholder score, lines the listening check
flagged, a picked picture the judge marked).
"""
from __future__ import annotations

import json

from .core import Ctx, PipelineError, get_index, loudness, media_info
from .keyframes import LOOK_UNDER


def marked_picks(keyframes: dict) -> tuple[list[str], list[str]]:
    """Shots whose picked keyframe the judge marked: (scored under LOOK_UNDER, each with its total), (has writing in it).

    Only the candidate that is in the film counts. The keyframes stage prints "look at" for the same two things when
    it picks, and that line is gone with the terminal. A shot whose pick has no score is in neither list: a shot that
    waits for consent fails its own check, and "the judge scored every candidate" names a score that is missing.
    """
    low, written = [], []
    for sid, k in keyframes.items():
        score = (k.get("scores") or {}).get(str(k.get("candidate"))) or {}
        total = score.get("total")
        if isinstance(total, (int, float)) and total < LOOK_UNDER:
            low.append(f"{sid} ({total})")
        if score.get("text_in_image"):
            written.append(sid)
    return low, written


def run(ctx: Ctx, state: dict | None = None) -> dict:
    state = state or {}
    sb, fmt = ctx.sb, ctx.sb["format"]
    path = ctx.out / "assemble" / f"index.film.{ctx.narration_lang}.json"
    if "assemble" in state and state["assemble"].get("mode") == "film":
        film = state["assemble"]
    elif path.exists():
        film = json.loads(path.read_text(encoding="utf-8"))
    else:
        raise PipelineError("no film has been assembled yet. Run: python -m pipeline film")

    checks: list[dict] = []

    def check(level: str, name: str, ok: bool, detail: str = "") -> None:
        checks.append({"level": level, "check": name, "ok": bool(ok), "detail": detail})

    lo, hi, fps = fmt["min_total_s"], fmt["max_total_s"], fmt["fps"]
    for exp in fmt["exports"]:
        name = exp["name"]
        fname = film["files"].get(name)
        if not fname or not (ctx.out / fname).exists():
            check("must", f"{name}: file exists", False, "not rendered")
            continue
        info = media_info(ctx.out / fname)
        check("must", f"{name}: length within {lo:.0f} to {hi:.0f} s", lo <= info["duration"] <= hi + 0.1, f"{info['duration']:.2f} s")
        check("must", f"{name}: size {exp['width']}x{exp['height']}", (info.get("width"), info.get("height")) == (exp["width"], exp["height"]),
              f"{info.get('width')}x{info.get('height')}")
        check("must", f"{name}: constant {fps} fps", info.get("r_frame_rate") == info.get("avg_frame_rate") and abs(info.get("fps", 0) - fps) < 0.01,
              f"{info.get('avg_frame_rate')}")
        check("must", f"{name}: H.264 video with AAC audio", info.get("vcodec") == "h264" and info.get("acodec") == "aac",
              f"{info.get('vcodec')} + {info.get('acodec')}")
        level = loudness(ctx.out / fname)
        check("must", f"{name}: loudness near -14 LUFS", abs(level["lufs"] + 14.0) <= 1.5, f"{level['lufs']:.1f} LUFS")
        check("must", f"{name}: true peak at or under -1 dB", level["true_peak_db"] <= -0.95, f"{level['true_peak_db']:.1f} dB")

    cues = film["cues"]
    longest = max((len(line) for _, _, lines in cues for line in lines), default=0)
    check("must", "subtitles: at most 2 lines of 40 characters", all(len(lines) <= 2 for _, _, lines in cues) and longest <= 40,
          f"{len(cues)} cues, longest line {longest} characters")
    narrated = [s["id"] for s in sb["shots"] if s["narration"] is not None]
    check("must", "subtitles: every narrated shot has them", all(t["narration_start"] is not None for t in film["timeline"]["shots"] if t["id"] in narrated),
          f"{len(narrated)} narrated shots")
    check("must", "end card: says the film was made with AI, for 2 s or more",
          any(" AI" in f" {line}" for line in film["end_card"]) and film["timeline"]["end_card_s"] >= 2, " / ".join(film["end_card"]))

    script = get_index(ctx, state, "script", per_lang=True, required=False).get("lines", {})
    doubtful = [sid for sid, line in script.items() if line.get("subtitle_check", {}).get("faithful") is False]
    check("note", "subtitles: each one says what its line says", not doubtful, ", ".join(doubtful) or "none in doubt")
    keyframes = get_index(ctx, state, "keyframes", required=False)
    blocked = [sid for sid, k in keyframes.items() if k.get("blocked")]
    check("must", "pictures: no shot is waiting for consent", not blocked, ", ".join(blocked) or "all shots have a picture")
    bordered = [sid for sid, k in keyframes.items() if k.get("border")]
    check("note", "pictures: every picked keyframe fills its frame", not bordered, ", ".join(bordered) or "no paper border")
    unscored = [sid for sid, k in keyframes.items() if k.get("unscored")]
    check("note", "pictures: the judge scored every candidate", not unscored, ", ".join(unscored) or "all scored")
    low, written = marked_picks(keyframes)
    check("note", f"pictures: no picked keyframe scored under {LOOK_UNDER} by the judge", not low, ", ".join(low) or "none")
    check("note", "pictures: no picked keyframe has writing in it", not written, ", ".join(written) or "none")
    shots = get_index(ctx, state, "shots", per_lang=True, required=False)
    fallback = [sid for sid, s in shots.items() if s.get("source") == "kenburns_fallback"]
    check("note", "motion: shots asked for Wan but still on the Ken Burns fallback", not fallback, ", ".join(fallback) or "none")
    pushed = {sid: t for sid, t in film.get("tails", {}).items() if t.get("tail") == "push"}
    check("note", "motion: every generated clip lasts as long as its shot", not pushed,
          ", ".join(f"{sid} ends on a {t['tail_s']:.1f} s push over its last frame" for sid, t in pushed.items()) or "none is shorter")
    music = get_index(ctx, state, "music", required=False)
    check("note", "music: a generated score is chosen", music.get("source") == "acestep", music.get("source", "?"))
    narration = get_index(ctx, state, "narration", per_lang=True, required=False)
    floor = sb.get("qa", {}).get("roundtrip_min", 0.6)
    weak = [f"{sid} ({n['roundtrip']:.2f})" for sid, n in narration.items() if n.get("roundtrip") is not None and n["roundtrip"] < floor]
    if sb.get("qa", {}).get("roundtrip"):
        weak += [f"{sid} (not checked)" for sid, n in narration.items() if n.get("roundtrip") is None]
    check("note", "narration: every line passed the listening check", not weak, ", ".join(weak) or "all lines at or above the floor")

    passed = all(c["ok"] for c in checks if c["level"] == "must")
    report = {"passed": passed, "language": ctx.narration_lang, "total_s": film["total_s"], "mix": film.get("mix", {}), "checks": checks}
    (ctx.out / "qc_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in checks:
        mark = "PASS" if c["ok"] else ("FAIL" if c["level"] == "must" else "NOTE")
        ctx.say(f"  {mark:<4} {c['check']:<58} {c['detail']}")
    ctx.say(f"  final-cut check: {'PASSED' if passed else 'FAILED'}  (report: {(ctx.out / 'qc_report.json').relative_to(ctx.root)})")
    return report
