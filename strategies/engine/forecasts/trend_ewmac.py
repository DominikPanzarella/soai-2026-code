"""
═══════════════════════════════════════════════════════════════════════════════
  TREND — EWMAC crossover (Carver's core trend rule)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* R. Carver, *Systematic Trading* §7; *Advanced Futures* Ch. on EWMAC.

Formula (per fast/slow pair)
----------------------------
    raw_t   = EWMA_fast(price)_t - EWMA_slow(price)_t          (price-diff space)
    vol_t   = σ%_t · price_t                                   (price units)
    fcast_t = raw_t / vol_t · scalar                           (→ avg |f| ≈ 10)

The rule averages several fast/slow pairs (each with its own Carver forecast
scalar), then caps at ±20. Positive → uptrend (long); negative → downtrend
(realised as cash at the portfolio layer for spot).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import EWMACConfig
from ..volatility import price_vol_units


def _ewmac_pair(prices: pd.Series, fast: int, slow: int, scalar: float,
                vol_span: int) -> pd.Series:
    """Scaled forecast for a single (fast, slow) crossover."""
    fast_ma = prices.ewm(span=fast, min_periods=2).mean()
    slow_ma = prices.ewm(span=slow, min_periods=2).mean()
    raw = fast_ma - slow_ma
    vol = price_vol_units(prices, span=vol_span).replace(0.0, np.nan)
    return (raw / vol) * scalar


def ewmac_forecast(prices: pd.Series, cfg: EWMACConfig, vol_span: int = 32,
                   cap: float = 20.0) -> pd.Series:
    """
    Combined EWMAC forecast (±cap) averaged across ``cfg.pairs``.

    Returns a Series aligned to ``prices``; caller takes ``.iloc[-1]`` at
    runtime. Robust to short/NaN warm-up (leading values are NaN).
    """
    prices = prices.astype(float)
    if len(cfg.pairs) != len(cfg.scalars):
        raise ValueError("EWMACConfig.pairs and .scalars must be parallel lists")

    parts = [
        _ewmac_pair(prices, fast, slow, scalar, vol_span)
        for (fast, slow), scalar in zip(cfg.pairs, cfg.scalars)
    ]
    combined = pd.concat(parts, axis=1).mean(axis=1)
    return combined.clip(-cap, cap)
