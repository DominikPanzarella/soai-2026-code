"""
═══════════════════════════════════════════════════════════════════════════════
  KAMA — Kaufman Adaptive Moving Average slope (v3 #6, Kaufman TSaM)
═══════════════════════════════════════════════════════════════════════════════

Adaptive trend: the MA speeds up in efficient (trending) markets and slows in
noise, via the efficiency ratio. Slope of KAMA → trend forecast. Decorrelated
from EWMAC (adapts by ER, not fixed span).

    ER   = |P_t − P_{t−n}| / Σ|ΔP| over n
    SC   = [ER·(2/(fast+1) − 2/(slow+1)) + 2/(slow+1)]²
    KAMA = KAMA_{t−1} + SC·(P_t − KAMA_{t−1})
    f    = clip(scalar · (KAMA_t − KAMA_{t−1}) / (σ%·price) , −cap, cap)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import KAMAConfig
from ..volatility import price_vol_units


def _kama(prices: np.ndarray, n: int, fast: int, slow: int) -> np.ndarray:
    fast_sc, slow_sc = 2.0 / (fast + 1), 2.0 / (slow + 1)
    kama = np.full(len(prices), np.nan)
    change = np.abs(prices - np.concatenate([np.full(n, np.nan), prices[:-n]]))
    vol = pd.Series(np.abs(np.diff(prices, prepend=prices[0]))).rolling(n).sum().values
    kama[n] = prices[n]
    for t in range(n + 1, len(prices)):
        er = change[t] / vol[t] if vol[t] and vol[t] > 0 else 0.0
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        prev = kama[t - 1] if np.isfinite(kama[t - 1]) else prices[t - 1]
        kama[t] = prev + sc * (prices[t] - prev)
    return kama


def kama_forecast(prices: pd.Series, cfg: KAMAConfig, cap: float = 20.0) -> pd.Series:
    prices = prices.astype(float)
    k = pd.Series(_kama(prices.values, cfg.er_window, cfg.fast, cfg.slow), index=prices.index)
    slope = k.diff()
    vpx = price_vol_units(prices, span=cfg.vol_span).replace(0.0, np.nan)
    return (cfg.scalar * slope / vpx).clip(-cap, cap).fillna(0.0)
