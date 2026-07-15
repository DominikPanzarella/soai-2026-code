"""
═══════════════════════════════════════════════════════════════════════════════
  ACCELERATION (Carver Advanced Futures — 2nd derivative of the trend forecast)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* Carver, *Advanced Futures Trading Strategies* — Acceleration rule: the change
  in the (already scaled) EWMAC forecast. Captures *accelerating* trends earlier
  and exits decelerating ones faster; correlation ≤ ~0.76 to the parent EWMAC,
  so it is a near-free diversifier once EWMAC exists.

Formula
-------
    f_ewmac_t = scaled EWMAC forecast (avg|f| ≈ 10)
    accel_t   = f_ewmac_t − f_ewmac_{t−N}
    f_t       = clip(accel_t · scalar, −cap, cap)     (crypto: max(·,0))
"""

from __future__ import annotations

import pandas as pd

from ..config import EWMACConfig, AccelerationConfig
from .trend_ewmac import ewmac_forecast


def acceleration_forecast(prices: pd.Series, ewmac_cfg: EWMACConfig,
                          cfg: AccelerationConfig, vol_span: int = 32,
                          cap: float = 20.0) -> pd.Series:
    """Acceleration of the EWMAC forecast (±cap)."""
    f_ewmac = ewmac_forecast(prices, ewmac_cfg, vol_span, cap)
    accel = (f_ewmac - f_ewmac.shift(cfg.N)) * cfg.scalar
    return accel.clip(-cap, cap)
