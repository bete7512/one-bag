"""E12: how far under the voice does the score sit at the brief's ducking ratio of 6, and at 3? Measured, not heard.

    python experiments/e12_ducking.py

No model is called: this is FFmpeg and arithmetic. The eight narration lines are placed where the radio cut
has them (outputs/assemble/index.radio.am.json) and mixed with one score, candidate 2 of the ACE-Step set,
twice. Each mix is made by the pipeline's own `assemble.build_mix`. The one thing changed between the two is
`ratio` in `assemble.DUCK`: first the pipeline's value, then the other one. Everything else stays as the
pipeline has it.

The results have three parts, because measuring the mix changed the mix code twice on 25 Nov 2026.
`before` is the first run of this script, on the mix code of commit 7d3222a. It found a premix that clipped, a
loudness pass that rode the gain, and a FLAC score that ended 1.3 s early. `after_first_fix` is the second
run, on the code of commit 4a80a3e: no clipping and a whole score, but the loudness pass still rode the gain
while the code said it did not. `after` is what this script measures now, on the mix code named in `mix_code`.
The first two parts are kept as they were written and never measured again: their code is no longer in the
working tree. Each has one list that was added by hand before its mix files were replaced, measured with the
functions below and marked with a note: `finished_mix_per_line` in `before`, `aac_of_the_mix` in `after_first_fix`.

A finished mix cannot say how loud the music is under the voice, so the same chain is run again per ratio
with the voice as the compressor's key only, not in the output. For that, three pieces of pipeline/assemble.py
are copied below: step 1 of `build_mix` into `voice_track`, its `mixgraph` into `chain`, and the body of
`to_target` into `last_step`, which keeps the limited file. The copy is checked on every run: it must give the
same finished file as `build_mix`, byte for byte, or the run stops.

How each number is computed is in HOW below, and is written into the results with the numbers:
outputs/experiments/E12/results.json, next to the two mixes. Intermediate audio goes to a temporary folder.
"""
import array
import json
import math
import re
import subprocess
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
AAC = ["-c:a", "aac", "-b:a", "192k"]  # how the film's sound is encoded: `join_and_mux` in pipeline/assemble.py
OUT = ROOT / "outputs" / "experiments" / "E12"

