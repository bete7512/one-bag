"""Stage 1, script: settle the words of the film.

Reads the narration lines for the film's language from storyboard.json. A missing subtitle is
filled by machine translation (one logged, cached model call per line). Writes
outputs/script/index.<lang>.json, the one place the later stages read words from.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import providers
from .core import STAGE_VERSION, Ctx, PipelineError, Unit, estimate_seconds, run_units, shot_text, write_index


def run(ctx: Ctx, state: dict, plan_only: bool = False) -> dict:
    sb, lang, sub = ctx.sb, ctx.narration_lang, ctx.sb["language"]["subtitles"]
    lines: dict[str, dict] = {}
    units: list[Unit] = []
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

    for uid, res in run_units(ctx, units, plan_only).items():
        sid = uid.split("_")[0]
        lines[sid]["subtitle"] = res.meta.get("subtitle") or "(translation pending)"
        lines[sid]["machine_translated"] = True

    index = {"language": lang, "subtitles": sub, "lines": lines,
             "estimate_total_s": round(sum(v["estimate_s"] for v in lines.values()), 1)}
    state["script"] = index
    if not plan_only:
        write_index(ctx, "script", index, per_lang=True)
    return index
