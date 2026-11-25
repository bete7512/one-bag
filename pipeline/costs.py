"""Measured cost: read runs.jsonl and say what each stage took.

Latency and GPU minutes come straight from the run log. The list-price column uses pricing.json.
A price that has not been filled in and checked is shown as "n/a": an invented price would be
worse than a missing one.
"""
from __future__ import annotations

import json
from collections import defaultdict

from .core import STAGES, Ctx, read_jsonl

BEGIN, END = "<!-- costs:begin (written by `python -m pipeline costs --write`) -->", "<!-- costs:end -->"


def list_price(run: dict, prices: dict) -> float | None:
    """List-price equivalent of one call in USD, or None when its price is unknown."""
    key = "kaggle_gpu" if run.get("provider") == "kaggle" else run.get("model")
    p = prices.get(key)
    if not p:
        return None
    params, unit = run.get("params", {}), p.get("unit")
    try:
        if unit == "per_image":
            return float(p["usd"])
        if unit == "per_megapixel":
            return float(p["usd"]) * float(params.get("megapixels", 0))
        if unit == "per_1k_chars":
            return float(p["usd"]) * float(params.get("chars", 0)) / 1000
        if unit == "per_gpu_minute":
            return float(p["usd"]) * float(run.get("gpu_minutes", 0))
        if unit == "per_1m_tokens":
            usage = run.get("usage") or {}
            return (float(p["usd_in"]) * (usage.get("input_tokens") or 0) + float(p["usd_out"]) * (usage.get("output_tokens") or 0)) / 1e6
    except (KeyError, TypeError, ValueError):
        return None
    return None


def summarise(ctx: Ctx) -> tuple[str, dict]:
    runs = read_jsonl(ctx.runlog)
    pricing_path = ctx.root / "pricing.json"
    prices = json.loads(pricing_path.read_text(encoding="utf-8")).get("models", {}) if pricing_path.exists() else {}
    rows: dict = defaultdict(lambda: {"calls": 0, "ok": 0, "errors": 0, "latency_s": 0.0, "gpu_minutes": 0.0, "usd": 0.0, "unpriced": 0})
    for r in runs:
        row = rows[(r.get("stage", "?"), r.get("provider", "?"), r.get("model", "?"))]
        row["calls"] += 1
        row["ok" if r.get("status") == "ok" else "errors"] += 1
        row["latency_s"] += r.get("latency_s") or 0.0
        row["gpu_minutes"] += r.get("gpu_minutes") or 0.0
        usd = list_price(r, prices) if r.get("status") == "ok" else 0.0
        if usd is None:
            row["unpriced"] += 1
        else:
            row["usd"] += usd

    order = {s: i for i, s in enumerate(STAGES)}
    lines = ["| Stage | Provider | Model | Calls | Failed | Total latency (s) | Mean latency (s) | GPU minutes | List price (USD) |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    totals = {"calls": 0, "errors": 0, "latency_s": 0.0, "gpu_minutes": 0.0, "usd": 0.0, "unpriced": 0}
    for (stage, provider, model), row in sorted(rows.items(), key=lambda kv: (order.get(kv[0][0], 99), kv[0])):
        price = "n/a" if row["unpriced"] else f"{row['usd']:.4f}"
        lines.append(f"| {stage} | {provider} | `{model}` | {row['calls']} | {row['errors']} | {row['latency_s']:.1f} | "
                     f"{row['latency_s'] / max(1, row['calls']):.1f} | {row['gpu_minutes']:.1f} | {price} |")
        for k in totals:
            totals[k] += row[k]
    price = "n/a" if totals["unpriced"] or not runs else f"{totals['usd']:.4f}"
    lines.append(f"| **Total** | | | {totals['calls']} | {totals['errors']} | {totals['latency_s']:.1f} | | {totals['gpu_minutes']:.1f} | {price} |")
    table = "\n".join(lines) + f"\n\nSource: `{ctx.runlog.relative_to(ctx.root).as_posix()}`, {len(runs)} model calls."
    if totals["unpriced"]:
        table += f" {totals['unpriced']} call(s) have no checked price in `pricing.json`, so their list price is n/a."
    return table, totals


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
