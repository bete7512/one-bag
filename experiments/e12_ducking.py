"""E12: how far under the voice does the score sit at the brief's ducking ratio of 6, and at 3? Measured, not heard.

    python experiments/e12_ducking.py

No model is called: this is FFmpeg and arithmetic. The eight narration lines are placed where the radio cut
has them (outputs/assemble/index.radio.am.json) and mixed with one score, candidate 2 of the ACE-Step set,
twice. Each mix is made by the pipeline's own `assemble.build_mix`. The one thing changed between the two is
`ratio` in `assemble.DUCK`: first the pipeline's value, then the other one. Threshold, attack, release, the
levels before ducking, the gain from the storyboard and the loudness target stay as the pipeline has them.

A finished mix cannot say how loud the music is under the voice, so the same chain is run again per ratio
with the voice as the compressor's key only, not in the output. For that, two pieces of `build_mix` in
pipeline/assemble.py are copied into `voice_track` and `chain` below: its step 1 and its `mixgraph` (lines 215
to 221 and 228 to 234 on 25 Nov 2026). The copy is checked on every run: its premix, put through the pipeline's
`loudnorm_two_pass`, must give the same file as `build_mix`, byte for byte. If it does not, the run stops.

How each number is computed is in HOW below, and is written into the results with the numbers:
outputs/experiments/E12/results.json, next to the two mixes. Intermediate audio goes to a temporary folder.
"""
import array
import json
import math
import re
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import assemble  # noqa: E402
from pipeline.core import Ctx, ff, ff_capture, file_sha, loudness, wav_seconds  # noqa: E402

SCORE = "candidate_2__5e84c28c48f1a1a3.flac"  # the second of the three ACE-Step candidates in outputs/music/
DUCK = dict(assemble.DUCK)  # the pipeline's settings, as imported
RATIOS = [DUCK["ratio"], 3 if DUCK["ratio"] == 6 else 6]  # the pipeline's ratio first, then the other one
WINDOW_S, RATE = 0.05, 48000
MAX_BYTES = 20_000_000  # a mix larger than this is kept as FLAC
OUT = ROOT / "outputs" / "experiments" / "E12"

HOW = {
    "mix": "The finished mix as `pipeline.core.loudness` measures it (FFmpeg ebur128, peak=true): EBU R128 integrated loudness in LUFS and "
           "true peak in dBTP. lra_lu is the loudness range from the summary of the same filter.",
    "level": "FFmpeg astats gives the RMS level of every 50 ms of a file, both channels together. The level of a file over a set of time spans "
             "is 10*log10 of the mean of the squared level of the windows whose centre lies in a span, in dB below full scale (dBFS). It is "
             "not K-weighted and not gated, so a level in dBFS is not a level in LUFS: compare dBFS with dBFS only.",
    "speech and gaps": "Speech: each line from its start on the radio cut's timeline to that start plus the measured length of its file, pauses "
                       "inside a line included. Gaps: the seven stretches between the end of one line and the start of the next.",
    "stems": "voice: the narration track after its gain. music: the score after its gain and fades and after the compressor keyed by the voice, "
             "with no voice in it. music_unducked: the same without the compressor.",
    "reduction_db": "Level of music_unducked minus level of music over the same windows: what the compressor took off the music. "
                    "deepest_db is the largest value in any one 50 ms window.",
    "before_normaliser": "Levels of the stems as they go into the last step, loudnorm.",
    "in_final_mix": "The same after loudnorm. It applies one gain to voice and music together, so each 50 ms of a stem is scaled by the gain of "
                    "that 50 ms: mean square of the finished mix over mean square of the premix.",
    "voice_over_music_db": "Level of voice minus level of music, both over the speech spans.",
    "voice_over_music_lu": "The same in loudness units, before the normaliser: voice and music each cut down to the speech spans and measured "
                           "with `pipeline.core.loudness` (K-weighted and gated, one decimal).",
    "music_rise_in_gaps_db": "Level of music over the gaps minus level of music over the speech spans. It holds the score's own changes too: "
                             "see the two music_unducked levels.",
    "normaliser": "asked and ran: the mode loudnorm was asked for, and the mode it reports for its second pass. gain_speech_db and gain_gaps_db: "
                  "level of the finished mix minus level of the premix over the same windows. gain_low_db and gain_high_db: the 5th and the "
                  "95th percentile of that gain per 50 ms window, over the windows where the premix is above -60 dBFS.",
    "per_line": "voice_db, music_db, reduction_db and voice_over_music_db as above, over that line alone and before the normaliser. "
                "reduction_before_line_db: the reduction in the 50 ms before the first window of the line in which the voice is above the "
                "compressor's threshold. reduction_0_1s_in_db: the reduction in the 50 ms that start 0.1 s after that first window starts. "
                "back_within_3db_s and back_within_1db_s: the clock starts at the end of the last window of the line in which the voice is "
                "above the threshold, and stops at the start of the first window where the reduction is under 3 dB, or under 1 dB. null: the "
                "next line started first. silence_after_s: from the same start of the clock to the start of the next line, or to the end.",
    "per_gap": "music_db and reduction_db over that gap alone, before the normaliser.",
    "checks": "copy_gives_the_pipeline_mix: the copied chain, normalised by the pipeline's function, is the same file as the pipeline's mix, "
              "byte for byte. The run stops when it is not. "
              "premix_peak_dbfs: the highest sample of voice plus music before the premix is written as 16 bit. premix_samples_at_full_scale: "
              "samples of the 16 bit premix at the highest or the lowest value the format has. music_ends_s: the length of the music stem as "
              "the compressor gives it out, to hold against total_s.",
}


