"""
═══════════════════════════════════════════════════════════════════════════════
  VOLATILITY — EWMA percentage volatility (Carver baseline)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* R. Carver, *Systematic Trading* §9 — volatility standardisation.

Formula
-------
    r_t   = close_t / close_{t-1} - 1
    σ²_t  = EWMA_span(r_t²)                 (mean of squared returns ≈ variance)
    σ%_t  = sqrt(σ²_t)                      (per-bar volatility)
    σ_ann = σ%_t · sqrt(bars_per_year)      (annualised)

Used both to standardise raw forecasts (§7) and to size positions (§9).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ── per-bar volatility ───────────────────────────────────────────────────────
def ewma_vol(prices: pd.Series, span: int = 32) -> pd.Series:
    """
    EWMA per-bar percentage volatility from a close-price series.

    Returns a Series aligned to ``prices`` (first value is NaN → forward logic
    should guard for warm-up). Uses squared simple returns, EWMA-averaged.
    """
    returns = prices.astype(float).pct_change(fill_method=None)
    var = returns.pow(2).ewm(span=span, min_periods=max(2, span // 4)).mean()
    return np.sqrt(var)


def last_vol(prices: pd.Series, span: int = 32, floor: float = 0.0) -> float:
    """Scalar latest per-bar vol, floored, robust to NaN/short series."""
    vol = ewma_vol(prices, span=span)
    v = float(vol.iloc[-1]) if len(vol) and np.isfinite(vol.iloc[-1]) else np.nan
    if not np.isfinite(v) or v <= 0.0:
        return floor
    return max(v, floor)


def annualise(vol_per_bar: float, bars_per_year: float) -> float:
    """Scale a per-bar vol to an annualised figure."""
    return float(vol_per_bar) * np.sqrt(bars_per_year)


def price_vol_units(prices: pd.Series, span: int = 32) -> pd.Series:
    """
    Volatility in *price units* (σ% · price), used to standardise EWMAC raw
    signals which live in price-difference space (Carver's ``vol`` denominator).
    """
    return ewma_vol(prices, span=span) * prices.astype(float)
