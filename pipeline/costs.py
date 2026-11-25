"""Measured cost: read runs.jsonl and say what each stage took.

Latency and GPU minutes come straight from the run log. So does the list price: each line carries
the `cost_usd` worked out when the call was made (see pricing.py). A call whose price was not
known then is priced from pricing.json now, and shown as "n/a" if it is still unknown: an invented
price would be worse than a missing one.
"""
from __future__ import annotations

from collections import defaultdict

from . import pricing
from .core import STAGES, Ctx, read_jsonl

BEGIN, END = "<!-- costs:begin (written by `python -m pipeline costs --write`) -->", "<!-- costs:end -->"


def summarise(ctx: Ctx) -> tuple[str, dict]:
    runs = read_jsonl(ctx.runlog)
    rows: dict = defaultdict(lambda: {"calls": 0, "ok": 0, "errors": 0, "latency_s": 0.0, "gpu_minutes": 0.0, "usd": 0.0, "unpriced": 0})
    for r in runs:
        row = rows[(r.get("stage", "?"), r.get("provider", "?"), r.get("model", "?"))]
        row["calls"] += 1
        row["ok" if r.get("status") == "ok" else "errors"] += 1
        row["latency_s"] += r.get("latency_s") or 0.0
        row["gpu_minutes"] += r.get("gpu_minutes") or 0.0
        usd = r.get("cost_usd")                      # the price on the day of the call
        if usd is None:
            usd = pricing.cost_usd(r, ctx.prices)    # a line written before its price was known
        if usd is None:
            row["unpriced"] += 1
        else:
            row["usd"] += usd

    order = {s: i for i, s in enumerate(STAGES)}
    lines = ["| Stage | Provider | Model | Calls | Failed | Total latency (s) | Mean latency (s) | GPU minutes | List price (USD) |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    totals = {"calls": 0, "errors": 0, "latency_s": 0.0, "gpu_minutes": 0.0, "usd": 0.0, "unpriced": 0}
    for (stage, provider, model), row in sorted(rows.items(), key=lambda kv: (order.get(kv[0][0], 99), kv[0])):
        price = "n/a" if row["unpriced"] == row["calls"] else f"{row['usd']:.4f}" + (f" + {row['unpriced']} n/a" if row["unpriced"] else "")
        lines.append(f"| {stage} | {provider} | `{model}` | {row['calls']} | {row['errors']} | {row['latency_s']:.1f} | "
                     f"{row['latency_s'] / max(1, row['calls']):.1f} | {row['gpu_minutes']:.1f} | {price} |")
        for k in totals:
            totals[k] += row[k]
    price = "n/a" if not runs or totals["unpriced"] == totals["calls"] else f"{totals['usd']:.4f}" + (f" + {totals['unpriced']} n/a" if totals["unpriced"] else "")
    lines.append(f"| **Total** | | | {totals['calls']} | {totals['errors']} | {totals['latency_s']:.1f} | | {totals['gpu_minutes']:.1f} | {price} |")
    table = "\n".join(lines) + f"\n\nSource: `{ctx.runlog.relative_to(ctx.root).as_posix()}`, {len(runs)} model calls."
    paid = sum((r.get("cost_usd") or 0.0) for r in runs if (ctx.prices.get(r.get("model")) or {}).get("paid"))
    paid += over_allowance(ctx, runs)
    table += (" List price is what the calls would cost without the free tiers."
              + (f" Really paid: {paid:.4f} USD, for the calls to models that have no free tier. Everything else ran free." if paid
                 else " Nothing was paid: every call ran on a free tier."))
    if totals["unpriced"]:
        table += (f" {totals['unpriced']} call(s) are n/a and not in the sums: their price, or the usage it applies to, "
                  "was not known when they were logged.")
    return table, totals


def over_allowance(ctx: Ctx, runs: list[dict]) -> float:
    """What was paid on an account that has a free daily allowance and pays for the rest: the part of each day over the allowance."""
    total = 0.0
    for model, price in ctx.prices.items():
        tier = (price or {}).get("free_tier") or {}
        if not (tier.get("then_paid_from") and tier.get("usd_per_day")):
            continue
        days: dict[str, float] = {}
        for r in runs:
            if r.get("model") == model and r["ts"][:10] >= tier["then_paid_from"][:10]:  # this allowance is counted per UTC day
                days[r["ts"][:10]] = days.get(r["ts"][:10], 0.0) + (r.get("cost_usd") or 0.0)
        total += sum(max(0.0, used - tier["usd_per_day"]) for used in days.values())
    return total


def run(ctx: Ctx, write: bool = False) -> str:
    table, _ = summarise(ctx)
    ctx.say(table)
    if write:
        path = ctx.root / "COSTS.md"
        text = path.read_text(encoding="utf-8") if path.exists() else f"# Costs\n\n{BEGIN}\n{END}\n"
        if BEGIN not in text or END not in text:
            text += f"\n{BEGIN}\n{END}\n"
        head, rest = text.split(BEGIN, 1)
        path.write_text(head + BEGIN + "\n" + table + "\n" + END + rest.split(END, 1)[1], encoding="utf-8")
        ctx.say("  COSTS.md updated between the costs markers")
    return table
