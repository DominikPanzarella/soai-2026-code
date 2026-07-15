"""
═══════════════════════════════════════════════════════════════════════════════
  MEAN-REVERSION — fast contrarian z-score (intraday chop harvester)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* Carver-style standardised deviation; contrarian sign.

Formula
-------
    mean_t = EWMA_span(price)_t
    dev_t  = price_t - mean_t
    vol_t  = σ%_t · price_t                      (price units)
    z_t    = dev_t / vol_t
    fcast  = -z_t · scalar                        (contrarian; → avg |f| ≈ 10)

Capped ±20. Stretched-up price → negative forecast (fade). Weighted lightly:
mean-reversion bleeds in strong trends, so it is a diversifier, not a core.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import MeanReversionConfig
from ..volatility import price_vol_units


def mean_reversion_forecast(prices: pd.Series, cfg: MeanReversionConfig,
                            cap: float = 20.0) -> pd.Series:
    """Contrarian z-score forecast (±cap)."""
    prices = prices.astype(float)
    mean = prices.ewm(span=cfg.span, min_periods=2).mean()
    vol = price_vol_units(prices, span=cfg.vol_span).replace(0.0, np.nan)
    z = (prices - mean) / vol
    fcast = -z * cfg.scalar
    return fcast.clip(-cap, cap)
