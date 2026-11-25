"""E28: do his clothes stay the same from shot to shot when their colours are written down?

    python experiments/e28_clothes.py

A reviewer of the cut of 26 Nov, 01:13 (commit 531e84a) saw that the young man's jacket, trousers,
shoes and backpack changed from shot to shot. The character description named no colour, and three
shots were drawn without the reference picture (E24). On 26 Nov the description was given colours
(charcoal grey jacket, olive green trousers, dark blue plastic sandals, olive green canvas backpack)
and every shot with him or his backpack was drawn again, from the words alone.

This script asks one model the same questions about the picture picked for each of those shots,
before and after: the colour of his jacket, of his trousers and of the backpack, and what he wears
on his feet. Every call goes through the pipeline's provider code, so each attempt is a line in
runs.jsonl with stage "experiment". Answers go to outputs/experiments/E28/results.json. A picture
that has an answer is not asked about again.
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import keyframes, providers  # noqa: E402
from pipeline.core import PipelineError, make_ctx, read_jsonl  # noqa: E402

MODEL = "claude-opus-5-5"
BEFORE = "531e84a"                                   # the commit of the cut the reviewer looked at
SHOTS = ["s01", "s03", "s04", "s06", "s07", "s08", "s09"]   # every shot with the young man or with his backpack
WANTED = {"jacket": "charcoal grey", "trousers": "olive green", "footwear": "plastic sandals", "backpack": "olive green"}
COLOURS = ["black", "charcoal grey", "grey", "navy blue", "blue", "olive green", "sage green", "green", "brown", "tan", "cream", "white",
           "other", "not in the picture"]
QUESTION = ("This picture is one frame of a short painted film. Its main character is a young man with a backpack. In some frames only "
            "his backpack is in the picture, and in one frame he is older and the backpack stands beside him.\n"
            "Look at the man the backpack belongs to (when two young men stand together: the one who carries it) and at the backpack. "
            "Give the colour of his jacket, the colour of his trousers, what he wears on his feet, and the colour of the backpack. "
            "Choose the nearest word from each list. Answer \"not in the picture\" for a thing that cannot be seen.")
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["jacket", "trousers", "footwear", "backpack", "notes"],
    "properties": {"jacket": {"type": "string", "enum": COLOURS}, "trousers": {"type": "string", "enum": COLOURS},
                   "footwear": {"type": "string", "enum": ["plastic sandals", "leather sandals", "closed shoes", "boots", "bare feet", "not in the picture"]},
                   "backpack": {"type": "string", "enum": COLOURS}, "notes": {"type": "string"}},
}


def picked(index: dict) -> dict:
    return {sid: index[sid]["file"] for sid in SHOTS if index.get(sid, {}).get("file")}


def main() -> None:
    ctx = make_ctx(root=ROOT)
    out = ctx.out / "experiments" / "E28" / "results.json"
    results = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    before = json.loads(subprocess.run(["git", "show", f"{BEFORE}:outputs/keyframes/index.json"], cwd=ROOT, capture_output=True, text=True,
                                       encoding="utf-8", check=True).stdout)
    after = json.loads((ctx.out / "keyframes" / "index.json").read_text(encoding="utf-8"))
    groups = {"before": picked(before), "after": picked(after)}
    for group, files in groups.items():
        for sid, name in files.items():
            key = f"{group}:{sid}"
            if results.get(key, {}).get("file") == name:
                continue
            picture = ctx.out / "keyframes" / name
            if not picture.exists():
                print(f"{key}: {name} is not on disk")
                continue
            seen = len(read_jsonl(ctx.runlog))
            try:
                answer, _ = providers.text(ctx, "experiment", f"E28_{group}_{sid}", QUESTION, kind="measure_clothes", schema=SCHEMA, model=MODEL,
                                           parts=[("image/jpeg", keyframes.small_jpeg(ctx, picture, side=768))])
            except PipelineError as e:
                print(f"{key}: failed, {e}")
                continue
            line = read_jsonl(ctx.runlog)[seen:][-1]
            results[key] = {"group": group, "shot": sid, "file": name, **json.loads(answer), "cost_usd": line["cost_usd"]}
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    summary = {}
    for group in groups:
        rows = [r for r in results.values() if r["group"] == group and r["shot"] != "s09" or (r["group"] == group and r["shot"] == "s09")]
        table = {}
        for thing, wanted in WANTED.items():
            # the man of the last shot is seven years older and dressed differently on purpose: only his backpack counts there
            seen_in = [r for r in rows if r[thing] != "not in the picture" and (thing == "backpack" or r["shot"] != "s09")]
            table[thing] = {"shots_where_seen": len(seen_in), "as_described": sum(r[thing] == wanted for r in seen_in),
                            "different_answers": dict(Counter(r[thing] for r in seen_in))}
        summary[group] = table
        print(f"\n{group}")
        for r in rows:
            print(f"  {r['shot']}  jacket {r['jacket']:<18} trousers {r['trousers']:<18} feet {r['footwear']:<18} backpack {r['backpack']:<14} {r['notes'][:70]}")
        for thing, t in table.items():
            print(f"  {thing:<9} as described in {t['as_described']} of {t['shots_where_seen']} shots where it is seen. Answers: {t['different_answers']}")
    spent = sum(r.get("cost_usd") or 0 for r in results.values())
    (out.parent / "summary.json").write_text(json.dumps({"wanted": WANTED, "before_commit": BEFORE, "summary": summary, "list_price_usd": round(spent, 4)},
                                                        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nlist price {spent:.4f} USD")


if __name__ == "__main__":
    main()
