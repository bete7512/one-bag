"""Stage 2, narration: one audio file per narrated shot, then a listening check.

One file per shot keeps the edit simple: picture follows the voice, shot by shot, and a changed
line replaces one file.

One request per take, not per line. The free speech tier counts requests (ten a day when this was
written), so the lines that are missing from the cache are spoken in a single request with a long
pause after each, and the answer is cut into one file per line here. One changed line is still one
request for that line. The model's answer is kept in narration/takes/, so cutting it again costs nothing.

A take is cut at its longest pauses when they stand out clearly. When they do not, a line is kept
only where a second method agrees on where it is: what is said in each phrase, matched to the
script. The first real take showed why. The voice paused inside a line as long as between two lines,
and after some lines it read the pause tag aloud. Where the two methods disagree nothing is guessed:
that line is spoken again in a request of its own.

The listening check is a round trip. The text model hears each file and writes down what it
heard, and that is compared with the script. A low score points at a line worth a human listen:
names and places are where text-to-speech goes wrong most often, and a cut in the wrong place
shows up here too. It measures, it does not decide.
"""
from __future__ import annotations

import json
import re
import shutil
import unicodedata
import uuid
import wave
from difflib import SequenceMatcher
from pathlib import Path

from . import providers
from .core import (STAGE_VERSION, Ctx, PipelineError, Unit, estimate_seconds, ff, ff_capture, file_sha, free_tier_use, get_index, is_cached,
                   now, run_units, sha, wav_seconds, write_index)

SILENCE = {"noise_db": -38, "min_s": 0.25}  # what counts as a pause when a take is cut
MIN_CUT_MARGIN = 1.5                        # the pauses used as cuts must be this many times longer than any pause left inside a line
MIN_WORD_MATCH = 0.5                        # a line's phrases, read together, must match its text at least this well to count as found
AGREE_S = 0.3                               # the cut by pauses and the cut by words agree on a line when both ends are this close
PAD_IN, PAD_OUT = 0.10, 0.20                # silence kept before and after each line

# The language is named: asked only for "the script of the language being spoken", the listener wrote two of the
# first eight Amharic lines in Latin letters, and a correct line then scored 0.16 against its script.
LISTEN_PROMPT = ("This audio is narration in {language}. Transcribe it exactly as spoken, in the usual script of {language}. "
                 "Reply with the transcription only, no translation and no comments.")


def normalise(text: str) -> str:
    """Lower case, no punctuation, single spaces: so only the words are compared."""
    kept = "".join(" " if unicodedata.category(ch)[0] in "PSZ" else ch for ch in text.lower())
    return re.sub(r"\s+", " ", kept).strip()


def similarity(script: str, heard: str) -> float:
    return round(SequenceMatcher(None, normalise(script), normalise(heard)).ratio(), 3)


def pauses(wav: Path) -> tuple[list[tuple[float, float]], float]:
    """Every silence in an audio file as (start, end), and the length of the file. Measured with FFmpeg."""
    total = wav_seconds(wav)
    err = ff_capture(["-i", str(wav), "-af", f"silencedetect=noise={SILENCE['noise_db']}dB:d={SILENCE['min_s']}", "-f", "null", "-"])
    number = r"(-?[\d.]+(?:e[-+]?\d+)?)"  # FFmpeg prints a start very close to zero as 4.16667e-05
    starts = [max(0.0, float(x)) for x in re.findall(rf"silence_start: {number}", err)]
    ends = [float(x) for x in re.findall(rf"silence_end: {number}", err)]
    return list(zip(starts, ends + [total] * (len(starts) - len(ends)))), total


def speech_spans(wav: Path, lines: int) -> tuple[list[tuple[float, float]], float]:
    """Where each of `lines` lines sits in one audio: it is cut at its longest pauses.

    Returns the spans and a margin: how many times longer the shortest pause used as a cut is than
    the longest pause left inside a line. A margin near 1 means the cuts are a guess.
    """
    silences, total = pauses(wav)
    lead = silences[0][1] if silences and silences[0][0] <= 0.05 else 0.0
    trail = silences[-1][0] if silences and silences[-1][1] >= total - 0.05 else total
    inside = [(a, b) for a, b in silences if a > 0.05 and b < total - 0.05]
    if len(inside) < lines - 1:
        raise PipelineError(f"{wav.name}: {lines} lines were spoken but only {len(inside)} pauses can be heard between them, so it cannot be cut. "
                            f"Listen to the file. The take is kept, so a fix to the cutting costs no speech request.")
    by_length = sorted(inside, key=lambda p: p[1] - p[0], reverse=True)
    cuts = sorted(by_length[:lines - 1])
    left = by_length[lines - 1:]
    margin = round((cuts and min(b - a for a, b in cuts) or 0.0) / (left[0][1] - left[0][0]), 2) if cuts and left else 99.0
    edges = [lead, *[t for pause in cuts for t in pause], trail]
    spans = [(max(0.0, edges[2 * i] - PAD_IN), min(total, edges[2 * i + 1] + PAD_OUT)) for i in range(lines)]
    return spans, margin


