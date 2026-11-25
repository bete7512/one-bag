"""E17: does a stricter question, and then a stronger model, make the keyframe judge tell pictures apart?

    python experiments/e17_judges.py

It asks the pipeline's judge question about the twelve pictures made on 25 Nov (shots s02, s05, s07,
two candidates each, before and after the style sentence of E16), once with each model. Every call
goes through the pipeline's own provider code, so each attempt is a line in runs.jsonl with stage
"experiment". The answers and the measured border of each picture go to
outputs/experiments/E17/results.json. A model that has already answered for a picture is not asked again.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import keyframes, providers  # noqa: E402
from pipeline.core import PipelineError, make_ctx, read_jsonl  # noqa: E402

MODELS = ["gemini-3.5-flash-lite", "claude-opus-5-5"]
PICTURES = {  # original file -> which set it belongs to
    "before": ["s02_c1__799b4d69fc00d0d3", "s02_c2__a159c086c27e4a9a", "s05_c1__b95301d26bf04787",
               "s05_c2__b7e31ad4278e280e", "s07_c1__bce79789ee7ff8e7", "s07_c2__fdb81586439f308f"],
    "after": ["s02_c1__6bf9ef1c4e184475", "s02_c2__450997677924dc1b", "s05_c1__ab0f1e8a9f237762",
              "s05_c2__c9f718379c9f1605", "s07_c1__3d4e8b91359c48bc", "s07_c2__877d97a7765691e6"],
}


def main() -> None:
    ctx = make_ctx(root=ROOT)
    shots = {s["id"]: s for s in ctx.sb["shots"]}
    out = ctx.out / "experiments" / "E17" / "results.json"
    results = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for group, names in PICTURES.items():
        for name in names:
            picture = ctx.out / "keyframes" / "original" / f"{name}.jpg"
            sid = name.split("_")[0]
            row = results.setdefault(name, {"set": group, "shot": sid, "paper_sides": keyframes.paper_edges(ctx, picture), "judges": {}})
            prompt = keyframes.JUDGE_PROMPT.format(shot=shots[sid]["keyframe"]["prompt"], who="none", style=ctx.sb["style"]["block"])
            parts = [("image/jpeg", keyframes.small_jpeg(ctx, picture, side=768))]
            for model in MODELS:
                if model in row["judges"]:
                    continue
                seen = len(read_jsonl(ctx.runlog))
                try:
                    answer, _ = providers.text(ctx, "experiment", f"E17_{name[:6]}_{group}", prompt, kind="judge", parts=parts,
                                               json_mode=True, schema=keyframes.JUDGE_SCHEMA, temperature=0.0, model=model)
                except PipelineError as e:
                    print(f"{name} {model}: failed, {e}")
                    continue
                scores = keyframes.parse_scores(answer)
                line = read_jsonl(ctx.runlog)[seen:][-1]
                row["judges"][model] = {**scores, "total": keyframes.judge_total(scores, False), "latency_s": line["latency_s"],
                                        "cost_usd": line["cost_usd"], "attempts": len(read_jsonl(ctx.runlog)) - seen}
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"{name[:6]} {group:<6} {model:<22} total {row['judges'][model]['total']:<5} border {scores.get('border')!s:<5} "
                      f"{line['latency_s']:>5.1f}s  measured sides {row['paper_sides']}")

    print("\nsummary")
    bordered = [name for name, row in results.items() if row["paper_sides"] >= keyframes.BORDER_SIDES]
    for model in MODELS:
        got = [row["judges"][model] for row in results.values() if model in row["judges"]]
        flagged = sum(1 for name in bordered if results[name]["judges"].get(model, {}).get("border") is True)
        wrongly = sum(1 for name, row in results.items() if name not in bordered and row["judges"].get(model, {}).get("border") is True)
        print(f"  {model:<22} answered {len(got)} of {len(results)} | flagged {flagged} of the {len(bordered)} measured borders, and {wrongly} more | "
              f"{len({j['total'] for j in got})} different totals | mean {sum(j['latency_s'] for j in got) / max(1, len(got)):.1f}s | "
              f"list price {sum(j['cost_usd'] or 0 for j in got):.4f} USD")


if __name__ == "__main__":
    main()