def voice_track(dst: Path, placed: list[tuple[Path, float]], total: float) -> None:
    """Every narration line at its place on the timeline. Copied from step 1 of `build_mix` in pipeline/assemble.py."""
    inputs, graph = [], []
    for i, (path, start) in enumerate(placed):
        inputs += ["-i", str(path)]
        graph.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,adelay={int(round(start * 1000))}:all=1[n{i}]")
    graph.append("".join(f"[n{i}]" for i in range(len(placed))) + f"amix=inputs={len(placed)}:normalize=0:dropout_transition=0,apad[a]")
    ff([*inputs, "-filter_complex", ";".join(graph), "-map", "[a]", "-t", f"{total:.3f}", "-ar", "48000", "-c:a", "pcm_s16le", str(dst)])


def chain(voice_gain: float, music_gain: float, total: float) -> list[str]:
    """The pipeline's mix graph, one string per step. Copied from `mixgraph` in `build_mix`, pipeline/assemble.py. Reads assemble.DUCK as it does."""
    duck = assemble.DUCK
    fade_out = max(0.0, total - 2.5)
    return [
        f"[0:a]volume={voice_gain:.2f}dB,asplit=2[voice][key]",
        f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
        f"volume={music_gain:.2f}dB,afade=t=in:st=0:d=1.5,afade=t=out:st={fade_out:.3f}:d=2.5[music]",
        f"[music][key]sidechaincompress=threshold={duck['threshold']}:ratio={duck['ratio']}:attack={duck['attack']}:release={duck['release']}[ducked]",
        "[voice][ducked]amix=inputs=2:normalize=0:dropout_transition=0[mix]",
    ]


def envelope(path: Path) -> list[float]:
    """Mean square of every 50 ms of a file, both channels together, as FFmpeg's astats measures it."""
    graph = (f"asetnsamples=n={round(RATE * WINDOW_S)}:p=0,astats=metadata=1:reset=1:measure_perchannel=none:measure_overall=RMS_level,"
             "ametadata=mode=print:key=lavfi.astats.Overall.RMS_level")
    found = re.findall(r"astats\.Overall\.RMS_level=(\S+)", ff_capture(["-i", str(path), "-af", graph, "-f", "null", "-"]))
    return [0.0 if v in ("-inf", "nan") else 10 ** (float(v) / 10) for v in found]


