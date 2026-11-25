"""E24: does the reference picture decide the layout of a shot?

    python experiments/e24_reference_layout.py

Three shots (the bus seat, Lamberet, the queue) were drawn twice on 25 Nov with the same words and
seeds, two candidates each: once from the words alone, once with the reference picture of the young
man, which shows one figure standing, seen from behind. This script asks one model the same
questions about each of the twelve pictures: how much of the picture's height the young man takes,
whether he stands or sits, and whether he is in the middle third of the width. Every call goes
through the pipeline's provider code, so each attempt is a line in runs.jsonl with stage
"experiment". Answers go to outputs/experiments/E24/results.json. A picture that has an answer is
not asked about again.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import keyframes, providers  # noqa: E402
from pipeline.core import PipelineError, make_ctx, read_jsonl  # noqa: E402

MODEL = "claude-opus-5-5"
PICTURES = {  # original file -> how it was drawn
    "words alone": ["s03_c1__ed8b4c5f2ddafa61", "s03_c2__5503fd35e7a2b365", "s04_c1__728582a10db91f43", "s04_c2__c0df8f76482ed588",
                    "s08_c1__302a3847589a49dd", "s08_c2__06339420ed15e4e3"],
    "with the reference": ["s03_c1__b2570f1e5ca5bd08", "s03_c2__e97240232b5b9d38", "s04_c1__cb7bae72cb46ce16", "s04_c2__692740e3f9ca7e11",
                           "s08_c1__51505b526b964995", "s08_c2__040f903fef9e297a"],
}
QUESTION = ("This picture is one frame of a short film. Its main character is a young man who carries a backpack.\n"
            "Find him. Say how much of the picture's height he takes, from the top of his head to the lowest part of him that is "
            "in the frame, as a share between 0 and 1. Say whether he stands or sits. Say whether the middle of his body is in the "
            "middle third of the picture's width. Say whether his face can be seen, even from the side. If he is not in the picture, "
            "give a share of 0.")
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["height_share", "posture", "in_middle_third", "face_seen", "notes"],
    "properties": {"height_share": {"type": "number"}, "posture": {"type": "string", "enum": ["stands", "sits", "not in the picture"]},
                   "in_middle_third": {"type": "boolean"}, "face_seen": {"type": "boolean"}, "notes": {"type": "string"}},
}
TALL = 0.5  # a figure that takes half of the height or more leads the picture


def main() -> None:
    ctx = make_ctx(root=ROOT)
    out = ctx.out / "experiments" / "E24" / "results.json"
    results = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for group, names in PICTURES.items():
        for name in names:
            if name in results:
                continue
            picture = ctx.out / "keyframes" / "original" / f"{name}.jpg"
            seen = len(read_jsonl(ctx.runlog))
            try:
                answer, _ = providers.text(ctx, "experiment", f"E24_{name[:6]}", QUESTION, kind="measure_figure", schema=SCHEMA, model=MODEL,
                                           parts=[("image/jpeg", keyframes.small_jpeg(ctx, picture, side=768))])
            except PipelineError as e:
                print(f"{name}: failed, {e}")
                continue
            line = read_jsonl(ctx.runlog)[seen:][-1]
            results[name] = {"drawn": group, "shot": name.split("_")[0], **json.loads(answer), "latency_s": line["latency_s"], "cost_usd": line["cost_usd"]}
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
            row = results[name]
            print(f"{name[:6]} {group:<19} height {row['height_share']:.2f} {row['posture']:<7} middle {row['in_middle_third']!s:<5} "
                  f"face {row['face_seen']!s:<5} {row['notes'][:90]}")

    print("\nsummary")
    for group in PICTURES:
        rows = [r for r in results.values() if r["drawn"] == group]
        leads = sum(r["posture"] == "stands" and r["in_middle_third"] and r["height_share"] >= TALL for r in rows)
        print(f"  {group:<19} {len(rows)} pictures | he stands in the middle and takes half the height or more: {leads} | "
              f"mean share of the height: {sum(r['height_share'] for r in rows) / max(1, len(rows)):.2f} | sits: {sum(r['posture'] == 'sits' for r in rows)} | "
              f"face seen: {sum(r['face_seen'] for r in rows)} | list price {sum(r['cost_usd'] or 0 for r in rows):.4f} USD")


if __name__ == "__main__":
    main()
