"""Beyond the floor: how well does the speech model handle other languages of Ethiopia and the Horn?

For each language it takes the film's first lines, has the text model translate them (the film's
own language uses the lines a person wrote), speaks them in one request per language, cuts that
into one file per line, then has the text model listen and write down what it heard. The match between the line and what was heard is a rough, automatic
intelligibility score.

This is a screening tool, not a verdict: for most languages a machine wrote the translation and a
machine did the listening. So the report comes with a listening sheet for a native speaker, and
their ratings are the evidence. A language that fails outright is a result too: the report keeps
the error text.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import providers
from .core import Ctx, PipelineError, Unit, file_sha, is_cached, run_units, shot_text
from .narration import LANGUAGE_NAMES as NAMES
from .narration import LISTEN_PROMPT, similarity, take

MAX_LINES = 4  # enough to hear the difference. One speech request per language, so four languages cost four of the day's ten


def one(ctx: Ctx, unit: Unit) -> tuple[Path | None, dict, str | None]:
    """Run one unit and keep going if it fails: a failure is a finding here."""
    try:
        res = run_units(ctx, [unit])[unit.id]
        return res.path, res.meta, None
    except PipelineError as e:
        return None, {}, str(e)[:200]


def run(ctx: Ctx, langs: list[str]) -> list[dict]:
    sb = ctx.sb
    sub = sb["language"]["subtitles"]
    source = [(s["id"], s["narration"][sub]) for s in sb["shots"] if s["narration"] and sub in s["narration"]][:MAX_LINES]
    if not source:
        raise PipelineError(f"the storyboard has no '{sub}' lines to translate from")
    voice, model, rows = sb["voice"], sb["models"]["tts"], []
    for lang in langs:
        name = NAMES.get(lang, lang)

        # 1. the lines in this language: written by a person for the film's own language, machine translated otherwise
        mine = []
        for sid, english in source:
            row = {"lang": lang, "language": name, "shot": sid, "source_line": english, "error": None}
            shot = next(s for s in sb["shots"] if s["id"] == sid)
            text, origin = shot_text(shot, lang), "written by a person"
            if text is None:
                origin = "machine translation"
                fp = {"line": english, "to": lang, "model": sb["models"]["text"]}

                def translate(tmp: Path, english: str = english, name: str = name, sid: str = sid, lang: str = lang) -> dict:
                    out, _ = providers.text(ctx, "langtest", f"{lang}_{sid}_text",
                                            f"Translate this line of film narration into {name}, in its usual script. "
                                            f"Reply with the translation only.\n{english}", kind="translate")
                    tmp.write_text(out, encoding="utf-8")
                    return {"text": out}

                _, meta, row["error"] = one(ctx, Unit("langtest", f"{lang}_{sid}_text", fp, "txt", translate))
                text = meta.get("text")
            row.update(text=text, origin=origin)
            mine.append(row)

        # 2. speak them in one request for the whole language: the speech tier counts requests, not lines
        units = {row["shot"]: Unit("langtest", f"{lang}_{row['shot']}_speech",
                                   {"text": row["text"], "voice": voice["name"], "style": voice["style"], "model": model}, "wav")
                 for row in mine if row["text"] and not row["error"]}
        missing = {sid: unit.fingerprint["text"] for sid, unit in units.items() if not is_cached(ctx, unit)}
        pieces: dict[str, Path] = {}
        if len(missing) > 1:
            try:
                pieces = take(ctx, missing, voice, model, stage="langtest", unit=f"{lang}_take", lang=lang)
                for row in mine:  # a line that cannot be cut out of the take is a finding too: one request per language, no more
                    if row["shot"] in missing and row["shot"] not in pieces:
                        row["error"] = "the take was spoken, but this line could not be cut out of it with certainty"
            except PipelineError as e:  # a language the model cannot speak is a finding, and no further request is spent on it
                for row in mine:
                    if row["shot"] in missing:
                        row["error"] = str(e)[:200]

        # 3. one file per line, then the listener writes down what it heard
        for row in mine:
            sid, text, wav = row["shot"], row["text"], None
            if text and not row["error"]:

                def speak(tmp: Path, text: str = text, sid: str = sid, lang: str = lang) -> dict:
                    if sid in pieces:
                        shutil.copy2(pieces[sid], tmp)
                    else:
                        raw, _ = providers.tts(ctx, "langtest", f"{lang}_{sid}_speech", text, voice=voice["name"], style=voice["style"])
                        tmp.write_bytes(raw)
                    return {"from_take": sid in pieces}

                units[sid].produce = speak
                wav, _, row["error"] = one(ctx, units[sid])
            if wav and not row["error"]:
                fp = {"audio": file_sha(wav), "model": sb["models"]["text"]}

                def listen(tmp: Path, wav: Path = wav, text: str = text, sid: str = sid, lang: str = lang) -> dict:
                    heard, _ = providers.text(ctx, "langtest", f"{lang}_{sid}_listen", LISTEN_PROMPT.format(language=NAMES.get(lang, lang)), kind="transcribe",
                                              parts=[("audio/wav", wav.read_bytes())], temperature=0.0)
                    result = {"heard": heard, "score": similarity(text, heard)}
                    tmp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                    return result

                _, meta, row["error"] = one(ctx, Unit("langtest", f"{lang}_{sid}_listen", fp, "json", listen))
                row.update(file=wav.name, heard=meta.get("heard"), score=meta.get("score"))
            rows.append(row)
        for folder in {piece.parent for piece in pieces.values()}:
            shutil.rmtree(folder, ignore_errors=True)

    out = ctx.out / "langtest"
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    report = ["# Language test", "", f"Speech model: `{sb['models']['tts']}`, voice {voice['name']}. Listener: `{sb['models']['text']}`.",
              "Score = how closely the listener's transcript matches the line that was spoken (1.00 = identical).", "",
              "| Language | Lines spoken | Lines failed | Mean match | Lowest match | Text from |", "|---|---:|---:|---:|---:|---|"]
    for lang in langs:
        mine = [r for r in rows if r["lang"] == lang]
        scores = [r["score"] for r in mine if r.get("score") is not None]
        mean = f"{sum(scores) / len(scores):.2f}" if scores else "n/a"
        report.append(f"| {NAMES.get(lang, lang)} | {len(scores)} | {sum(1 for r in mine if r['error'])} | {mean} | "
                      f"{min(scores):.2f}" + f" | {mine[0]['origin']} |" if scores else
                      f"| {NAMES.get(lang, lang)} | 0 | {sum(1 for r in mine if r['error'])} | n/a | n/a | {mine[0]['origin']} |")
    failures = [r for r in rows if r["error"]]
    if failures:
        report += ["", "## Failures", ""] + [f"- {r['language']} {r['shot']}: {r['error']}" for r in failures]
    report += ["", "## Listening sheet for a native speaker", "",
               "Play each file. Rate 1 (cannot understand) to 5 (sounds like a native speaker) and note any word said wrongly.", "",
               "| File | Language | Line | Rating 1-5 | Words said wrongly |", "|---|---|---|---|---|"]
    report += [f"| {r['file']} | {r['language']} | {r['text']} | | |" for r in rows if r.get("file")]
    (out / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    ctx.say("\n".join(report[:9 + len(langs)]))
    ctx.say(f"  full report and listening sheet: {(out / 'report.md').relative_to(ctx.root)}")
    return rows