def level(env: list[float], spans: list[tuple[float, float]]) -> float:
    """RMS level in dBFS over the windows whose centre lies in one of the spans."""
    picked = [ms for k, ms in enumerate(env) if any(a <= (k + 0.5) * WINDOW_S < b for a, b in spans)]
    return 10 * math.log10(sum(picked) / len(picked))


def speech_only(src: Path, dst: Path, spans: list[tuple[float, float]]) -> Path:
    """The file cut down to the spans, joined end to end."""
    graph = ";".join(f"[0:a]atrim={a:.4f}:{b:.4f},asetpts=PTS-STARTPTS[p{i}]" for i, (a, b) in enumerate(spans))
    graph += ";" + "".join(f"[p{i}]" for i in range(len(spans))) + f"concat=n={len(spans)}:v=0:a=1[o]"
    ff(["-i", str(src), "-filter_complex", graph, "-map", "[o]", "-c:a", "pcm_f32le", str(dst)])
    return dst


def normaliser(premix: Path) -> dict:
    """What loudnorm did with this premix: the two passes of `assemble.loudnorm_two_pass`, copied, with the second one asked to report too."""
    def report(spec: str) -> dict:
        err = ff_capture(["-i", str(premix), "-af", spec + ":print_format=json", "-ar", "48000", "-f", "null", "-"])
        return json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S).group(0))

    target = assemble.TARGET
    spec = f"loudnorm=I={target['lufs']}:TP={target['true_peak']}:LRA={target['lra']}"
    m = report(spec)
    second = report(spec + f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
                           f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    return {"asked": "linear", "ran": second["normalization_type"], "premix_lufs": float(m["input_i"]), "premix_true_peak_db": float(m["input_tp"])}


def measure(tmp: Path, ratio: int, lines: list[tuple[str, float, float]], placed: list, voice: Path, music: Path, total: float, gain_db: float) -> dict:
    assemble.DUCK = {**DUCK, "ratio": ratio}  # the one thing changed. build_mix and chain read it when they are called
    out = OUT / f"mix_ratio_{ratio}.wav"
    meta = assemble.build_mix(Ctx(root=tmp, sb={}), out, placed, music, total, gain_db)  # the pipeline's own mix. Its work folder is under tmp
    r128 = ff_capture(["-i", str(out), "-map", "0:a:0", "-af", "ebur128", "-f", "null", "-"])
    lra = float(re.search(r"LRA:\s*(-?[\d.]+) LU", r128[r128.rfind("Summary:"):]).group(1))

    # The same chain again, for what build_mix deletes (the premix) and never writes (the music alone).
    steps = chain(meta["voice_gain_db"], meta["music_gain_db"], total)
    src, cut = ["-i", str(voice), "-stream_loop", "-1", "-i", str(music)], ["-t", f"{total:.3f}", "-ar", "48000"]
    premix, again = tmp / f"premix_{ratio}.wav", tmp / f"again_{ratio}.wav"
    ff([*src, "-filter_complex", ";".join(steps), "-map", "[mix]", *cut, "-c:a", "pcm_s16le", str(premix)])
    assemble.loudnorm_two_pass(premix, again)
    if file_sha(again) != file_sha(out):
        raise SystemExit("The copied chain no longer gives the pipeline's mix: build_mix in pipeline/assemble.py has changed. Copy its graph into chain() again.")
    stem = {name: tmp / f"{name}_{ratio}.wav" for name in ("voice", "music", "music_unducked")}  # 32 bit float: nothing is clipped or rounded
    ff([*src, "-filter_complex", ";".join(steps[:3]), "-map", "[voice]", *cut, "-c:a", "pcm_f32le", str(stem["voice"]),
        "-map", "[ducked]", *cut, "-c:a", "pcm_f32le", str(stem["music"])])
    ff([*src, "-filter_complex", steps[1], "-map", "[music]", *cut, "-c:a", "pcm_f32le", str(stem["music_unducked"])])
    peak = ff_capture(["-i", str(stem["voice"]), "-i", str(stem["music"]), "-filter_complex", "amix=inputs=2:normalize=0,astats=measure_perchannel=none[o]",
                       "-map", "[o]", "-f", "null", "-"])
    with wave.open(str(premix), "rb") as w:
        samples = array.array("h", w.readframes(w.getnframes()))
    checks = {"copy_gives_the_pipeline_mix": True,  # or the run has stopped above
              "premix_peak_dbfs": float(re.search(r"Peak level dB: (\S+)", peak).group(1)),
              "premix_samples_at_full_scale": samples.count(32767) + samples.count(-32768),
              "music_ends_s": wav_seconds(stem["music"])}

    env = {name: envelope(path) for name, path in {**stem, "premix": premix, "final": out}.items()}
    gain = [f / p if p > 0 else 0.0 for f, p in zip(env["final"], env["premix"])]  # what loudnorm did to each 50 ms, as a power ratio
    heard = {name: [s * g for s, g in zip(env[name], gain)] for name in ("voice", "music")}
    reduction = [10 * math.log10(u / m) if u > 0 and m > 0 else None for u, m in zip(env["music_unducked"], env["music"])]
    speech = [(a, b) for _, a, b in lines]
    gaps = [(lines[i][2], lines[i + 1][1]) for i in range(len(lines) - 1)]

    def taken_off(spans: list[tuple[float, float]]) -> float:
        return level(env["music_unducked"], spans) - level(env["music"], spans)

    def levels(e: dict) -> dict:
        return {"voice_speech_db": level(e["voice"], speech), "music_speech_db": level(e["music"], speech), "music_gaps_db": level(e["music"], gaps),
                "voice_over_music_db": level(e["voice"], speech) - level(e["music"], speech),
                "music_rise_in_gaps_db": level(e["music"], gaps) - level(e["music"], speech)}

    def back(last: int, until: float, within: float) -> float | None:
        for k in range(last + 1, len(reduction)):
            if k * WINDOW_S >= until:
                return None
            if reduction[k] is not None and reduction[k] < within:
                return (k - last - 1) * WINDOW_S
        return None

    per_line = []
    for i, (sid, a, b) in enumerate(lines):
        loud = [k for k in range(int(a / WINDOW_S), int(b / WINDOW_S) + 1) if env["voice"][k] > DUCK["threshold"] ** 2]  # voice above the threshold
        first, last = loud[0], loud[-1]
        until = lines[i + 1][1] if i + 1 < len(lines) else total
        per_line.append({"shot": sid, "voice_db": level(env["voice"], [(a, b)]), "music_db": level(env["music"], [(a, b)]), "reduction_db": taken_off([(a, b)]),
                         "voice_over_music_db": level(env["voice"], [(a, b)]) - level(env["music"], [(a, b)]),
                         "reduction_before_line_db": reduction[first - 1], "reduction_0_1s_in_db": reduction[first + 2],
                         "silence_after_s": until - (last + 1) * WINDOW_S, "back_within_3db_s": back(last, until, 3.0), "back_within_1db_s": back(last, until, 1.0)})
    per_gap = [{"after": lines[i][0], "seconds": b - a, "music_db": level(env["music"], [(a, b)]), "reduction_db": taken_off([(a, b)])}
               for i, (a, b) in enumerate(gaps)]
    before = {**levels(env), "music_unducked_speech_db": level(env["music_unducked"], speech), "music_unducked_gaps_db": level(env["music_unducked"], gaps),
              "voice_lufs": loudness(speech_only(stem["voice"], tmp / "voice_speech.wav", speech))["lufs"],
              "music_lufs": loudness(speech_only(stem["music"], tmp / "music_speech.wav", speech))["lufs"]}
    before["voice_over_music_lu"] = before["voice_lufs"] - before["music_lufs"]
    moved = sorted(10 * math.log10(g) for g, p in zip(gain, env["premix"]) if p > 1e-6 and g > 0)
    result = {
        "file": out.name,
        "mix": {"lufs": meta["lufs"], "true_peak_db": meta["true_peak_db"], "lra_lu": lra},
        "gains_before_ducking": {"voice_gain_db": meta["voice_gain_db"], "music_gain_db": meta["music_gain_db"]},
        "reduction_db": {"speech": taken_off(speech), "gaps": taken_off(gaps), "deepest_db": max(r for r in reduction if r is not None)},
        "before_normaliser": before, "in_final_mix": levels(heard),
        "normaliser": {**normaliser(premix), "gain_speech_db": level(env["final"], speech) - level(env["premix"], speech),
                       "gain_gaps_db": level(env["final"], gaps) - level(env["premix"], gaps),
                       "gain_low_db": moved[len(moved) // 20], "gain_high_db": moved[len(moved) * 19 // 20]},
        "per_line": per_line, "per_gap": per_gap, "checks": checks,
    }
    if out.stat().st_size > MAX_BYTES:
        ff(["-i", str(out), "-c:a", "flac", str(out.with_suffix(".flac"))])
        out.unlink()
        result["file"] = out.with_suffix(".flac").name
    return json.loads(json.dumps(result), parse_float=lambda x: round(float(x), 2))  # every number to two decimals


def main() -> None:
    out_dir = ROOT / "outputs"
    radio = json.loads((out_dir / "assemble" / "index.radio.am.json").read_text(encoding="utf-8"))
    narration = json.loads((out_dir / "narration" / "index.am.json").read_text(encoding="utf-8"))
    gain_db = json.loads((ROOT / "storyboard.json").read_text(encoding="utf-8"))["music"].get("gain_db", 0)
    total, music = radio["total_s"], out_dir / "music" / SCORE
    placed, lines = [], []
    for t in radio["timeline"]["shots"]:
        if t["narration_start"] is None:
            continue
        path = out_dir / "narration" / narration[t["id"]]["file"]
        seconds = wav_seconds(path)
        if abs(seconds - t["narration_s"]) > 0.002:
            raise SystemExit(f"{t['id']}: the file is {seconds:.3f} s long and the radio cut's timeline says {t['narration_s']:.3f} s. Make the radio cut again first.")
        placed.append((path, t["narration_start"]))
        lines.append((t["id"], t["narration_start"], t["narration_start"] + seconds))

    OUT.mkdir(parents=True, exist_ok=True)
    results = {"experiment": "E12", "changed": f"ratio of the sidechain compressor: {RATIOS[0]} (the pipeline) against {RATIOS[1]}",
               "held_fixed": {"duck": {k: v for k, v in DUCK.items() if k != "ratio"}, "levels_before_ducking_lufs": [assemble.VOICE_LUFS, assemble.MUSIC_LUFS],
                              "music_gain_db_in_storyboard": gain_db, "target": assemble.TARGET},
               "score": SCORE, "timeline": "outputs/assemble/index.radio.am.json", "total_s": total, "window_s": WINDOW_S,
               "lines": [{"shot": sid, "file": path.name, "start": a, "end": round(b, 3)} for (sid, a, b), (path, _) in zip(lines, placed)],
               "speech_s": round(sum(b - a for _, a, b in lines), 3), "gaps_s": round(sum(lines[i + 1][1] - lines[i][2] for i in range(len(lines) - 1)), 3),
               "how": HOW, "ratios": {}}
    with tempfile.TemporaryDirectory(prefix="e12-") as folder:
        tmp = Path(folder)
        voice_track(tmp / "voice.wav", placed, total)
        for ratio in RATIOS:
            results["ratios"][str(ratio)] = measure(tmp, ratio, lines, placed, tmp / "voice.wav", music, total, gain_db)
    assemble.DUCK = DUCK
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    a, b = (results["ratios"][str(r)] for r in RATIOS)
    print(f"E12  score {SCORE}, {len(lines)} lines on the radio cut's timeline, {total:.2f} s: {results['speech_s']:.1f} s of speech, "
          f"{results['gaps_s']:.1f} s of gaps between lines\n")
    print(f"{'':<56}{'ratio ' + str(RATIOS[0]):>10}{'ratio ' + str(RATIOS[1]):>10}")

    def row(label: str, pick) -> None:
        print(f"{label:<56}{pick(a)!s:>10}{pick(b)!s:>10}")

    row("mix: integrated loudness, LUFS", lambda r: r["mix"]["lufs"])
    row("mix: true peak, dBTP", lambda r: r["mix"]["true_peak_db"])
    row("mix: loudness range, LU", lambda r: r["mix"]["lra_lu"])
    row("the compressor takes off the music: speech, dB", lambda r: r["reduction_db"]["speech"])
    row("the compressor takes off the music: gaps, dB", lambda r: r["reduction_db"]["gaps"])
    row("the compressor takes off the music: deepest 50 ms, dB", lambda r: r["reduction_db"]["deepest_db"])
    for where in ("before_normaliser", "in_final_mix"):
        name = where.replace("_", " ")
        row(f"{name}: voice during speech, dBFS", lambda r: r[where]["voice_speech_db"])
        row(f"{name}: music during speech, dBFS", lambda r: r[where]["music_speech_db"])
        row(f"{name}: music in the gaps, dBFS", lambda r: r[where]["music_gaps_db"])
        row(f"{name}: voice over music, dB", lambda r: r[where]["voice_over_music_db"])
        row(f"{name}: music rises in the gaps by, dB", lambda r: r[where]["music_rise_in_gaps_db"])
    row("before normaliser: voice over music, LU", lambda r: r["before_normaliser"]["voice_over_music_lu"])
    row("before normaliser: score without ducking, speech, dBFS", lambda r: r["before_normaliser"]["music_unducked_speech_db"])
    row("before normaliser: score without ducking, gaps, dBFS", lambda r: r["before_normaliser"]["music_unducked_gaps_db"])
    row("normaliser: asked for linear, ran", lambda r: r["normaliser"]["ran"])
    row("normaliser: gain during speech, dB", lambda r: r["normaliser"]["gain_speech_db"])
    row("normaliser: gain in the gaps, dB", lambda r: r["normaliser"]["gain_gaps_db"])
    row("check: the copied chain gives the pipeline's mix", lambda r: r["checks"]["copy_gives_the_pipeline_mix"])
    row("check: peak of the premix before 16 bit, dBFS", lambda r: r["checks"]["premix_peak_dbfs"])
    row("check: samples of the premix at full scale", lambda r: r["checks"]["premix_samples_at_full_scale"])
    row(f"check: the music ends at, s (the mix at {total:.2f})", lambda r: r["checks"]["music_ends_s"])

    columns = [("voice dBFS", "voice_db"), ("music dBFS", "music_db"), ("taken off dB", "reduction_db"), ("voice over music dB", "voice_over_music_db"),
               ("0.1 s in, off dB", "reduction_0_1s_in_db"), ("silence after s", "silence_after_s"), ("back in 3 dB s", "back_within_3db_s"),
               ("back in 1 dB s", "back_within_1db_s")]
    print(f"\nper line, before the normaliser: ratio {RATIOS[0]} / ratio {RATIOS[1]}")
    print("shot " + "".join(f"{title:>21}" for title, _ in columns))
    for x, y in zip(a["per_line"], b["per_line"]):
        print(f"{x['shot']:<5}" + "".join(f"{'/'.join('-' if v is None else str(v) for v in (x[key], y[key])):>21}" for _, key in columns))
    print(f"\nper gap, and how each number is computed: {(OUT / 'results.json').relative_to(ROOT)}")
    print("mixes: " + ", ".join(f"{r['file']} (ratio {ratio})" for ratio, r in zip(RATIOS, (a, b))))


if __name__ == "__main__":
    main()