HOW = {
    "mix": "lufs and true_peak_db: the finished mix as `pipeline.core.loudness` measures it (FFmpeg ebur128, peak=true), EBU R128 integrated "
           "loudness in LUFS and true peak in dBTP, one decimal. lra_lu is the loudness range from the summary of the same filter. "
           "lufs_2dp and true_peak_db_2dp: the same two from the meter inside FFmpeg's loudnorm, which prints two decimals. Nothing is "
           "normalised with it: it only measures. aac: the finished mix encoded as the film's sound is (AAC, 192k) and measured in both ways.",
    "level": "FFmpeg astats gives the RMS level of every 50 ms of a file, both channels together. The level of a file over a set of time spans "
             "is 10*log10 of the mean of the squared level of the windows whose centre lies in a span, in dB below full scale (dBFS). It is "
             "not K-weighted and not gated, so a level in dBFS is not a level in LUFS: compare dBFS with dBFS only.",
    "speech and gaps": "Speech: each line from its start on the radio cut's timeline to that start plus the measured length of its file, pauses "
                       "inside a line included. Gaps: the seven stretches between the end of one line and the start of the next.",
    "stems": "voice: the narration track, every line with its own gain. music: the score after its gain and fades and after the compressor "
             "keyed by the voice, with no voice in it. music_unducked: the same without the compressor. premix: voice plus music, as it "
             "goes into the last step. limited: the premix after the limiter.",
    "reduction_db": "Level of music_unducked minus level of music over the same windows: what the compressor took off the music. "
                    "deepest_db is the largest value in any one 50 ms window.",
    "before_normaliser": "Levels of the stems as they go into the last step (the limiter, then one gain).",
    "in_final_mix": "The same in the finished mix. The last step applies one gain to voice and music together, so each 50 ms of a stem is "
                    "scaled by the gain of that 50 ms: mean square of the finished mix over mean square of the premix. The finished mix is "
                    "read later by the limiter's delay, so that the same sound is compared.",
    "voice_over_music_db": "Level of voice minus level of music, both over the speech spans.",
    "voice_over_music_lu": "The same in loudness units, before the last step: voice and music each cut down to the speech spans and measured "
                           "with `pipeline.core.loudness` (K-weighted and gated, one decimal).",
    "music_rise_in_gaps_db": "Level of music over the gaps minus level of music over the speech spans. It holds the score's own changes too: "
                             "see the two music_unducked levels.",
    "limiter": "ceiling_dbfs: the limit `to_target` sets, null when it does not limit. delay_samples: how late the limiter gives its output, "
               "found by sending one click through it. The limited file is read later by that much. windows: 50 ms windows in the mix. "
               "windows_over_ceiling: windows of the premix with a sample over the ceiling. windows_touched: windows whose level the "
               "limiter lowered by 0.1 dB or more, and windows_touched_in_speech those of them inside a line. largest_peak_cut_db: the most "
               "it took off the highest sample of a window. largest_window_drop_db: the most it took off the level of a window. "
               "takes_off_speech_db: level of the premix minus level of the limited file over the speech spans. takes_off_lu: integrated "
               "loudness of the premix minus that of the limited file, both by the two-decimal meter.",
    "normaliser": "pipeline_says: what `build_mix` returns as `normalised`. The next numbers are those `to_target` works with, measured with "
                  "`pipeline.core.loudness` as it does: the premix, the gain planned from it (target loudness minus its loudness), the limited "
                  "file, gain_for_loudness_db (what would reach the target loudness after limiting), gain_peaks_allow_db (true-peak target "
                  "minus the true peak after limiting) and gain_db, the smaller of the two, which is applied. short_of_target_lu: the "
                  "loudness of the finished mix by the two-decimal meter, under the target. gain_speech_db and gain_gaps_db: level of the "
                  "finished mix minus level of the premix over the same windows, so the limiter is in them. gain_low_db and gain_high_db: "
                  "the 5th and the 95th percentile of that gain per 50 ms window, over the windows where the premix is above -60 dBFS. "
                  "after_limiter: the gain per 50 ms window from the limited file to the finished mix, over the same windows: its lowest, "
                  "5th percentile, 95th percentile and highest value, and highest minus lowest in thousandths of a dB. One fixed gain gives "
                  "the same value in every window, up to the rounding of the 16 bit file.",
    "per_line": "voice_db, music_db, reduction_db and voice_over_music_db as above, over that line alone and before the last step. gain_db: "
                "the gain `build_mix` gave the line. voice_lufs: the voice stem cut down to the line, by `pipeline.core.loudness`. "
                "limiter_takes_off_db: level of the premix minus level of the limited file over the line. limiter_takes_off_lu: the same two "
                "files cut down to the line, each by `pipeline.core.loudness`, premix minus limited. mix_db and mix_lufs: the finished "
                "mix over the line, voice and the music under it together, as a level and by `pipeline.core.loudness`. "
                "reduction_before_line_db: the reduction in the 50 ms before the first window of the line in which the voice is above the "
                "compressor's threshold. reduction_0_1s_in_db: the reduction in the 50 ms that start 0.1 s after that first window starts. "
                "back_within_3db_s and back_within_1db_s: the clock starts at the end of the last window of the line in which the voice is "
                "above the threshold, and stops at the start of the first window where the reduction is under 3 dB, or under 1 dB. null: the "
                "next line started first. silence_after_s: from the same start of the clock to the start of the next line, or to the end.",
    "line_spread": "Lowest, highest and highest minus lowest over the eight lines, for voice_db and for mix_lufs.",
    "per_gap": "music_db and reduction_db over that gap alone, before the last step.",
    "checks": "copy_gives_the_pipeline_mix: the copied chain gives the same finished file as the pipeline's `build_mix`, byte for byte. The "
              "run stops when it does not. premix_peak_dbfs: the highest sample of the premix. premix_samples_over_full_scale: samples of "
              "the premix at 1.0 or more, either sign. The premix is a float file, so they are kept as they are. "
              "mix_samples_at_full_scale: samples of the 16 bit finished mix at the highest or the lowest value the format has. "
              "music_ends_s: the length of the music stem as the compressor gives it out, to hold against total_s.",
}


def mix_code() -> dict:
    """Which mix code is measured: a hash of the file, and the commit that last changed it when git can say."""
    name = "pipeline/assemble.py"
    told = {"file": name, "sha256_first_16": file_sha(ROOT / name)}

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()

    try:  # three questions that change nothing in the repository
        commit = git("log", "-1", "--format=%h", "--", name)
        if commit:
            told.update(last_commit=commit, changed_since_that_commit=git("rev-parse", f"HEAD:{name}") != git("hash-object", name))
    except (OSError, subprocess.SubprocessError):
        pass
    return told


