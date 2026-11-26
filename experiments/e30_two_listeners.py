"""E30: when the listener writes a word differently, is it the voice or the listener?

    python experiments/e30_two_listeners.py

The listening check of the film uses one speech model. In the ten lines of the cut it wrote nine
words differently from the script. One model cannot say whose fault that is. This script has a
second listener, the text model that listened before 26 Nov, write down the same ten audio files,
and then compares word by word: a word of the script is in doubt only when neither listener wrote
it. Every call goes through the pipeline's provider code, so each attempt is a line in runs.jsonl
with stage "experiment". Results go to outputs/experiments/E30/results.json. A line that has an
answer for the same audio file is not asked about again.
"""
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import providers  # noqa: E402
from pipeline.core import PipelineError, fold, make_ctx  # noqa: E402
from pipeline.narration import LANGUAGE_NAMES, LISTEN_PROMPT, similarity  # noqa: E402


def unmatched(script: list[str], heard: list[str]) -> list[str]:
    """The words of the script that the listener did not write, after the two are lined up in order."""
    blocks = SequenceMatcher(None, script, heard, autojunk=False).get_matching_blocks()
    kept = {i for b in blocks for i in range(b.a, b.a + b.size)}
    return [w for i, w in enumerate(script) if i not in kept]


def main() -> None:
    ctx = make_ctx(root=ROOT)
    lang = ctx.narration_lang
    index = json.loads((ctx.out / "narration" / f"index.{lang}.json").read_text(encoding="utf-8"))
    lines = {s["id"]: s["narration"][lang] for s in ctx.sb["shots"] if s["narration"]}
    out = ctx.out / "experiments" / "E30" / "results.json"
    results = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    prompt = LISTEN_PROMPT.format(language=LANGUAGE_NAMES.get(lang, lang))
    for sid, text in lines.items():
        entry = index[sid]
        if results.get(sid, {}).get("file") != entry["file"]:
            try:
                heard, _ = providers.text(ctx, "experiment", f"E30_{sid}", prompt, kind="transcribe",
                                          parts=[("audio/wav", (ctx.out / "narration" / entry["file"]).read_bytes())], temperature=0.0)
            except PipelineError as e:
                print(f"{sid}: failed, {e}")
                continue
            results[sid] = {"file": entry["file"], "text_model_heard": heard}
        row = results[sid]
        script = fold(text).split()
        by_speech = unmatched(script, fold(entry.get("heard", "")).split())
        by_text = unmatched(script, fold(row["text_model_heard"]).split())
        row.update(speech_model_heard=entry.get("heard"), speech_model_match=entry.get("roundtrip"),
                   text_model_match=similarity(text, row["text_model_heard"]),
                   not_written_by_speech_model=by_speech, not_written_by_text_model=by_text,
                   not_written_by_either=[w for w in by_speech if w in by_text])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{sid}  speech model {row['speech_model_match']}  text model {row['text_model_match']}  "
              f"not written by the speech model {by_speech}  by the text model {by_text}  by either {row['not_written_by_either']}")
    rows = [results[sid] for sid in lines if sid in results]
    print(f"\n{len(rows)} lines. Words not written by the speech model: {sum(len(r['not_written_by_speech_model']) for r in rows)}, "
          f"by the text model: {sum(len(r['not_written_by_text_model']) for r in rows)}, by either: {sum(len(r['not_written_by_either']) for r in rows)}")


if __name__ == "__main__":
    main()
