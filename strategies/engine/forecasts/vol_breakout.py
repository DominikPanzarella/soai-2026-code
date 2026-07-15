"""
═══════════════════════════════════════════════════════════════════════════════
  VOLATILITY BREAKOUT — Keltner-style vol-channel breakout (volatility family)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* Keltner / Bookstaber volatility channel; Larry Williams volatility breakout.
  A "volatility" family rule: position = distance of price from its EMA measured
  in *realized-volatility units* (not min/max channel like Donchian). Expands the
  trend/momentum/volatility exposure the book targets.

Formula
-------
    mid   = EWMA(close, band_span)
    rv    = σ%_t · price_t                (realized vol in price units — the "ATR")
    f     = clip( scalar · (close − mid) / (k · rv) , −cap, cap )

Positive when price breaks out above its vol band; negative below (short leg used
on shortable equities in risk-off; crypto floors at 0 in the portfolio layer).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import VolBreakoutConfig
from ..volatility import price_vol_units


def vol_breakout_forecast(prices: pd.Series, cfg: VolBreakoutConfig,
                          cap: float = 20.0) -> pd.Series:
    prices = prices.astype(float)
    mid = prices.ewm(span=cfg.band_span, min_periods=2).mean()
    rv = price_vol_units(prices, span=cfg.vol_span).replace(0.0, np.nan)
    f = cfg.scalar * (prices - mid) / (cfg.k * rv)
    return f.clip(-cap, cap).fillna(0.0)
