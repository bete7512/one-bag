"""Stage 2, narration: one audio file per narrated shot, then a listening check.

One file per shot keeps retakes cheap: change a line and only that line is spoken again.

The listening check is a round trip. The text model hears each file and writes down what it
heard, and that is compared with the script. A low score points at a line worth a human listen:
names and places are where text-to-speech goes wrong most often. It measures, it does not decide.
"""
from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from . import providers
from .core import STAGE_VERSION, Ctx, Unit, estimate_seconds, get_index, run_units, wav_seconds, write_index

LISTEN_PROMPT = ("Transcribe this audio exactly as spoken, in the script of the language being spoken. "
                 "Reply with the transcription only, no translation and no comments.")


def normalise(text: str) -> str:
    """Lower case, no punctuation, single spaces: so only the words are compared."""
    kept = "".join(" " if unicodedata.category(ch)[0] in "PSZ" else ch for ch in text.lower())
    return re.sub(r"\s+", " ", kept).strip()


def similarity(script: str, heard: str) -> float:
    return round(SequenceMatcher(None, normalise(script), normalise(heard)).ratio(), 3)


def run(ctx: Ctx, state: dict, plan_only: bool = False) -> dict:
    sb, lang = ctx.sb, ctx.narration_lang
    script = get_index(ctx, state, "script", per_lang=True)
    voice, qa = sb["voice"], sb.get("qa", {})

    units = []
    for sid, line in script["lines"].items():
        fp = {"v": STAGE_VERSION["narration"], "text": line["text"], "lang": lang, "voice": voice["name"],
              "style": voice["style"], "model": sb["models"]["tts"]}

        def produce(tmp: Path, sid: str = sid, text: str = line["text"]) -> dict:
            raw, _ = providers.tts(ctx, "narration", sid, text, voice=voice["name"], style=voice["style"])
            tmp.write_bytes(raw)
            return {"seconds": round(wav_seconds(tmp), 3)}

        units.append(Unit("narration", sid, fp, "wav", produce))
    spoken = run_units(ctx, units, plan_only)

    checks = {}
    if qa.get("roundtrip") and not plan_only:
        check_units = []
        for sid, res in spoken.items():
            text = script["lines"][sid]["text"]
            fp = {"v": STAGE_VERSION["narration"], "audio": res.key, "text": text, "model": sb["models"]["text"]}

            def produce(tmp: Path, sid: str = sid, text: str = text, wav: Path = res.path) -> dict:
                heard, _ = providers.text(ctx, "narration", f"{sid}_listen", LISTEN_PROMPT, kind="transcribe",
                                          parts=[("audio/wav", wav.read_bytes())], temperature=0.0)
                result = {"heard": heard, "score": similarity(text, heard)}
                tmp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                return result

            check_units.append(Unit("narration", f"{sid}_listen", fp, "json", produce))
        checks = run_units(ctx, check_units)

    floor = qa.get("roundtrip_min", 0.6)
    index = {}
    for sid, res in spoken.items():
        entry = {"file": res.path.name if res.path else None, "key": res.key,
                 "seconds": res.meta.get("seconds") or script["lines"][sid]["estimate_s"]}
        check = checks.get(f"{sid}_listen")
        if check:
            entry.update(heard=check.meta["heard"], roundtrip=check.meta["score"])
            if check.meta["score"] < floor:
                ctx.say(f"  listen to {sid}: the model heard \"{check.meta['heard'][:70]}\" (match {check.meta['score']:.2f}, floor {floor})")
        index[sid] = entry
    state["narration"] = index
    if not plan_only:
        write_index(ctx, "narration", index, per_lang=True)
    return index


__all__ = ["run", "similarity", "normalise", "estimate_seconds"]