LANGUAGE_NAMES = {"am": "Amharic", "ti": "Tigrinya", "so": "Somali", "om": "Afaan Oromo", "en": "English", "sw": "Swahili", "ar": "Arabic"}

PHRASE_PROMPT = ("This clip is one phrase from a narration in {language}. It can be a single word. Transcribe it exactly as spoken, "
                 "in the usual script of {language}. Reply with the transcription only, no translation and no comments.")


def phrases(wav: Path) -> list[tuple[float, float]]:
    """The stretches of speech in an audio file, each between two pauses."""
    silences, total = pauses(wav)
    edges = [0.0, *[t for pause in silences for t in pause], total]
    return [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2) if edges[i + 1] - edges[i] > 0.12]


def assign(heard: list[str], lines: list[str]) -> list[int]:
    """Give every phrase to a line: phrases stay in order, every line gets at least one, and the split is the one where
    each line's phrases, read together, are closest to that line's text. Returns the number of phrases per line."""
    n, k = len(heard), len(lines)
    if n < k:
        raise PipelineError(f"{n} phrases were heard for {k} lines: the take cannot be matched to the script")
    best: dict[tuple[int, int], tuple[float, int]] = {(0, 0): (0.0, 0)}  # (phrases used, lines done) -> (score, where the last line began)
    for done in range(1, k + 1):
        for used in range(done, n - (k - done) + 1):
            options = [(best[(start, done - 1)][0] + similarity(lines[done - 1], " ".join(heard[start:used])), start)
                       for start in range(done - 1, used) if (start, done - 1) in best]
            if options:
                best[(used, done)] = max(options)
    counts, used = [], n
    for done in range(k, 0, -1):
        start = best[(used, done)][1]
        counts.append(used - start)
        used = start
    return counts[::-1]


def hear_phrases(ctx: Ctx, wav: Path, found: list[tuple[float, float]], stage: str, unit: str, lang: str | None = None) -> list[str]:
    """What is said in each phrase of a take. One request to the listening model per phrase: requests that held
    many clips were refused as overload again and again on the day this was written, while single clips passed."""
    language = LANGUAGE_NAMES.get(lang or ctx.narration_lang, lang or ctx.narration_lang)
    work = ctx.out / "tmp" / f"phrases-{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True, exist_ok=True)
    heard = []
    try:
        for n, (start, end) in enumerate(found, start=1):
            piece = work / f"{n:03d}.wav"
            ff(["-i", str(wav), "-ss", f"{max(0.0, start - 0.05):.3f}", "-to", f"{end + 0.05:.3f}", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(piece)])
            said, _ = providers.text(ctx, stage, f"{unit}_phrase_{n:02d}", PHRASE_PROMPT.format(language=language), kind="transcribe",
                                     parts=[("audio/wav", piece.read_bytes())], temperature=0.0)
            heard.append(said)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return heard


def spans_by_words(wav: Path, found: list[tuple[float, float]], heard: list[str], lines: list[str]) -> tuple[list[tuple[float, float]], list[float]]:
    """Where each line sits in a take, found from what is said and not from how long the pauses are.

    A voice that tells a story pauses inside a line as long as between two lines. So every phrase between
    two pauses is transcribed and the phrases are matched to the script. A line runs from its first phrase
    to its last. Returns the spans and, for each line, how well its phrases match its text.
    """
    total, spans, matches, at = wav_seconds(wav), [], [], 0
    for line, count in zip(lines, assign(heard, lines)):
        spans.append((max(0.0, found[at][0] - PAD_IN), min(total, found[at + count - 1][1] + PAD_OUT)))
        matches.append(similarity(line, " ".join(heard[at:at + count])))
        at += count
    return spans, matches