def voice_track(dst: Path, placed: list[tuple[Path, float]], gains: list[float], total: float) -> None:
    """Every narration line at its place on the timeline, with the gain build_mix gave it. Copied from step 1 of `build_mix` in pipeline/assemble.py."""
    inputs, graph = [], []
    for i, ((path, start), gain) in enumerate(zip(placed, gains)):
        inputs += ["-i", str(path)]
        graph.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={gain:.2f}dB,"
                     f"adelay={int(round(start * 1000))}:all=1[n{i}]")
    graph.append("".join(f"[n{i}]" for i in range(len(placed))) + f"amix=inputs={len(placed)}:normalize=0:dropout_transition=0,apad[a]")
    ff([*inputs, "-filter_complex", ";".join(graph), "-map", "[a]", "-t", f"{total:.3f}", "-ar", "48000", "-c:a", "pcm_f32le", str(dst)])


def chain(music_gain: float, total: float) -> list[str]:
    """The pipeline's mix graph, one string per step. Copied from `mixgraph` in `build_mix`, pipeline/assemble.py. Reads assemble.DUCK as it does."""
    duck, block = assemble.DUCK, assemble.BLOCK
    fade_out = max(0.0, total - 2.5)
    return [
        f"[0:a]asplit=2[voice][key0];[key0]asetnsamples=n={block}[key]",
        f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
        f"volume={music_gain:.2f}dB,afade=t=in:st=0:d=1.5,afade=t=out:st={fade_out:.3f}:d=2.5,asetnsamples=n={block}[music]",
        f"[music][key]sidechaincompress=threshold={duck['threshold']}:ratio={duck['ratio']}:attack={duck['attack']}:release={duck['release']}[ducked]",
        "[voice][ducked]amix=inputs=2:normalize=0:dropout_transition=0[mix]",
    ]


def last_step(premix: Path, dst: Path) -> dict:
    """The body of `assemble.to_target`, copied: measure, limit once if the peaks are in the way, measure again, one gain. It keeps the limited file."""
    target, limit = assemble.TARGET, assemble.LIMIT
    level = loudness(premix)
    gain = target["lufs"] - level["lufs"]
    told = {"premix_lufs": level["lufs"], "premix_true_peak_db": level["true_peak_db"], "planned_gain_db": gain, "ceiling_dbfs": None, "limiter": None, "limited": premix}
    if level["true_peak_db"] + gain > target["true_peak"]:
        ceiling = target["true_peak"] - gain - limit["margin_db"]
        limiter = f"alimiter=limit={min(1.0, 10 ** (ceiling / 20)):.4f}:attack={limit['attack']}:release={limit['release']}:level=false"
        limited = premix.with_name(premix.stem + "-limited.wav")
        ff(["-i", str(premix), "-af", limiter, "-ar", "48000", "-c:a", "pcm_f32le", str(limited)])
        level = loudness(limited)
        for_loudness, peaks_allow = target["lufs"] - level["lufs"], target["true_peak"] - level["true_peak_db"]
        gain = min(for_loudness, peaks_allow)
        told.update(ceiling_dbfs=ceiling, limiter=limiter, limited=limited, limited_lufs=level["lufs"], limited_true_peak_db=level["true_peak_db"],
                    gain_for_loudness_db=for_loudness, gain_peaks_allow_db=peaks_allow)
    ff(["-i", str(told["limited"]), "-af", f"volume={gain:.2f}dB", "-ar", "48000", "-c:a", "pcm_s16le", str(dst)])
    return {**told, "gain_db": gain}


def meter(path: Path) -> dict:
    """Integrated loudness and true peak with two decimals, from the meter inside FFmpeg's loudnorm. It only measures here."""
    err = ff_capture(["-i", str(path), "-map", "0:a:0", "-af", "loudnorm=print_format=json", "-f", "null", "-"])
    found = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S).group(0))
    return {"lufs": float(found["input_i"]), "true_peak_db": float(found["input_tp"])}


def floats(path: Path) -> array.array:
    """Every sample of a file as a float, the channels in turn."""
    raw = path.with_suffix(".f32")
    ff(["-i", str(path), "-c:a", "pcm_f32le", "-f", "f32le", str(raw)])
    samples = array.array("f")
    samples.frombytes(raw.read_bytes())
    raw.unlink()
    return samples


