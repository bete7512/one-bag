"""Final-cut check: is this film what the brief asks for?

Deterministic measurements on the exported files, so "done" is a fact and not a feeling:
length, both aspect ratios, constant frame rate, codecs, loudness and true peak, subtitle line
lengths, the AI end card. "must" checks decide pass or fail. "note" checks are things a person
should look at before release (fallback shots, a placeholder score, lines the listening check
flagged).
"""
from __future__ import annotations

import json

from .core import Ctx, PipelineError, get_index, loudness, media_info


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

    keyframes = get_index(ctx, state, "keyframes", required=False)
    blocked = [sid for sid, k in keyframes.items() if k.get("blocked")]
    check("must", "pictures: no shot is waiting for consent", not blocked, ", ".join(blocked) or "all shots have a picture")
    shots = get_index(ctx, state, "shots", per_lang=True, required=False)
    fallback = [sid for sid, s in shots.items() if s.get("source") == "kenburns_fallback"]
    check("note", "motion: shots asked for Wan but still on the Ken Burns fallback", not fallback, ", ".join(fallback) or "none")
    music = get_index(ctx, state, "music", required=False)
    check("note", "music: a generated score is chosen", music.get("source") == "acestep", music.get("source", "?"))
    narration = get_index(ctx, state, "narration", per_lang=True, required=False)
    floor = sb.get("qa", {}).get("roundtrip_min", 0.6)
    weak = [f"{sid} ({n['roundtrip']:.2f})" for sid, n in narration.items() if n.get("roundtrip") is not None and n["roundtrip"] < floor]
    check("note", "narration: every line passed the listening check", not weak, ", ".join(weak) or "all lines at or above the floor")

    passed = all(c["ok"] for c in checks if c["level"] == "must")
    report = {"passed": passed, "language": ctx.narration_lang, "total_s": film["total_s"], "mix": film.get("mix", {}), "checks": checks}
    (ctx.out / "qc_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in checks:
        mark = "PASS" if c["ok"] else ("FAIL" if c["level"] == "must" else "NOTE")
        ctx.say(f"  {mark:<4} {c['check']:<58} {c['detail']}")
    ctx.say(f"  final-cut check: {'PASSED' if passed else 'FAILED'}  (report: {(ctx.out / 'qc_report.json').relative_to(ctx.root)})")
    return report