def cut(ctx: Ctx, wav: Path, start: float, end: float, out: Path, note: str | None = None) -> None:
    ff(["-i", str(wav), "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-c:a", "pcm_s16le", str(out)])
    if ctx.mock and note is not None:  # the mock listener reads the line from a private chunk of the file: put it back
        with wave.open(str(out), "rb") as w:
            frames, rate = w.readframes(w.getnframes()), w.getframerate()
        out.write_bytes(providers.pcm_to_wav(frames, rate, note=note))


def take(ctx: Ctx, lines: dict[str, str], voice: dict, model: str, stage: str = "narration", unit: str = "take", lang: str | None = None) -> dict[str, Path]:
    """Speak several lines in one request and return one audio file for each line that can be cut out of it with certainty.

    The take is kept in <stage>/takes/. A line that is missing from the answer was not cut: the caller speaks it alone.
    """
    # the key is what the model was asked. How its answer is cut here is not part of it: a better cut must not cost a new request
    key = sha({"lines": list(lines.items()), "voice": voice["name"], "style": voice["style"], "model": model})[:16]
    folder = ctx.out / stage / "takes"
    record = folder / f"take__{key}.json"
    if not record.exists():  # the model's answer is kept as it came, so it is asked for once
        wavs, meta = providers.tts_take(ctx, stage, unit, list(lines.values()), voice=voice["name"], style=voice["style"], model=model)
        folder.mkdir(parents=True, exist_ok=True)
        files = []
        for n, data in enumerate(wavs, start=1):
            files.append(f"take__{key}_{n}.wav")
            (folder / files[-1]).write_bytes(data)
        record.write_text(json.dumps({"key": key, "created": now(), "lines": list(lines), "files": files, "voice": voice["name"],
                                      "audio_seconds": meta.get("audio_seconds")}, ensure_ascii=False, indent=1), encoding="utf-8")
    info = json.loads(record.read_text(encoding="utf-8"))
    blocks = [folder / name for name in info["files"]]
    work = ctx.out / "tmp" / f"take-{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True, exist_ok=True)
    pieces: dict[str, Path] = {}
    if len(blocks) == len(lines):                 # the model answered with one audio per line: only the pause at its end is trimmed
        for (sid, text), block in zip(lines.items(), blocks):
            (span,), _ = speech_spans(block, 1)
            pieces[sid] = work / f"{sid}.wav"
            cut(ctx, block, *span, pieces[sid], note=text)
        margin = None
    elif len(blocks) == 1:                        # one audio for everything: cut it at the long pauses
        try:
            spans, margin = speech_spans(blocks[0], len(lines))
        except PipelineError:
            spans, margin = [], 0.0
        sure = list(lines)
        if margin < MIN_CUT_MARGIN:  # the pauses alone do not say where a line ends: ask the words too, and keep a line only where both agree
            found = phrases(blocks[0])
            if len(info.get("heard", [])) != len(found):  # what was heard is kept with the take, so cutting it again asks nobody
                info["heard"] = hear_phrases(ctx, blocks[0], found, stage, unit, lang)
                record.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
            try:
                by_words, matches = spans_by_words(blocks[0], found, info["heard"], list(lines.values()))
            except PipelineError:
                by_words, matches = [], []
            info["word_match"] = dict(zip(lines, matches))
            sure = [sid for sid, a, b, match in zip(lines, spans, by_words, matches)
                    if abs(a[0] - b[0]) <= AGREE_S and abs(a[1] - b[1]) <= AGREE_S and match >= MIN_WORD_MATCH]
            again = [sid for sid in lines if sid not in sure]
            ctx.say(f"  [{stage}] the pauses do not mark the lines of this take (margin {margin}). The pauses and the words agree on "
                    f"{', '.join(sure) or 'no line'}." + (f" Not cut, so nothing is guessed: {', '.join(again)}." if again else ""))
        info["cut_from_take"] = sure
        for (sid, text), span in zip(lines.items(), spans):
            if sid in sure:
                pieces[sid] = work / f"{sid}.wav"
                cut(ctx, blocks[0], *span, pieces[sid], note=text)
    else:
        raise PipelineError(f"the take came back as {len(blocks)} audio parts for {len(lines)} lines. It is kept in {folder.relative_to(ctx.root)}: listen to it.")
    info.update(cut_margin=margin, spans={sid: round(wav_seconds(path), 3) for sid, path in pieces.items()})
    record.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return pieces