def limiter_delay(limiter: str | None, tmp: Path) -> int:
    """How many samples late the limiter gives its output: one click is sent through it and looked for."""
    if not limiter:
        return 0
    click, late = tmp / "click.wav", tmp / "click_limited.wav"
    ff(["-f", "lavfi", "-i", f"aevalsrc='if(eq(n\\,{RATE // 2})\\,0.9\\,0)':s={RATE}:d=1", "-c:a", "pcm_f32le", str(click)])
    ff(["-i", str(click), "-af", limiter, "-c:a", "pcm_f32le", str(late)])
    heard = floats(late)
    return max(range(len(heard)), key=lambda i: abs(heard[i])) - RATE // 2


def envelope(path: Path, skip: int = 0, what: str = "RMS_level") -> list[float]:
    """Mean square of every 50 ms of a file, both channels together, as FFmpeg's astats measures it. With what="Peak_level": the square of
    the highest sample of every 50 ms. `skip` leaves out that many samples at the start."""
    graph = (f"atrim=start_sample={skip},asetnsamples=n={round(RATE * WINDOW_S)}:p=0,astats=metadata=1:reset=1:measure_perchannel=none:"
             f"measure_overall={what},ametadata=mode=print:key=lavfi.astats.Overall.{what}")
    found = re.findall(rf"astats\.Overall\.{what}=(\S+)", ff_capture(["-i", str(path), "-af", graph, "-f", "null", "-"]))
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


