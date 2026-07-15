"""
═══════════════════════════════════════════════════════════════════════════════
  MTF PULLBACK-CONTINUATION (v3 #1 — The Trend Following Bible)
═══════════════════════════════════════════════════════════════════════════════

With-trend re-entry: in a higher-timeframe uptrend, buy the working-timeframe
pullback (a genuinely new cell vs catalog breakouts and counter-trend fades).

    htf_up  = price > EWMA(price, htf_span)          (regime gate)
    fast    = EWMA(price, fast_span)
    dip     = (fast − price) / (σ%·price)            (>0 when pulled back below fast MA)
    f       = clip(scalar · max(dip,0) · htf_up , 0 , cap)   (long/flat)

Long-only by construction (buy dips in uptrends); decays to 0 as price resumes
above the fast MA or the HTF regime flips.
"""

from __future__ import annotations

import pandas as pd

from ..config import MTFPullbackConfig
from ..volatility import price_vol_units


def mtf_pullback_forecast(prices: pd.Series, cfg: MTFPullbackConfig,
                          cap: float = 20.0) -> pd.Series:
    prices = prices.astype(float)
    htf = prices.ewm(span=cfg.htf_span, min_periods=cfg.htf_span // 2).mean()
    fast = prices.ewm(span=cfg.fast_span, min_periods=2).mean()
    vpx = price_vol_units(prices, span=cfg.vol_span).replace(0.0, float("nan"))
    dip = ((fast - prices) / vpx).clip(lower=0.0)
    gate = (prices > htf).astype(float)
    return (dip * cfg.scalar * gate).clip(0.0, cap).fillna(0.0)
