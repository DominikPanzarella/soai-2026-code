"""
═══════════════════════════════════════════════════════════════════════════════
  CONVEX — upside sleeve for the terminal-return tournament
═══════════════════════════════════════════════════════════════════════════════

Why this exists
---------------
The competition scores a single number — Terminal Return over one month, one
winner. A well-diversified, vol-targeted core maximises risk-adjusted return
(survival) but, on its own, rarely wins a short winner-takes-most tournament,
which rewards convex upside. This sleeve carves out ``fraction`` of capital and
concentrates it in the strongest momentum name(s) *when the regime is up*, and
sits in cash otherwise — a cheap, rules-based call option on a hot streak.

    momentum_i = price_i,t / price_i,{t-L} - 1
    winners    = top_n symbols by momentum with momentum > 0
    weight_i   = fraction / len(winners)      (equal split; cash if none)

Kept deliberately simple and long/flat — no leverage on spot, and the whole
point is a robust, non-fragile upside tilt, not an over-fit bet.
"""

from __future__ import annotations

import pandas as pd

from .config import ConvexConfig


def convex_weights(closes: dict[str, pd.Series], cfg: ConvexConfig) -> dict[str, float]:
    """
    Return convex-sleeve target weights (summing to ≤ ``cfg.fraction``).

    Empty dict when disabled, when no series is long enough, or when no name
    has positive momentum (→ the sleeve holds cash).
    """
    if not cfg.enabled or cfg.fraction <= 0.0 or not closes:
        return {}

    momentum: dict[str, float] = {}
    for sym, c in closes.items():
        if c is None or len(c) <= cfg.momentum_lookback:
            continue
        past = float(c.iloc[-cfg.momentum_lookback - 1])
        if past > 0:
            momentum[sym] = float(c.iloc[-1]) / past - 1.0

    winners = sorted((s for s, m in momentum.items() if m > 0.0),
                     key=lambda s: momentum[s], reverse=True)[:cfg.top_n]
    if not winners:
        return {}  # risk-off → cash

    w = cfg.fraction / len(winners)
    return {s: w for s in winners}