def measure(tmp: Path, ratio: int, lines: list[tuple[str, float, float]], placed: list, music: Path, total: float, gain_db: float) -> dict:
    assemble.DUCK = {**DUCK, "ratio": ratio}  # the one thing changed. build_mix and chain read it when they are called
    out = OUT / f"mix_ratio_{ratio}.wav"
    meta = assemble.build_mix(Ctx(root=tmp, sb={}), out, placed, music, total, gain_db)  # the pipeline's own mix. Its work folder is under tmp
    r128 = ff_capture(["-i", str(out), "-map", "0:a:0", "-af", "ebur128", "-f", "null", "-"])
    lra = float(re.search(r"LRA:\s*(-?[\d.]+) LU", r128[r128.rfind("Summary:"):]).group(1))

    # The same chain again, for what build_mix deletes (the premix, the limited file) and never writes (the music alone).
    voice, premix, again = tmp / f"voice_track_{ratio}.wav", tmp / f"premix_{ratio}.wav", tmp / f"again_{ratio}.wav"
    voice_track(voice, placed, meta["line_gains_db"], total)
    steps = chain(meta["music_gain_db"], total)
    src, cut = ["-i", str(voice), "-stream_loop", "-1", "-i", str(music)], ["-t", f"{total:.3f}", "-ar", "48000", "-c:a", "pcm_f32le"]
    ff([*src, "-filter_complex", ";".join(steps), "-map", "[mix]", *cut, str(premix)])
    told = last_step(premix, again)
    if file_sha(again) != file_sha(out):
        raise SystemExit("The copied chain no longer gives the pipeline's mix: build_mix or to_target in pipeline/assemble.py has changed. "
                         "Copy them into voice_track(), chain() and last_step() again.")
    stem = {name: tmp / f"{name}_{ratio}.wav" for name in ("voice", "music", "music_unducked")}
    ff([*src, "-filter_complex", ";".join(steps[:3]), "-map", "[voice]", *cut, str(stem["voice"]), "-map", "[ducked]", *cut, str(stem["music"])])
    ff([*src, "-filter_complex", steps[1], "-map", "[music]", *cut, str(stem["music_unducked"])])
    limited, delay = told["limited"], limiter_delay(told["limiter"], tmp)
    encoded = tmp / f"mix_{ratio}.m4a"
    ff(["-i", str(out), *AAC, str(encoded)])
    fine = {name: meter(path) for name, path in (("premix", premix), ("limited", limited), ("mix", out), ("aac", encoded))}
    with wave.open(str(out), "rb") as w:
        mixed = array.array("h", w.readframes(w.getnframes()))
    loud = floats(premix)
    checks = {"copy_gives_the_pipeline_mix": True,  # or the run has stopped above
              "premix_peak_dbfs": 20 * math.log10(max(max(loud), -min(loud))), "premix_samples_over_full_scale": sum(1 for x in loud if x >= 1.0 or x <= -1.0),
              "mix_samples_at_full_scale": mixed.count(32767) + mixed.count(-32768), "music_ends_s": wav_seconds(stem["music"])}

    env = {name: envelope(path) for name, path in {**stem, "premix": premix}.items()}
    env.update(limited=envelope(limited, delay), final=envelope(out, delay))  # read later by the limiter's delay: the same sound in the same window
    whole = min(len(env[name]) for name in ("premix", "limited", "final")) - 1  # the last window is not a full one in every file
    gain = [f / p if p > 0 else 0.0 for f, p in zip(env["final"], env["premix"])]  # what the last step did to each 50 ms, as a power ratio
    heard = {name: [s * g for s, g in zip(env[name], gain)] for name in ("voice", "music")}
    reduction = [10 * math.log10(u / m) if u > 0 and m > 0 else None for u, m in zip(env["music_unducked"], env["music"])]
    speech = [(a, b) for _, a, b in lines]
    gaps = [(lines[i][2], lines[i + 1][1]) for i in range(len(lines) - 1)]
    later = delay / RATE

    def taken_off(spans: list[tuple[float, float]], a: str = "music_unducked", b: str = "music") -> float:
        return level(env[a], spans) - level(env[b], spans)

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

    def moved(top: str, bottom: str) -> list[float]:
        """The gain from one file to another in every 50 ms window where there is enough sound to measure it, lowest first."""
        return sorted(10 * math.log10(env[top][k] / env[bottom][k]) for k in range(whole) if env["premix"][k] > 1e-6 and env[top][k] > 0 and env[bottom][k] > 0)

    # what the limiter did, window by window
    drop = [10 * math.log10(env["premix"][k] / env["limited"][k]) if env["limited"][k] > 0 else 0.0 for k in range(whole)]
    peak, peak_limited = envelope(premix, 0, "Peak_level"), envelope(limited, delay, "Peak_level")
    cut_off = [10 * math.log10(peak[k] / peak_limited[k]) if peak_limited[k] > 0 else 0.0 for k in range(whole)]
    in_speech = [any(a <= (k + 0.5) * WINDOW_S < b for a, b in speech) for k in range(whole)]
    ceiling = told["ceiling_dbfs"]
    limiter = {"ceiling_dbfs": ceiling, "delay_samples": delay, "windows": whole + 1,
               "windows_over_ceiling": sum(1 for k in range(whole) if ceiling is not None and peak[k] > 10 ** (ceiling / 10)),
               "windows_touched": sum(1 for d in drop if d >= 0.1), "windows_touched_in_speech": sum(1 for d, s in zip(drop, in_speech) if d >= 0.1 and s),
               "largest_peak_cut_db": max(cut_off), "largest_window_drop_db": max(drop),
               "takes_off_speech_db": taken_off(speech, "premix", "limited"), "takes_off_lu": fine["premix"]["lufs"] - fine["limited"]["lufs"]}

    per_line = []
    for i, (sid, a, b) in enumerate(lines):
        over = [k for k in range(int(a / WINDOW_S), int(b / WINDOW_S) + 1) if env["voice"][k] > DUCK["threshold"] ** 2]  # voice above the threshold
        first, last = over[0], over[-1]
        until = lines[i + 1][1] if i + 1 < len(lines) else total
        per_line.append({"shot": sid, "gain_db": meta["line_gains_db"][i], "voice_db": level(env["voice"], [(a, b)]),
                         "voice_lufs": loudness(speech_only(stem["voice"], tmp / "line.wav", [(a, b)]))["lufs"],
                         "music_db": level(env["music"], [(a, b)]), "reduction_db": taken_off([(a, b)]),
                         "voice_over_music_db": level(env["voice"], [(a, b)]) - level(env["music"], [(a, b)]),
                         "limiter_takes_off_db": taken_off([(a, b)], "premix", "limited"),
                         "limiter_takes_off_lu": loudness(speech_only(premix, tmp / "line.wav", [(a, b)]))["lufs"]
                         - loudness(speech_only(limited, tmp / "line.wav", [(a + later, b + later)]))["lufs"], "mix_db": level(env["final"], [(a, b)]),
                         "mix_lufs": loudness(speech_only(out, tmp / "line.wav", [(a + later, b + later)]))["lufs"],
                         "reduction_before_line_db": reduction[first - 1], "reduction_0_1s_in_db": reduction[first + 2],
                         "silence_after_s": until - (last + 1) * WINDOW_S, "back_within_3db_s": back(last, until, 3.0), "back_within_1db_s": back(last, until, 1.0)})
    per_gap = [{"after": lines[i][0], "seconds": b - a, "music_db": level(env["music"], [(a, b)]), "reduction_db": taken_off([(a, b)])}
               for i, (a, b) in enumerate(gaps)]
    before = {**levels(env), "music_unducked_speech_db": level(env["music_unducked"], speech), "music_unducked_gaps_db": level(env["music_unducked"], gaps),
              "voice_lufs": loudness(speech_only(stem["voice"], tmp / "voice_speech.wav", speech))["lufs"],
              "music_lufs": loudness(speech_only(stem["music"], tmp / "music_speech.wav", speech))["lufs"]}
    before["voice_over_music_lu"] = before["voice_lufs"] - before["music_lufs"]
    all_of_it, alone = moved("final", "premix"), moved("final", "limited")
    result = {
        "file": out.name,
        "mix": {"lufs": meta["lufs"], "true_peak_db": meta["true_peak_db"], "lra_lu": lra, "lufs_2dp": fine["mix"]["lufs"], "true_peak_db_2dp": fine["mix"]["true_peak_db"],
                "aac": {**loudness(encoded), "lufs_2dp": fine["aac"]["lufs"], "true_peak_db_2dp": fine["aac"]["true_peak_db"]}},
        "gains_before_ducking": {"line_gains_db": meta["line_gains_db"], "music_gain_db": meta["music_gain_db"]},
        "reduction_db": {"speech": taken_off(speech), "gaps": taken_off(gaps), "deepest_db": max(r for r in reduction if r is not None)},
        "before_normaliser": before, "in_final_mix": levels(heard), "limiter": limiter,
        "normaliser": {"pipeline_says": meta["normalised"], **{k: v for k, v in told.items() if k not in ("limiter", "limited", "ceiling_dbfs")},
                       "short_of_target_lu": assemble.TARGET["lufs"] - fine["mix"]["lufs"],
                       "gain_speech_db": taken_off(speech, "final", "premix"), "gain_gaps_db": taken_off(gaps, "final", "premix"),
                       "gain_low_db": all_of_it[len(all_of_it) // 20], "gain_high_db": all_of_it[len(all_of_it) * 19 // 20],
                       "after_limiter": {"lowest_db": alone[0], "low_db": alone[len(alone) // 20], "high_db": alone[len(alone) * 19 // 20],
                                         "highest_db": alone[-1], "spread_thousandths_db": round(1000 * (alone[-1] - alone[0])), "windows": len(alone)}},
        "line_spread": {key: {"lowest": min(x[key] for x in per_line), "highest": max(x[key] for x in per_line),
                              "spread": max(x[key] for x in per_line) - min(x[key] for x in per_line)} for key in ("voice_db", "mix_lufs")},
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
    old = json.loads((OUT / "results.json").read_text(encoding="utf-8")) if (OUT / "results.json").exists() else {}
    kept = {name: old[name] for name in ("before", "after_first_fix") if name in old}  # carried over as they were written, never measured again
    after = {"note": "Measured by this script on the mix code named in mix_code.", "changed": f"ratio of the sidechain compressor: {RATIOS[0]} (the pipeline) against {RATIOS[1]}",
             "mix_code": mix_code(),
             "held_fixed": {"duck": {k: v for k, v in DUCK.items() if k != "ratio"}, "levels_before_ducking_lufs": [assemble.VOICE_LUFS, assemble.MUSIC_LUFS],
                            "line_gain_max_db": assemble.LINE_GAIN_MAX, "block_samples": assemble.BLOCK, "limit": assemble.LIMIT,
                            "music_gain_db_in_storyboard": gain_db, "target": assemble.TARGET},
             "score": SCORE, "timeline": "outputs/assemble/index.radio.am.json", "total_s": total, "window_s": WINDOW_S,
             "lines": [{"shot": sid, "file": path.name, "start": a, "end": round(b, 3)} for (sid, a, b), (path, _) in zip(lines, placed)],
             "speech_s": round(sum(b - a for _, a, b in lines), 3), "gaps_s": round(sum(lines[i + 1][1] - lines[i][2] for i in range(len(lines) - 1)), 3),
             "how": HOW, "ratios": {}}
    with tempfile.TemporaryDirectory(prefix="e12-") as folder:
        for ratio in RATIOS:
            after["ratios"][str(ratio)] = measure(Path(folder), ratio, lines, placed, music, total, gain_db)
    assemble.DUCK = DUCK
    (OUT / "results.json").write_text(json.dumps({"experiment": "E12", **kept, "after": after}, ensure_ascii=False, indent=1), encoding="utf-8")

    def block(part: dict, ratio: int) -> dict:
        """One part's numbers at one ratio, with the lists that were added to a kept part by hand folded in."""
        found = dict(part.get("ratios", {}).get(str(ratio), {}))
        later = part.get("finished_mix_per_line", {}).get(str(ratio))
        if later:
            found["per_line"] = [{**x, **y} for x, y in zip(found["per_line"], later)]
        extra = part.get("aac_of_the_mix", {}).get(str(ratio))
        if extra:
            found["mix"] = {**found["mix"], "aac": extra["aac"], "lufs_2dp": extra["mix_2dp"]["lufs"], "true_peak_db_2dp": extra["mix_2dp"]["true_peak_db"]}
        return found

    def says(r: dict) -> str:
        told = r["normaliser"].get("pipeline_says")
        return told["how"] if isinstance(told, dict) else told or "asked for " + r["normaliser"]["asked"]

    def spread(key: str):
        def pick(r: dict) -> str:
            values = [x[key] for x in r["per_line"]]
            return f"{min(values)} to {max(values)}: {round(max(values) - min(values), 2)}"
        return pick

    def after_limiter(r: dict) -> str:
        n = r["normaliser"]
        if "after_limiter" in n:
            return "{lowest_db} to {highest_db}: {:.3f}".format(n["after_limiter"]["spread_thousandths_db"] / 1000, **n["after_limiter"])
        return f"5th to 95th percentile {n['loudnorm_low_db']} to {n['loudnorm_high_db']}"

    rows = [
        ("mix: integrated loudness, LUFS", lambda r: r["mix"]["lufs"]),
        ("mix: true peak, dBTP", lambda r: r["mix"]["true_peak_db"]),
        ("mix: loudness range, LU", lambda r: r["mix"]["lra_lu"]),
        ("mix: the same two with two decimals", lambda r: f"{r['mix']['lufs_2dp']} / {r['mix']['true_peak_db_2dp']}"),
        ("mix as AAC 192k: loudness / true peak", lambda r: f"{r['mix']['aac']['lufs_2dp']} / {r['mix']['aac']['true_peak_db_2dp']}"),
        ("mix: 16 bit samples at full scale", lambda r: r["checks"]["mix_samples_at_full_scale"]),
        ("premix: highest sample, dBFS", lambda r: r["checks"]["premix_peak_dbfs"]),
        ("premix: samples at or over full scale", lambda r: r["checks"].get("premix_samples_over_full_scale", r["checks"].get("premix_samples_at_full_scale"))),
        (f"music ends at, s (the mix at {total:.2f})", lambda r: r["checks"]["music_ends_s"]),
        ("last step: the pipeline says", says),
        ("last step: what loudnorm itself reports", lambda r: r["normaliser"].get("second_pass_ran") or r["normaliser"].get("ran") or "no loudnorm in it"),
        ("last step: gain it applies, dB", lambda r: r["normaliser"]["gain_db"]),
        ("last step: short of the target loudness by, LU", lambda r: r["normaliser"]["short_of_target_lu"]),
        ("gain after the limiter per 50 ms, dB: low to high: spread", after_limiter),
        ("premix to mix: gain during speech / in the gaps, dB", lambda r: f"{r['normaliser']['gain_speech_db']} / {r['normaliser']['gain_gaps_db']}"),
        ("premix to mix: gain per 50 ms, 5th / 95th percentile, dB", lambda r: f"{r['normaliser']['gain_low_db']} / {r['normaliser']['gain_high_db']}"),
        ("limiter: ceiling, dBFS", lambda r: r["limiter"]["ceiling_dbfs"]),
        ("limiter: 50 ms windows with a sample over the ceiling", lambda r: f"{r['limiter']['windows_over_ceiling']} of {r['limiter']['windows']}"),
        ("limiter: windows it lowers by 0.1 dB or more", lambda r: r["limiter"]["windows_touched"]),
        ("limiter: most it takes off a peak / a window, dB", lambda r: f"{r['limiter']['largest_peak_cut_db']} / {r['limiter']['largest_window_drop_db']}"),
        ("limiter: takes off the mix during speech, dB / LU", lambda r: f"{r['limiter']['takes_off_speech_db']} / {r['limiter']['takes_off_lu']}"),
        ("limiter: takes off a line, least to most, dB", lambda r: f"{min(x['limiter_takes_off_db'] for x in r['per_line'])} to {max(x['limiter_takes_off_db'] for x in r['per_line'])}"),
        ("limiter: takes off a line, least to most, LU", lambda r: f"{min(x['limiter_takes_off_lu'] for x in r['per_line'])} to {max(x['limiter_takes_off_lu'] for x in r['per_line'])}"),
        ("limiter: its output is late by, samples", lambda r: r["limiter"]["delay_samples"]),
        ("compressor takes off the music: speech / gaps / deepest", lambda r: "{speech} / {gaps} / {deepest_db}".format(**r["reduction_db"])),
        ("before the last step: voice / music during speech, dBFS", lambda r: f"{r['before_normaliser']['voice_speech_db']} / {r['before_normaliser']['music_speech_db']}"),
        ("before the last step: music in the gaps, dBFS", lambda r: r["before_normaliser"]["music_gaps_db"]),
        ("before the last step: voice over music, dB / LU", lambda r: f"{r['before_normaliser']['voice_over_music_db']} / {r['before_normaliser']['voice_over_music_lu']}"),
        ("finished mix: voice / music during speech, dBFS", lambda r: f"{r['in_final_mix']['voice_speech_db']} / {r['in_final_mix']['music_speech_db']}"),
        ("finished mix: music in the gaps, dBFS", lambda r: r["in_final_mix"]["music_gaps_db"]),
        ("finished mix: voice over music, dB", lambda r: r["in_final_mix"]["voice_over_music_db"]),
        ("voice over music, the line with least / with most, dB", lambda r: f"{min(x['voice_over_music_db'] for x in r['per_line'])} / {max(x['voice_over_music_db'] for x in r['per_line'])}"),
        ("lines before the last step, voice dBFS: low to high: spread", spread("voice_db")),
        ("lines in the finished mix, LUFS: low to high: spread", spread("mix_lufs")),
    ]
    parts = [("before", kept.get("before", {})), ("after the first fix", kept.get("after_first_fix", {})), ("after", after)]
    print(f"E12  score {SCORE}, {len(lines)} lines on the radio cut's timeline, {total:.2f} s: {after['speech_s']:.1f} s of speech, "
          f"{after['gaps_s']:.1f} s of gaps between lines. Mix code: {after['mix_code']}")
    for ratio in RATIOS:
        print(f"\nratio {ratio}" + " " * (52 - len(str(ratio))) + "".join(f"{name:>36}" for name, _ in parts))
        for label, pick in rows:
            cells = []
            for _, part in parts:
                try:
                    cells.append(str(pick(block(part, ratio))))
                except (KeyError, TypeError):  # that run did not measure this
                    cells.append("-")
            print(f"{label:<58}" + "".join(f"{c:>36}" for c in cells))

    a, b = (after["ratios"][str(r)] for r in RATIOS)
    shown = [("gain dB", "gain_db"), ("voice LUFS", "voice_lufs"), ("voice dBFS", "voice_db"), ("music dBFS", "music_db"), ("taken off dB", "reduction_db"),
             ("voice over music dB", "voice_over_music_db"), ("limiter takes dB", "limiter_takes_off_db"), ("limiter takes LU", "limiter_takes_off_lu"),
             ("in the mix LUFS", "mix_lufs"),
             ("back in 3 dB s", "back_within_3db_s"), ("back in 1 dB s", "back_within_1db_s")]
    print(f"\nafter, per line: ratio {RATIOS[0]} / ratio {RATIOS[1]}")
    print("shot " + "".join(f"{title:>21}" for title, _ in shown))
    for x, y in zip(a["per_line"], b["per_line"]):
        print(f"{x['shot']:<5}" + "".join(f"{'/'.join('-' if v is None else str(v) for v in (x[key], y[key])):>21}" for _, key in shown))
    print(f"\nper gap, the two earlier runs, and how each number is computed: {(OUT / 'results.json').relative_to(ROOT)}")
    print("mixes: " + ", ".join(f"{r['file']} (ratio {ratio})" for ratio, r in zip(RATIOS, (a, b))))


if __name__ == "__main__":
    main()
