"""List prices: what one model call would cost without the free tier.

Every call in this project ran on a free tier, so nothing was paid. The brief still asks what the
same work costs at list price, per call, so each line of runs.jsonl carries `cost_usd`. Prices live
in pricing.json. Each one is copied from the provider's own pricing page with the date it was read.
When a price, or the usage it applies to, is not known, the cost is None: a missing number is
better than an invented one.

Units in pricing.json:

* per_1m_tokens     usd_in, usd_out. Output tokens include the model's thinking tokens.
* per_audio_second  usd_out per second of generated audio, plus usd_in per 1M input tokens when
                    the provider reports them.
* per_512_tile      usd_out per 512x512 tile of the generated image, plus usd_in per reference
                    image (each is sent smaller than one tile) and usd_step per step.
* per_gpu_minute    usd per minute, times the number of GPUs the job ran on.
"""
from __future__ import annotations

import json
import math
from pathlib import Path


def load(root: Path) -> dict:
    path = Path(root) / "pricing.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("models", {})


def tiles(width: float, height: float) -> int:
    """512x512 tiles needed to cover an image."""
    return math.ceil(width / 512) * math.ceil(height / 512)


def cost_usd(run: dict, prices: dict) -> float | None:
    """List-price equivalent of one logged call, or None when it cannot be worked out."""
    price = prices.get("kaggle_gpu" if run.get("provider") == "kaggle" else run.get("model"))
    if not price:
        return None
    params, usage = run.get("params") or {}, run.get("usage") or {}
    try:
        unit = price["unit"]
        if unit == "per_1m_tokens":
            if usage.get("input_tokens") is None or usage.get("output_tokens") is None:
                return None
            spent_out = usage["output_tokens"] + (usage.get("thoughts_tokens") or 0)
            usd = (price["usd_in"] * usage["input_tokens"] + price["usd_out"] * spent_out) / 1e6
        elif unit == "per_audio_second":
            if run.get("audio_seconds") is None:
                return None
            usd = price["usd_out"] * run["audio_seconds"] + price.get("usd_in", 0.0) * (usage.get("input_tokens") or 0) / 1e6
        elif unit == "per_512_tile":
            if not params.get("width") or not params.get("height"):
                return None
            steps = params.get("steps") or price.get("default_steps") or 0
            usd = (price["usd_out"] * tiles(params["width"], params["height"]) + price.get("usd_in", 0.0) * (params.get("refs") or 0)
                   + price.get("usd_step", 0.0) * steps)
        elif unit == "per_gpu_minute":
            if run.get("gpu_minutes") is None:
                return None
            usd = price["usd"] * run["gpu_minutes"] * max(1, run.get("gpu_count") or 1)
        else:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return round(float(usd), 6)
