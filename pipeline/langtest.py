"""Beyond the floor: how well does the speech model handle other languages of Ethiopia and the Horn?

For each language it takes the film's first lines, has the text model translate them (the film's
own language uses the lines a person wrote), speaks each one, then has the text model listen and
write down what it heard. The match between the line and what was heard is a rough, automatic
intelligibility score.

This is a screening tool, not a verdict: for most languages a machine wrote the translation and a
machine did the listening. So the report comes with a listening sheet for a native speaker, and
their ratings are the evidence. A language that fails outright is a result too: the report keeps
the error text.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import providers
from .core import Ctx, PipelineError, Unit, run_units, shot_text
from .narration import LISTEN_PROMPT, similarity

NAMES = {"am": "Amharic", "ti": "Tigrinya", "so": "Somali", "om": "Afaan Oromo", "en": "English", "sw": "Swahili", "ar": "Arabic"}
MAX_LINES = 4  # enough to hear the difference, small enough for a free quota


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
    voice, rows = sb["voice"], []
    for lang in langs:
        name = NAMES.get(lang, lang)
        for sid, english in source:
            row = {"lang": lang, "language": name, "shot": sid, "source_line": english}
            shot = next(s for s in sb["shots"] if s["id"] == sid)
            text, origin, error = shot_text(shot, lang), "written by a person", None
            if text is None:
                origin = "machine translation"
                fp = {"line": english, "to": lang, "model": sb["models"]["text"]}

                def translate(tmp: Path, english: str = english, name: str = name, sid: str = sid, lang: str = lang) -> dict:
                    out, _ = providers.text(ctx, "langtest", f"{lang}_{sid}_text",
                                            f"Translate this line of film narration into {name}, in its usual script. "
                                            f"Reply with the translation only.\n{english}", kind="translate")
                    tmp.write_text(out, encoding="utf-8")
                    return {"text": out}

                _, meta, error = one(ctx, Unit("langtest", f"{lang}_{sid}_text", fp, "txt", translate))
                text = meta.get("text")
            row.update(text=text, origin=origin)
            wav = None
            if text and not error:
                fp = {"text": text, "voice": voice["name"], "style": voice["style"], "model": sb["models"]["tts"]}

                def speak(tmp: Path, text: str = text, sid: str = sid, lang: str = lang) -> dict:
                    raw, _ = providers.tts(ctx, "langtest", f"{lang}_{sid}_speech", text, voice=voice["name"], style=voice["style"])
                    tmp.write_bytes(raw)
                    return {}

                wav, _, error = one(ctx, Unit("langtest", f"{lang}_{sid}_speech", fp, "wav", speak))
            if wav and not error:
                fp = {"audio": wav.name, "model": sb["models"]["text"]}

                def listen(tmp: Path, wav: Path = wav, text: str = text, sid: str = sid, lang: str = lang) -> dict:
                    heard, _ = providers.text(ctx, "langtest", f"{lang}_{sid}_listen", LISTEN_PROMPT, kind="transcribe",
                                              parts=[("audio/wav", wav.read_bytes())], temperature=0.0)
                    result = {"heard": heard, "score": similarity(text, heard)}
                    tmp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                    return result

                _, meta, error = one(ctx, Unit("langtest", f"{lang}_{sid}_listen", fp, "json", listen))
                row.update(file=wav.name, heard=meta.get("heard"), score=meta.get("score"))
            row["error"] = error
            rows.append(row)

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
