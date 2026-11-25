"""E19: does a three-pose character sheet put three copies of the character into the scene?

    python experiments/e19_reference.py

The five shots with the young man were drawn twice on 25 Nov, two candidates each. The only change
between the two sets is the reference picture sent with the prompt: first a character sheet with
three poses (front, side, back), then one figure seen from behind. This script asks one model the
same three questions about each of the twenty pictures: how many times the young man with the
backpack appears, whether a face of his is turned to the viewer, and whether the picture looks
painted or photographed. Every call goes through the pipeline's provider code, so each attempt is a
line in runs.jsonl with stage "experiment". Answers go to outputs/experiments/E19/results.json. A
picture that has an answer is not asked about again.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import keyframes, providers  # noqa: E402
from pipeline.core import PipelineError, make_ctx, read_jsonl  # noqa: E402

MODEL = "claude-opus-5-5"
PICTURES = {  # original file -> the reference it was drawn with
    "sheet of three poses": ["s01_c1__94b6a9fe37e14446", "s01_c2__20231c855a884c58", "s03_c1__da3fe41be9de9068", "s03_c2__b33f4baecd14e015",
                             "s04_c1__aaa66f93dd6f8110", "s04_c2__9b926646c6455889", "s06_c1__db4edebc9fa76144", "s06_c2__97a75521eab9415b",
                             "s08_c1__de08e0e97287b266", "s08_c2__3d46c81588c9e696"],
    "one back view": ["s01_c1__539e0090fd6742db", "s01_c2__d8374f29bdaeca74", "s03_c1__f19d8a90695f79a8", "s03_c2__7e088cb585c800a3",
                      "s04_c1__6870a32709a02922", "s04_c2__13083ecca2fad8b3", "s06_c1__329cbb4d69461290", "s06_c2__13d8852260818c3b",
                      "s08_c1__b3639bff24e44df3", "s08_c2__f117b7c941cf77eb"],
}
QUESTION = ("This picture is one frame of a short film. Its main character is a slim young man in a dark jacket who carries a backpack. "
            "He should be in the picture exactly once, and seen from behind.\n"
            "Count how many separate figures in the picture are this young man with a backpack, drawn again: same clothes, same build. "
            "Other people do not count. Then say whether the face of any of these figures is turned to the viewer, in front or three-quarter "
            "view, and whether the picture looks painted by hand or like a photograph.")
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["copies", "face_to_viewer", "looks", "notes"],
    "properties": {"copies": {"type": "integer"}, "face_to_viewer": {"type": "boolean"},
                   "looks": {"type": "string", "enum": ["painted", "photograph"]}, "notes": {"type": "string"}},
}


def main() -> None:
    ctx = make_ctx(root=ROOT)
    out = ctx.out / "experiments" / "E19" / "results.json"
    results = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for group, names in PICTURES.items():
        for name in names:
            if name in results:
                continue
            picture = ctx.out / "keyframes" / "original" / f"{name}.jpg"
            seen = len(read_jsonl(ctx.runlog))
            try:
                answer, _ = providers.text(ctx, "experiment", f"E19_{name[:6]}", QUESTION, kind="count_copies", schema=SCHEMA, model=MODEL,
                                           parts=[("image/jpeg", keyframes.small_jpeg(ctx, picture, side=768))])
            except PipelineError as e:
                print(f"{name}: failed, {e}")
                continue
            line = read_jsonl(ctx.runlog)[seen:][-1]
            results[name] = {"reference": group, "shot": name.split("_")[0], **json.loads(answer), "latency_s": line["latency_s"], "cost_usd": line["cost_usd"]}
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
            row = results[name]
            print(f"{name[:6]} {group:<21} copies {row['copies']} face to viewer {row['face_to_viewer']!s:<5} {row['looks']:<10} {row['notes'][:110]}")

    print("\nsummary")
    for group in PICTURES:
        rows = [r for r in results.values() if r["reference"] == group]
        print(f"  {group:<21} {len(rows)} pictures | more than one copy: {sum(r['copies'] > 1 for r in rows)} | no copy at all: {sum(r['copies'] == 0 for r in rows)} | "
              f"a face to the viewer: {sum(r['face_to_viewer'] for r in rows)} | looks like a photograph: {sum(r['looks'] == 'photograph' for r in rows)} | "
              f"list price {sum(r['cost_usd'] or 0 for r in rows):.4f} USD")


if __name__ == "__main__":
    main()
