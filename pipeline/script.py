"""Stage 1, script: settle the words of the film.

Reads the narration lines for the film's language from storyboard.json. A missing subtitle is
filled by machine translation (one logged, cached model call per line). A written subtitle is
checked against its line: a model translates the line literally and names every difference in
meaning. The film is graded on accurate subtitles, and the people who read them cannot hear
whether they are. The check measures, it does not decide: it is an optional unit, and what it
finds goes to the author. Writes outputs/script/index.<lang>.json, the one place the later
stages read words from.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import providers
from .core import STAGE_VERSION, Ctx, PipelineError, Unit, estimate_seconds, run_units, shot_text, write_index


CHECK_VERSION = 2  # bump when the question changes
CHECK_PROMPT = """A short film is narrated in the language with the code "{lang}" and subtitled in "{sub}". Check one subtitle against the line it stands for.

Spoken line: {text}
Subtitle: {subtitle}

Report as JSON:
- literal: a plain, literal translation of the spoken line into the subtitle's language.
- faithful: true if the subtitle says what the line says, with nothing added, dropped or changed in meaning. A subtitle may be shorter and plainer than the line. A different tense, a different number or a different person is a change in meaning. Words in round brackets that explain a date or a name to a reader of the subtitle's language are not an addition, as long as what they say is correct: if it is wrong, report it as a difference.
- differences: each difference in meaning, as a short phrase. An empty list if there are none."""
CHECK_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["literal", "faithful", "differences"],
                "properties": {"literal": {"type": "string"}, "faithful": {"type": "boolean"},
                               "differences": {"type": "array", "items": {"type": "string"}}}}


def run(ctx: Ctx, state: dict, plan_only: bool = False) -> dict:
    sb, lang, sub = ctx.sb, ctx.narration_lang, ctx.sb["language"]["subtitles"]
    checker = sb["models"].get("judge") or sb["models"]["text"]  # the stricter model, when the storyboard names one
    lines: dict[str, dict] = {}
    units: list[Unit] = []
    checks: list[Unit] = []
    for s in sb["shots"]:
        if s["narration"] is None:
            continue
        text = shot_text(s, lang)
        if text is None:
            raise PipelineError(f"{s['id']}: no narration line for language '{lang}'. Add narration.{lang} to storyboard.json.")
        lines[s["id"]] = {"text": text, "subtitle": s["narration"].get(sub), "machine_translated": False,
                          "estimate_s": estimate_seconds(text)}
        if lines[s["id"]]["subtitle"] is None:
            fp = {"v": STAGE_VERSION["script"], "text": text, "from": lang, "to": sub, "model": sb["models"]["text"]}

            def produce(tmp: Path, sid: str = s["id"], text: str = text) -> dict:
                prompt = (f"Translate this line of film narration from language '{lang}' to language '{sub}'. "
                          f"Keep it short and plain, for a subtitle. Reply with the translation only.\n{text}")
                out, _ = providers.text(ctx, "script", f"{sid}_subtitle", prompt, kind="translate")
                tmp.write_text(json.dumps({"subtitle": out}, ensure_ascii=False), encoding="utf-8")
                return {"subtitle": out}

            units.append(Unit("script", f"{s['id']}_subtitle", fp, "json", produce))
        elif sb.get("qa", {}).get("subtitle_check", True) and lang != sub:
            written = lines[s["id"]]["subtitle"]
            fp = {"v": STAGE_VERSION["script"], "check": CHECK_VERSION, "text": text, "subtitle": written, "from": lang, "to": sub, "model": checker}

            def check(tmp: Path, sid: str = s["id"], text: str = text, written: str = written) -> dict:
                answer, _ = providers.text(ctx, "script", f"{sid}_subtitle_check", CHECK_PROMPT.format(lang=lang, sub=sub, text=text, subtitle=written),
                                           kind="subtitle_check", json_mode=True, schema=CHECK_SCHEMA, temperature=0.0, model=checker)
                found = re.search(r"\{.*\}", answer, re.S)
                try:
                    result = json.loads(found.group(0)) if found else {}
                except json.JSONDecodeError:
                    result = {}
                if not isinstance(result.get("faithful"), bool):
                    raise PipelineError(f"the subtitle check for {sid} did not answer in the asked form: {answer[:120]}")
                tmp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                return result

            checks.append(Unit("script", f"{s['id']}_subtitle_check", fp, "json", check, optional=True))

    for uid, res in run_units(ctx, units, plan_only).items():
        sid = uid.split("_")[0]
        lines[sid]["subtitle"] = res.meta.get("subtitle") or "(translation pending)"
        lines[sid]["machine_translated"] = True

    for uid, res in run_units(ctx, checks, plan_only).items():
        sid = uid.split("_")[0]
        if isinstance(res.meta.get("faithful"), bool):
            lines[sid]["subtitle_check"] = {"faithful": res.meta["faithful"], "literal": res.meta.get("literal", ""),
                                            "differences": res.meta.get("differences", [])}
            if not res.meta["faithful"] and not plan_only:
                ctx.say(f"  look at {sid}: the subtitle may not say what the line says: {'; '.join(res.meta.get('differences', []))[:200]}")

    index = {"language": lang, "subtitles": sub, "lines": lines,
             "estimate_total_s": round(sum(v["estimate_s"] for v in lines.values()), 1)}
    state["script"] = index
    if not plan_only:
        write_index(ctx, "script", index, per_lang=True)
    return index