def run(ctx: Ctx, state: dict, plan_only: bool = False) -> dict:
    sb, lang = ctx.sb, ctx.narration_lang
    script = get_index(ctx, state, "script", per_lang=True)
    voice, qa, model = sb["voice"], sb.get("qa", {}), sb["models"]["tts"]

    fingerprints = {sid: {"v": STAGE_VERSION["narration"], "text": line["text"], "lang": lang, "voice": voice["name"],
                          "style": voice["style"], "model": model} for sid, line in script["lines"].items()}
    missing = [sid for sid, fp in fingerprints.items() if not is_cached(ctx, Unit("narration", sid, fp, "wav"))]
    if missing:
        use = None if ctx.mock else free_tier_use(ctx, model)
        left = f", {max(0, use['limit']['requests_per_day'] - use['requests'])} left today" if use and use["limit"].get("requests_per_day") else ""
        ctx.say(f"  [narration] {len(missing)} line(s) to speak in 1 speech request{left}. A line that cannot be cut out of the take "
                f"with certainty costs one more request")
    pieces = take(ctx, {sid: script["lines"][sid]["text"] for sid in missing}, voice, model) if len(missing) > 1 and not plan_only else {}

    units = []
    for sid, line in script["lines"].items():

        def produce(tmp: Path, sid: str = sid, text: str = line["text"]) -> dict:
            if sid in pieces:
                shutil.copy2(pieces[sid], tmp)
            else:
                raw, _ = providers.tts(ctx, "narration", sid, text, voice=voice["name"], style=voice["style"])
                tmp.write_bytes(raw)
            return {"seconds": round(wav_seconds(tmp), 3), "from_take": sid in pieces}

        units.append(Unit("narration", sid, fingerprints[sid], "wav", produce))
    spoken = run_units(ctx, units, plan_only)
    for path in {piece.parent for piece in pieces.values()}:
        shutil.rmtree(path, ignore_errors=True)

    checks = {}
    if qa.get("roundtrip") and not plan_only:
        check_units = []
        for sid, res in spoken.items():
            text = script["lines"][sid]["text"]
            prompt = LISTEN_PROMPT.format(language=LANGUAGE_NAMES.get(lang, lang))
            fp = {"v": STAGE_VERSION["narration"], "audio": file_sha(res.path), "text": text, "model": sb["models"]["text"],  # the sound itself
                  "question": sha(prompt)[:12]}

            def produce(tmp: Path, sid: str = sid, text: str = text, wav: Path = res.path, prompt: str = prompt) -> dict:
                heard, _ = providers.text(ctx, "narration", f"{sid}_listen", prompt, kind="transcribe",
                                          parts=[("audio/wav", wav.read_bytes())], temperature=0.0)
                result = {"heard": heard, "score": similarity(text, heard)}
                tmp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                return result

            # optional: the check measures. If the model cannot be reached the line is still spoken, and a person listens.
            check_units.append(Unit("narration", f"{sid}_listen", fp, "json", produce, optional=True))
        checks = run_units(ctx, check_units)

    floor = qa.get("roundtrip_min", 0.6)
    index = {}
    for sid, res in spoken.items():
        entry = {"file": res.path.name if res.path else None, "key": res.key,
                 "seconds": res.meta.get("seconds") or script["lines"][sid]["estimate_s"]}
        if res.path and not plan_only:  # the silences inside the line, so its subtitles can change where the voice stops
            entry["pauses"] = [[round(a, 2), round(b, 2)] for a, b in pauses(res.path)[0]]
        check = checks.get(f"{sid}_listen")
        if check and "score" in check.meta:
            entry.update(heard=check.meta["heard"], roundtrip=check.meta["score"])
            if check.meta["score"] < floor:
                ctx.say(f"  listen to {sid}: the model heard \"{check.meta['heard'][:70]}\" (match {check.meta['score']:.2f}, floor {floor})")
        elif check:
            ctx.say(f"  listen to {sid} yourself: the listening check did not run. The next run tries again.")
        index[sid] = entry
    state["narration"] = index
    if not plan_only:
        write_index(ctx, "narration", index, per_lang=True)
    return index


__all__ = ["run", "similarity", "normalise", "estimate_seconds"]
