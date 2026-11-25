"""Stage 6, assemble: the edit, in code and from the storyboard.

Picture. One encoded scene file per shot per export, subtitles burned in, all with the same
encoder settings. They are joined with the concat demuxer and no re-encode, so changing one shot
re-renders one scene file per export and nothing else.

Sound. Narration lines are placed on the timeline (picture follows the voice). Voice and score are
first brought to known levels, line by line, the score is ducked under the voice with a sidechain
compressor, and the mix is brought toward -14 LUFS with one fixed gain, after its highest peaks are
limited once. The encoded film stays under -1 dB true peak.

Two aspect ratios from one master. Each shot is fitted per export: if cropping to the export
loses 45% of the frame or less it is cropped around the centre, otherwise it sits over a blurred
copy of itself.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

from .core import (STAGE_VERSION, Ctx, PipelineError, Unit, ff, ff_capture, get_index, loudness, media_info,
                   plan_timeline, run_units, subtitle_cues)

ENCODE = ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-video_track_timescale", "12288", "-an"]
DUCK = {"threshold": 0.02, "ratio": 6, "attack": 300, "release": 1500}  # the starting point the brief suggests
TARGET = {"lufs": -14.0, "true_peak": -1.7}  # the AAC encoder adds to the peaks (0.2 to 0.7 dB measured here): this keeps the film under -1 dBTP
VOICE_LUFS, MUSIC_LUFS = -16.0, -24.0  # levels before ducking: the score starts 8 dB under the voice
LINE_GAIN_MAX = 12.0     # dB: a narration line is never moved further than this to reach the voice level
BLOCK = 1024             # samples per block on both inputs of the ducking compressor
LIMIT = {"attack": 5, "release": 50, "margin_db": 0.3}  # the peak limiter before the last gain: milliseconds and dB
MAX_CROP_LOSS = 0.45
MAX_SLOWDOWN = 1.25
TAIL_MIN_S = 0.75        # a hold shorter than this is not seen as a freeze
TAIL_PUSH_PER_S = 0.012  # after a clip ends its last frame keeps moving: about 1% closer each second
TAIL_PUSH_MAX = 0.08
SUBTITLE_STYLE = 2  # bump when the look of the subtitles changes


def work_dir(ctx: Ctx) -> Path:
    path = ctx.out / "assemble" / "work"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ----------------------------------------------------------------------------- subtitles (ASS)


def ass_time(t: float) -> str:
    cs = int(round(max(0.0, t) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def ass_escape(text: str) -> str:
    return text.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def ass_document(width: int, height: int, margin_v: int, events: list[tuple[float, float, str, str]]) -> str:
    """events: (start, end, style, text). Styles: Sub (bottom centre) and Card (middle centre)."""
    side = round(width * 0.075)
    size = min(round(height * 0.05), int((width - 2 * side) / (40 * 0.52)))  # 40 characters must fit on one line
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Arial,{size},&H00FFFFFF,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,{max(2, size // 14)},1,2,{side},{side},{margin_v},1
Style: Card,Arial,{round(min(width, height) * 0.035)},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,{side},{side},0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    body = "".join(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},{style},,0,0,0,,{text}\n" for a, b, style, text in events)
    return head + body


def cue_events(cues: list) -> list[tuple[float, float, str, str]]:
    return [(a, b, "Sub", "\\N".join(ass_escape(line) for line in lines)) for a, b, lines in cues]


def card_event(lines: list[str], width: int, height: int, start: float, end: float) -> tuple[float, float, str, str]:
    big, small = round(min(width, height) * 0.075), round(min(width, height) * 0.034)
    text = "{\\fad(500,0)}" + "\\N".join(f"{{\\fs{big if i == 0 else small}}}{ass_escape(line)}" for i, line in enumerate(lines))
    return (start, end, "Card", text)


HOLD_S = 2.5  # the last words of a line stay on screen this long after the voice stops, when the shot lasts that long


def hold_last(cues: list, limit: float) -> list:
    """Keep the last cue of a line up after the voice has stopped, so it can be read, but never past `limit` (the end of its shot)."""
    if cues:
        start, end, lines = cues[-1]
        cues[-1] = (start, round(max(end, min(limit, end + HOLD_S)), 3), lines)
    return cues


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


# ----------------------------------------------------------------------------- picture


def fit_graph(src_w: int, src_h: int, width: int, height: int, focus_y: float = 0.5) -> tuple[str, str]:
    """Filter steps that take a `src` clip to exactly width x height. Returns (graph, mode).

    `focus_y` says where the subject sits, from 0 (top) to 1 (bottom). A crop that takes height away keeps
    the part around it: the wide film cuts a square picture to its middle band, and a standing figure loses its head there.
    """
    src_ar, out_ar = src_w / src_h, width / height
    loss = 1 - min(src_ar / out_ar, out_ar / src_ar)
    cover = (f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,"
             f"crop={width}:{height}:(iw-{width})/2:(ih-{height})*{min(1.0, max(0.0, focus_y)):.3f}")
    if loss <= MAX_CROP_LOSS:
        return cover, "crop"
    graph = (f"split[bgsrc][fgsrc];[bgsrc]{cover},boxblur=24:4,eq=brightness=-0.10[bg];"
             f"[fgsrc]scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos[fg];"
             f"[bg][fg]overlay=(W-w)/2:(H-h)/2")
    return graph, "blur_fill"


def render_scene(ctx: Ctx, clip: Path, out: Path, *, width: int, height: int, frames: int, fps: int, cues: list, margin_v: int,
                 focus_y: float = 0.5) -> dict:
    """One shot at one export size, exactly `frames` long, subtitles burned in.

    A generated clip is a few seconds long and a shot lasts as long as its narration. A clip that
    is too short is slowed by at most MAX_SLOWDOWN. What is still missing is the tail: the clip's
    last frame goes on as a slow push in, so the picture never freezes while the voice is speaking.
    """
    info = media_info(clip)
    have = max(1, round(info["duration"] * fps))
    slow = 1.0 if have >= frames else min(MAX_SLOWDOWN, frames / have)
    tail = max(0.0, frames / fps - info["duration"] * slow)
    fit, mode = fit_graph(info["width"], info["height"], width, height, focus_y)
    graph = f"[0:v]setpts={slow:.5f}*(PTS-STARTPTS),fps={fps},tpad=stop_mode=clone:stop_duration={tail + 0.5:.3f}"
    kind = "none" if tail == 0 else "hold" if tail < TAIL_MIN_S else "push"
    if kind == "push":
        # The whole shot goes through one zoom filter: zoom 1 while the clip plays, then an eased push in over
        # its last frame. Both parts are resampled the same way, so nothing changes at the point where they meet.
        w0, h0 = info["width"], info["height"]
        start = round(info["duration"] * slow * fps)
        ease = f"(1-cos(PI*(on-{start})/{max(1, frames - start)}))/2"
        zoom = f"if(lt(on,{start}),1,1+{min(TAIL_PUSH_MAX, TAIL_PUSH_PER_S * tail):.4f}*{ease})"
        graph += (f",scale={3 * w0}:{3 * h0}:flags=lanczos,zoompan=z='{zoom}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'"
                  f":d=1:s={w0}x{h0}:fps={fps}")
    graph += f",{fit}"
    work = work_dir(ctx)
    ass = None
    if cues:
        ass = work / f"sub-{uuid.uuid4().hex[:8]}.ass"
        ass.write_text(ass_document(width, height, margin_v, cue_events(cues)), encoding="utf-8")
        graph += f",ass={ass.name}"
    graph += ",format=yuv420p[v]"
    try:  # run inside the work folder so the subtitle file is named without a path: no escaping trouble on any OS
        ff(["-i", str(clip), "-filter_complex", graph, "-map", "[v]", "-frames:v", str(frames), "-r", str(fps), *ENCODE, str(out)], cwd=work)
    finally:
        if ass:
            ass.unlink(missing_ok=True)
    return {"fit": mode, "slowdown": round(slow, 3), "tail": kind, "tail_s": round(tail, 3)}


def render_card(ctx: Ctx, out: Path, *, lines: list[str], width: int, height: int, frames: int, fps: int) -> dict:
    work = work_dir(ctx)
    ass = work / f"card-{uuid.uuid4().hex[:8]}.ass"
    ass.write_text(ass_document(width, height, 0, [card_event(lines, width, height, 0.0, frames / fps + 1)]), encoding="utf-8")
    try:
        ff(["-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r={fps}:d={frames / fps + 1:.3f}", "-vf", f"ass={ass.name},format=yuv420p",
            "-frames:v", str(frames), "-r", str(fps), *ENCODE, str(out)], cwd=work)
    finally:
        ass.unlink(missing_ok=True)
    return {}


def join_and_mux(ctx: Ctx, scenes: list[Path], mix: Path, out: Path) -> dict:
    work = work_dir(ctx)
    tag = uuid.uuid4().hex[:8]
    listing, silent = work / f"concat-{tag}.txt", work / f"joined-{tag}.mp4"
    listing.write_text("".join("file '" + p.as_posix().replace("'", "'\\''") + "'\n" for p in scenes), encoding="utf-8")
    try:
        ff(["-f", "concat", "-safe", "0", "-i", listing.name, "-c", "copy", str(silent)], cwd=work)
        ff(["-i", str(silent), "-i", str(mix), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", str(out)])
    finally:
        listing.unlink(missing_ok=True)
        silent.unlink(missing_ok=True)
    return {}


# ----------------------------------------------------------------------------- sound


def to_target(src: Path, dst: Path) -> dict:
    """Bring a mix to the target loudness with one fixed gain, and say what was done, as measured.

    The brief suggests FFmpeg's loudnorm in two passes. Its second pass applies one fixed gain only when the
    peaks stay under the true-peak target after it. With a voice as peaky as this one they do not, and loudnorm
    then rides the gain up and down without saying so (E12). So the steps are done here, in the open: measure
    with the same EBU R128 meter, limit the peaks that are in the way once, measure again, and apply one gain.

    The limiter makes the mix quieter, so that gain falls short of the target: by 0.7 to 1.0 LU on the first
    real cut. That is accepted. Limiting harder to win it back squeezes the voice, and its flattened peaks
    then overshoot in the AAC encoder: four rounds of it put the film's true peak at -0.8 dB.
    """
    level = loudness(src)
    if level["lufs"] < -70:  # silence: nothing to normalise
        shutil.copy2(src, dst)
        return {"how": "copy"}
    limited = src.with_name(src.stem + "-limited.wav")
    cur, ceiling = src, None
    try:
        gain = TARGET["lufs"] - level["lufs"]
        if level["true_peak_db"] + gain > TARGET["true_peak"]:
            ceiling = TARGET["true_peak"] - gain - LIMIT["margin_db"]  # dBFS: with the planned gain the peaks would sit just under the target
            ff(["-i", str(src), "-af", f"alimiter=limit={min(1.0, 10 ** (ceiling / 20)):.4f}:attack={LIMIT['attack']}:release={LIMIT['release']}:level=false",
                "-ar", "48000", "-c:a", "pcm_f32le", str(limited)])
            cur, level = limited, loudness(limited)
            gain = min(TARGET["lufs"] - level["lufs"], TARGET["true_peak"] - level["true_peak_db"])  # never a peak over the target
        ff(["-i", str(cur), "-af", f"volume={gain:.2f}dB", "-ar", "48000", "-c:a", "pcm_s16le", str(dst)])
    finally:
        limited.unlink(missing_ok=True)
    return {"how": "limited once, then one fixed gain" if ceiling is not None else "one fixed gain", "gain_db": round(gain, 2),
            "ceiling_db": round(ceiling, 2) if ceiling is not None else None}


def build_mix(ctx: Ctx, out: Path, placed: list[tuple[Path, float]], music: Path, total: float, gain_db: float) -> dict:
    work = work_dir(ctx)
    tag = uuid.uuid4().hex[:8]
    voice, premix = work / f"voice-{tag}.wav", work / f"premix-{tag}.wav"
    try:
        # 1. every narration line at its place on the timeline, each brought to the same loudness first:
        #    lines that come from different speech requests differ by several dB
        inputs, graph, gains = [], [], []
        for i, (path, start) in enumerate(placed):
            inputs += ["-i", str(path)]
            gains.append(max(-LINE_GAIN_MAX, min(LINE_GAIN_MAX, VOICE_LUFS - loudness(path)["lufs"])))
            graph.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={gains[-1]:.2f}dB,"
                         f"adelay={int(round(start * 1000))}:all=1[n{i}]")
        if placed:
            graph.append("".join(f"[n{i}]" for i in range(len(placed))) + f"amix=inputs={len(placed)}:normalize=0:dropout_transition=0,apad[a]")
            # float samples: a peak over full scale is kept as it is here and dealt with once, at the end
            ff([*inputs, "-filter_complex", ";".join(graph), "-map", "[a]", "-t", f"{total:.3f}", "-ar", "48000", "-c:a", "pcm_f32le", str(voice)])
        else:
            ff(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{total:.3f}", "-c:a", "pcm_f32le", str(voice)])
        # 2. known levels first, so the balance is a decision and not a repair
        music_gain = MUSIC_LUFS - loudness(music, seconds=total)["lufs"] + gain_db
        fade_out = max(0.0, total - 2.5)
        # Both inputs of the compressor are cut into blocks of the same size. Without that a FLAC score, which
        # arrives in larger blocks than the voice, came out 1.3 s short and lost the end of its fade.
        mixgraph = (
            f"[0:a]asplit=2[voice][key0];[key0]asetnsamples=n={BLOCK}[key];"
            f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
            f"volume={music_gain:.2f}dB,afade=t=in:st=0:d=1.5,afade=t=out:st={fade_out:.3f}:d=2.5,asetnsamples=n={BLOCK}[music];"
            f"[music][key]sidechaincompress=threshold={DUCK['threshold']}:ratio={DUCK['ratio']}:attack={DUCK['attack']}:release={DUCK['release']}[ducked];"
            f"[voice][ducked]amix=inputs=2:normalize=0:dropout_transition=0[mix]")
        ff(["-i", str(voice), "-stream_loop", "-1", "-i", str(music), "-filter_complex", mixgraph, "-map", "[mix]",
            "-t", f"{total:.3f}", "-ar", "48000", "-c:a", "pcm_f32le", str(premix)])
        # 3. loudness for the platforms, last
        done = to_target(premix, out)
    finally:
        voice.unlink(missing_ok=True)
        premix.unlink(missing_ok=True)
    level = loudness(out)
    return {"lufs": level["lufs"], "true_peak_db": level["true_peak_db"], "line_gains_db": [round(g, 2) for g in gains],
            "music_gain_db": round(music_gain, 2), "normalised": done}


# ----------------------------------------------------------------------------- the stage


def run(ctx: Ctx, state: dict, mode: str = "film", plan_only: bool = False) -> dict:
    sb = ctx.sb
    V, fmt, fps = STAGE_VERSION["assemble"], sb["format"], sb["format"]["fps"]
    lang = ctx.narration_lang
    suffix = "" if lang == sb["language"]["narration"] else f".{lang}"
    script = get_index(ctx, state, "script", per_lang=True)
    narration = get_index(ctx, state, "narration", per_lang=True)
    music = get_index(ctx, state, "music")
    timeline = plan_timeline(sb, {k: v["seconds"] for k, v in narration.items()})
    total = timeline["total_s"]

    cues: dict[str, list] = {}       # per shot, timed from the start of the shot
    absolute: list = []              # for the whole film, timed from zero
    for t in timeline["shots"]:
        line = script["lines"].get(t["id"])
        if line and t["narration_start"] is not None:
            inside = narration[t["id"]].get("pauses")
            cues[t["id"]] = hold_last(subtitle_cues(line["subtitle"], t["narration_start"] - t["start"], t["narration_s"], pauses=inside),
                                      t["duration"] - 0.3)
            absolute += hold_last(subtitle_cues(line["subtitle"], t["narration_start"], t["narration_s"], pauses=inside),
                                  t["start"] + t["duration"] - 0.3)

    narr_dir, music_dir = ctx.out / "narration", ctx.out / "music"
    placed = [(narr_dir / narration[t["id"]]["file"], t["narration_start"]) for t in timeline["shots"]
              if t["narration_start"] is not None and narration[t["id"]]["file"]]
    mix_fp = {"v": V, "lines": [[narration[t["id"]]["key"], t["narration_start"]] for t in timeline["shots"] if t["narration_start"] is not None],
              "music": music["key"], "gain_db": sb["music"].get("gain_db", 0), "total": total, "duck": DUCK, "target": TARGET,
              "levels": [VOICE_LUFS, MUSIC_LUFS], "line_gain_max": LINE_GAIN_MAX, "block": BLOCK, "limit": LIMIT}
    mix = run_units(ctx, [Unit("assemble", f"mix{suffix}", mix_fp, "wav",
                               lambda tmp: build_mix(ctx, tmp, placed, music_dir / music["file"], total, sb["music"].get("gain_db", 0)))],
                    plan_only)[f"mix{suffix}"]

    card_lines = sb["end_card"]["lines"]
    card_frames = round(timeline["end_card_s"] * fps)
    files: dict[str, str] = {}
    tails: dict[str, dict] = {}      # shots whose clip ended before the shot did, and how the rest was covered

    if mode == "radio":
        exp = fmt["exports"][0]
        W, H, margin = exp["width"], exp["height"], exp.get("subtitle_margin_v", round(exp["height"] * 0.08))
        events = cue_events(absolute) + [card_event(card_lines, W, H, timeline["end_card_start"], total)]
        fp = {"v": V, "mix": mix.key, "events": events, "size": [W, H], "total": total, "style": SUBTITLE_STYLE}

        def radio(tmp: Path) -> dict:
            work = work_dir(ctx)
            ass = work / f"radio-{uuid.uuid4().hex[:8]}.ass"
            ass.write_text(ass_document(W, H, margin, events), encoding="utf-8")
            try:
                ff(["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={fps}:d={total:.3f}", "-i", str(mix.path), "-vf", f"ass={ass.name},format=yuv420p",
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-crf", "24", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(tmp)], cwd=work)
            finally:
                ass.unlink(missing_ok=True)
            return {}

        res = run_units(ctx, [Unit("assemble", f"radio_cut{suffix}", fp, "mp4", radio)], plan_only)[f"radio_cut{suffix}"]
        if res.path:
            files["radio"] = f"radio_cut{suffix}.mp4"
            shutil.copy2(res.path, ctx.out / files["radio"])
    else:
        shots = get_index(ctx, state, "shots", per_lang=True)
        shots_dir = ctx.out / "shots"
        focus_of = {shot["id"]: shot["keyframe"].get("focus_y", 0.5) for shot in sb["shots"]}
        for exp in fmt["exports"]:
            name, W, H = exp["name"], exp["width"], exp["height"]
            margin = exp.get("subtitle_margin_v", round(H * 0.08))
            units = []
            for t in timeline["shots"]:
                sid, clip = t["id"], shots[t["id"]]
                focus = focus_of.get(sid, 0.5)
                fp = {"v": V, "clip": clip["key"], "size": [W, H], "frames": t["frames"], "fps": fps, "cues": cues.get(sid, []),
                      "margin_v": margin, "style": SUBTITLE_STYLE, "focus_y": focus}

                def produce(tmp: Path, sid: str = sid, clip: dict = clip, frames: int = t["frames"], focus: float = focus) -> dict:
                    return render_scene(ctx, shots_dir / clip["file"], tmp, width=W, height=H, frames=frames, fps=fps,
                                        cues=cues.get(sid, []), margin_v=margin, focus_y=focus)

                units.append(Unit("assemble", f"{name}_{sid}{suffix}", fp, "mp4", produce))
            fp = {"v": V, "card": card_lines, "size": [W, H], "frames": card_frames, "fps": fps, "style": SUBTITLE_STYLE}
            units.append(Unit("assemble", f"{name}_endcard", fp, "mp4",
                              lambda tmp, W=W, H=H: render_card(ctx, tmp, lines=card_lines, width=W, height=H, frames=card_frames, fps=fps)))
            scenes = run_units(ctx, units, plan_only)
            for t in timeline["shots"]:
                meta = scenes[f"{name}_{t['id']}{suffix}"].meta
                if meta.get("tail_s"):
                    tails[t["id"]] = {"tail": meta["tail"], "tail_s": meta["tail_s"], "slowdown": meta.get("slowdown")}
            order = [scenes[u.id] for u in units]
            fp = {"v": V, "scenes": [r.key for r in order], "mix": mix.key}
            final = run_units(ctx, [Unit("assemble", f"film_{name}{suffix}", fp, "mp4",
                                         lambda tmp, order=order: join_and_mux(ctx, [r.path for r in order], mix.path, tmp))],
                              plan_only)[f"film_{name}{suffix}"]
            if final.path:
                files[name] = f"film_{name}{suffix}.mp4"
                shutil.copy2(final.path, ctx.out / files[name])

    index = {"mode": mode, "language": lang, "total_s": total, "files": files, "timeline": timeline, "mix": mix.meta,
             "cues": [[a, b, lines] for a, b, lines in absolute], "end_card": card_lines, "tails": tails}
    state["assemble"] = index
    if not plan_only:
        if files:
            srt = "".join(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n" + "\n".join(lines) + "\n\n" for i, (a, b, lines) in enumerate(absolute, 1))
            (ctx.out / f"subtitles.{sb['language']['subtitles']}{suffix}.srt").write_text(srt, encoding="utf-8")
        # film and radio cut keep separate indexes, so making a radio cut never hides the film from the final check
        (ctx.out / "assemble" / f"index.{mode}.{lang}.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
        if not files:
            raise PipelineError("assemble produced no file")
        for name, fname in files.items():
            ctx.say(f"  wrote {(ctx.out / fname).relative_to(ctx.root)}  ({total:.1f}s)")
    return index
