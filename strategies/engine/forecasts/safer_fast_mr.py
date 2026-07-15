"""
═══════════════════════════════════════════════════════════════════════════════
  SAFER FAST MEAN-REVERSION (Carver Advanced Futures — trend-gated fast MR)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* Carver, *Advanced Futures Trading Strategies* — "safer" fast mean-reversion:
  a fast reversion signal is only taken WITH the long-term trend and is
  attenuated when volatility is abnormally high (don't catch falling knives).
* Catalog (books) top terminal-return keeper.

Formula
-------
    dev_t   = price_t − EWMA(price, span)
    vol_t   = σ%_t · price_t
    raw_t   = −dev_t / vol_t · scalar          (contrarian, fast)
    trend_t = EWMA(price, fast_trend) − EWMA(price, slow_trend)   (regime)
    gate    = 1 if trend_t > 0 else 0          (only mean-revert with an uptrend)
    atten   = clip(vol_target / σ_ann , 0, 1)  (shrink in high-vol regimes)
    f_t     = clip(max(raw_t, 0) · gate · atten , 0 , cap)   (long/flat)

Distinct from the plain z-score reversion (which fades both ways, ungated):
this only buys dips inside an uptrend and stands aside in downtrends / vol spikes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import SaferFastMRConfig
from ..volatility import ewma_vol, price_vol_units


def safer_fast_mr_forecast(prices: pd.Series, cfg: SaferFastMRConfig,
                           vol_span: int = 32, bars_per_year: float = 8760.0,
                           cap: float = 20.0) -> pd.Series:
    """Trend-gated, vol-attenuated fast mean-reversion forecast in [0, cap]."""
    prices = prices.astype(float)
    mean = prices.ewm(span=cfg.span, min_periods=2).mean()
    vpx = price_vol_units(prices, span=cfg.vol_span).replace(0.0, np.nan)
    raw = -(prices - mean) / vpx * cfg.scalar

    trend = (prices.ewm(span=cfg.fast_trend, min_periods=2).mean()
             - prices.ewm(span=cfg.slow_trend, min_periods=2).mean())
    gate = (trend > 0).astype(float)

    ann = ewma_vol(prices, span=cfg.vol_span) * np.sqrt(bars_per_year)
    atten = (cfg.vol_target_annual / ann).clip(0.0, 1.0).fillna(0.0)

    f = (raw.clip(lower=0.0) * gate * atten)
    return f.clip(0.0, cap)
