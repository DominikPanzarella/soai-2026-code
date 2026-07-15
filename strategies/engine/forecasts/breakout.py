"""
═══════════════════════════════════════════════════════════════════════════════
  BREAKOUT — Donchian channel position (Carver breakout family)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* R. Carver, *Advanced Futures Trading Strategies* — breakout rules.

Formula (per window N)
----------------------
    hi_t   = max(price, N);  lo_t = min(price, N)
    mid_t  = (hi_t + lo_t) / 2
    pos_t  = (price_t - mid_t) / ((hi_t - lo_t) / 2)     (≈ [-1, +1])
    smooth = EWMA_{span=smooth_frac·N}(pos_t)
    fcast  = smooth · scalar                             (→ avg |f| ≈ 10)

Averaged across windows, capped ±20. Positive = breaking out to the upside.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import BreakoutConfig


def _breakout_window(prices: pd.Series, window: int, smooth_frac: float,
                     scalar: float) -> pd.Series:
    hi = prices.rolling(window, min_periods=max(2, window // 4)).max()
    lo = prices.rolling(window, min_periods=max(2, window // 4)).min()
    half_range = ((hi - lo) / 2.0).replace(0.0, np.nan)
    pos = (prices - (hi + lo) / 2.0) / half_range
    span = max(2, int(smooth_frac * window))
    smoothed = pos.ewm(span=span, min_periods=2).mean()
    return smoothed * scalar


def breakout_forecast(prices: pd.Series, cfg: BreakoutConfig,
                      cap: float = 20.0) -> pd.Series:
    """Combined breakout forecast (±cap) averaged across ``cfg.windows``."""
    prices = prices.astype(float)
    parts = [
        _breakout_window(prices, w, cfg.smooth_frac, cfg.scalar)
        for w in cfg.windows
    ]
    combined = pd.concat(parts, axis=1).mean(axis=1)
    return combined.clip(-cap, cap)
