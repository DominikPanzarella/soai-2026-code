"""
═══════════════════════════════════════════════════════════════════════════════
  OVERLAYS — forecast conditioners (multipliers, not weighted forecasts)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* G1 vol-managed / crash-managed momentum: Barroso & Santa-Clara, *Momentum Has
  Its Moments*, JFE 2015 — https://doi.org/10.1016/j.jfineco.2014.11.003 ;
  Moreira & Muir, JF 2017.
* Soft-cap (H1): retain tail convexity instead of a hard ±20 clip — valuable in
  a terminal-return tournament.

These MULTIPLY existing forecasts; they never carry forecast weight themselves.
The vol-managed overlay is applied to directional trend/breakout/momentum
forecasts only (NOT reversion), before the cap, and is excluded from the
portfolio vol-target denominator to avoid double vol-scaling.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import VolManagedConfig
from .volatility import ewma_vol


def soft_cap(x, cap: float = 20.0):
    """tanh soft-cap: linear near 0, saturates smoothly toward ±cap."""
    if isinstance(x, pd.Series):
        return cap * np.tanh(x / cap)
    return float(cap * np.tanh(float(x) / cap))


def vol_managed_multiplier(prices: pd.Series, cfg: VolManagedConfig,
                           vol_span: int, bars_per_year: float) -> pd.Series:
    """
    Scale by target_vol / realised_vol, clamped. >1 in calm regimes, <1 in
    volatile ones — cuts the left tail, adds convexity. Returns a Series aligned
    to ``prices`` (1.0 where vol is undefined).
    """
    if not cfg.enabled:
        return pd.Series(1.0, index=prices.index)
    realised = ewma_vol(prices, span=vol_span) * np.sqrt(bars_per_year)
    mult = (cfg.target_vol_annual / realised.replace(0.0, np.nan))
    return mult.clip(cfg.clip_lo, cfg.clip_hi).fillna(1.0)


def last_vol_managed_mult(prices: pd.Series, cfg: VolManagedConfig,
                          vol_span: int, bars_per_year: float) -> float:
    """Scalar latest vol-managed multiplier (runtime convenience)."""
    s = vol_managed_multiplier(prices, cfg, vol_span, bars_per_year)
    v = float(s.iloc[-1]) if len(s) else 1.0
    return v if np.isfinite(v) and v > 0 else 1.0


def regime_gross_scalar(closes: dict, target_vol: float, lo: float, span: int,
                        bars_per_year: float) -> float:
    """Vol-conditioned gross multiplier: full risk when the book is calm, cut when
    market vol spikes. mult = clip(target_vol / realised_book_vol, lo, 1.0).

    NOTE (tested 2026-07): both a HELD-book vol-managed variant of this overlay and
    a hardened drawdown floor were measured against the full engine and neither
    reduced the deep multi-month drawdown — the −66% DD is driven by fast 3x-ETF
    moves that any realised-vol / drawdown signal detects only in arrears, so they
    sell low and drag the recovery. The deep DD is structural to vol_target=0.80 on
    a leveraged book; the only clean lever is lowering vol_target (symmetric)."""
    rets = pd.DataFrame({s: c.pct_change(fill_method=None) for s, c in closes.items()
                         if c is not None and len(c) > span}).mean(axis=1)
    if len(rets) < span:
        return 1.0
    v = float(rets.tail(span).std() * np.sqrt(bars_per_year))
    if not np.isfinite(v) or v <= 0:
        return 1.0
    return float(np.clip(target_vol / v, lo, 1.0))


def drawdown_scalar(dd: float, dd0: float, dmax: float, dmin: float) -> float:
    """Survival floor: 1.0 above -dd0, ramping to dmin at -dmax (kill-switch)."""
    if dd >= -dd0:
        return 1.0
    return max(dmin, 1.0 - (1.0 - dmin) * (-dd - dd0) / max(dmax - dd0, 1e-9))


def market_breadth_last(closes: dict, ma: int) -> float:
    """Fraction of instruments whose latest close is above their own MA(ma).
    Low breadth = risk-off regime (used to gate the tactical short leg)."""
    above, total = 0, 0
    for s, c in closes.items():
        if c is None or len(c) < ma:
            continue
        total += 1
        if float(c.iloc[-1]) > float(c.tail(ma).mean()):
            above += 1
    return (above / total) if total else 1.0
