"""
═══════════════════════════════════════════════════════════════════════════════
  COMBINE — forecast combination with FDM (Carver §8)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* R. Carver, *Systematic Trading* §8 — combining forecasts.

Formula
-------
    f_combined = clip( FDM · Σ_i (w_i · f_i) / Σ_i w_i , ±cap )

where f_i are individual rule forecasts (each already in the ±cap frame),
w_i are forecast weights, and FDM is the forecast diversification multiplier
that restores the combined forecast's scale after averaging correlated rules.
"""

from __future__ import annotations

import numpy as np


def combine_forecasts(forecasts: dict[str, float], weights: dict[str, float],
                      fdm: float, cap: float = 20.0, soft: bool = True) -> float:
    """
    Combine per-rule forecasts for a single asset into one ±cap forecast.

    Ignores rules whose forecast is NaN/None (warm-up) and renormalises the
    weights over the rules that are actually available. ``soft`` uses a tanh
    soft-cap (retains tail convexity) instead of a hard clip. Returns 0.0 if
    nothing is available yet.
    """
    num = 0.0
    wsum = 0.0
    for name, f in forecasts.items():
        w = weights.get(name, 0.0)
        if w <= 0.0 or f is None:
            continue
        f = float(f)
        if not np.isfinite(f):
            continue
        num += w * f
        wsum += w
    if wsum <= 0.0:
        return 0.0
    combined = fdm * (num / wsum)
    if soft:
        return float(cap * np.tanh(combined / cap))
    return float(np.clip(combined, -cap, cap))
