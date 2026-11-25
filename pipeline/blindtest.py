"""Beyond the floor: a blind A/B preference test.

"Which looks better, the Wan clip or the pan over the still?" is only evidence when the people
answering do not know which is which. `pack` copies pairs of files under neutral names (X and Y,
shuffled per pair with a seed) and writes the key to a file you keep to yourself. `score` reads the
votes and reports how often each way won, with an exact two-sided sign test.

    python -m pipeline blindtest pack motion --labels kenburns,wan --a still1.mp4 --b wan1.mp4 --a still2.mp4 --b wan2.mp4
    python -m pipeline blindtest score motion --votes votes.csv
"""
from __future__ import annotations

import csv
import json
import random
import shutil
from math import comb

from .core import Ctx, PipelineError


def sign_test(wins: int, n: int) -> float:
    """Chance of a split at least this lopsided if people really had no preference (two-sided, exact)."""
    if n == 0:
        return 1.0
    observed = comb(n, wins)
    return min(1.0, sum(comb(n, k) for k in range(n + 1) if comb(n, k) <= observed) / 2 ** n)


def pack(ctx: Ctx, name: str, a_files: list, b_files: list, labels: list[str], seed: int) -> int:
    if not a_files or len(a_files) != len(b_files):
        raise PipelineError("give the same number of --a and --b files, at least one pair")
    out = ctx.out / "blindtest" / name
    out.mkdir(parents=True, exist_ok=True)
    rng, key = random.Random(seed), {}
    for i, (a, b) in enumerate(zip(a_files, b_files), start=1):
        for f in (a, b):
            if not f.exists():
                raise PipelineError(f"{f} does not exist")
        flip = rng.random() < 0.5
        x, y = (b, a) if flip else (a, b)
        shutil.copy2(x, out / f"pair{i:02d}_X{x.suffix}")
        shutil.copy2(y, out / f"pair{i:02d}_Y{y.suffix}")
        key[f"pair{i:02d}"] = {"X": labels[1] if flip else labels[0], "Y": labels[0] if flip else labels[1]}
    (out / "key.json").write_text(json.dumps({"labels": labels, "seed": seed, "pairs": key}, indent=1), encoding="utf-8")
    (out / "votes_template.csv").write_text("rater,pair,choice\n" + "".join(f"rater1,{p},\n" for p in key), encoding="utf-8")
    sheet = [f"# Which do you prefer? ({name})", "", "For each pair, watch X and Y and say which one you prefer: X or Y.",
             "There is no right answer. Please do not discuss it with other raters before answering.", "",
             "| Pair | Your choice (X or Y) |", "|---|---|"] + [f"| {p} | |" for p in key]
    (out / "rater_sheet.md").write_text("\n".join(sheet) + "\n", encoding="utf-8")
    ctx.say(f"  {len(key)} pair(s) in {out.relative_to(ctx.root)}. Share the pair files and rater_sheet.md. Keep key.json to yourself.")
    return 0


def score(ctx: Ctx, name: str, votes_path) -> int:
    out = ctx.out / "blindtest" / name
    if not (out / "key.json").exists():
        raise PipelineError(f"no blind test called {name}. Run `blindtest pack {name}` first.")
    if not votes_path or not votes_path.exists():
        raise PipelineError("give the votes with --votes file.csv (columns: rater,pair,choice)")
    key = json.loads((out / "key.json").read_text(encoding="utf-8"))
    first, second = key["labels"]
    tally, raters, per_pair = {first: 0, second: 0}, set(), {}
    with open(votes_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            choice, pair = (row.get("choice") or "").strip().upper(), (row.get("pair") or "").strip()
            if choice not in ("X", "Y") or pair not in key["pairs"]:
                continue
            winner = key["pairs"][pair][choice]
            tally[winner] += 1
            raters.add((row.get("rater") or "").strip())
            per_pair.setdefault(pair, {first: 0, second: 0})[winner] += 1
    n = tally[first] + tally[second]
    if n == 0:
        raise PipelineError("no usable votes in that file")
    p = sign_test(tally[first], n)
    lines = [f"# Blind test: {name}", "", f"{len(raters)} rater(s), {n} votes.", "",
             "| Way | Votes | Share |", "|---|---:|---:|",
             f"| {first} | {tally[first]} | {tally[first] / n:.0%} |", f"| {second} | {tally[second]} | {tally[second] / n:.0%} |", "",
             f"Exact two-sided sign test: p = {p:.3f}. " + ("A split this lopsided would be unusual if people had no preference."
                                                             if p < 0.05 else "A split like this is what chance alone often gives: no clear preference shown."),
             "", "| Pair | " + first + " | " + second + " |", "|---|---:|---:|"]
    lines += [f"| {pair} | {v[first]} | {v[second]} |" for pair, v in sorted(per_pair.items())]
    if len(raters) < 5:
        lines += ["", f"Only {len(raters)} rater(s): the brief asks for at least five before calling it a result."]
    (out / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ctx.say("\n".join(lines))
    return 0


def run(ctx: Ctx, args) -> int:
    labels = [part.strip() for part in args.labels.split(",")]
    if len(labels) != 2:
        raise PipelineError("--labels takes two names, for example kenburns,wan")
    if args.action == "pack":
        return pack(ctx, args.name, args.a, args.b, labels, args.seed)
    return score(ctx, args.name, args.votes)
