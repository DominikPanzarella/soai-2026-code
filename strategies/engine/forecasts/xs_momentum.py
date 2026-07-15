"""
═══════════════════════════════════════════════════════════════════════════════
  XS-MOMENTUM — cross-sectional momentum across the crypto basket
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* Jegadeesh & Titman (1993); crypto XS-momentum (e.g. SSRN cross-sectional
  crypto studies). Carver-style ±20 framing for combination.

Formula (at each timestamp t)
-----------------------------
    ret_i   = price_i,t / price_i,{t-L} - 1          (lookback return, L bars)
    demean  = ret_i - mean_j(ret_j)                  (cross-sectional demean)
    z_i     = demean_i / std_j(ret_j)                (cross-sectional z)
    fcast_i = z_i · scalar                            (→ ±cap)

Strongest names get the largest positive forecast (→ long); weakest get
negative (→ cash at the portfolio layer, since spot has no short leg). This is
the one rule that needs the whole basket, hence a dedicated signature.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import XSMomentumConfig


def xs_momentum_forecast(prices_by_symbol: dict[str, pd.Series],
                         cfg: XSMomentumConfig,
                         cap: float = 20.0,
                         groups: dict[str, str] | None = None
                         ) -> dict[str, pd.Series]:
    """
    Cross-sectional momentum forecast per symbol (±cap).

    Ranks lookback returns cross-sectionally. When ``groups`` (symbol →
    asset-class group) is given, the demean/standardise is done WITHIN each
    group (Carver class-aware relative momentum) — so a crypto name is scored
    against other crypto, an ETF against other ETFs. Needs ≥ 2 symbols in a
    group; singletons get a flat-zero forecast.
    """
    symbols = [s for s, p in prices_by_symbol.items() if p is not None and len(p)]
    if len(symbols) < 2:
        return {s: pd.Series(0.0, index=prices_by_symbol[s].index)
                for s in prices_by_symbol}

    px = pd.concat({s: prices_by_symbol[s].astype(float) for s in symbols}, axis=1).sort_index()
    rets = px / px.shift(cfg.lookback) - 1.0

    if groups is None:
        clusters = {"__all__": symbols}
    else:
        clusters = {}
        for s in symbols:
            clusters.setdefault(groups.get(s, "__other__"), []).append(s)

    out: dict[str, pd.Series] = {}
    for members in clusters.values():
        if len(members) < 2:
            for s in members:
                out[s] = pd.Series(0.0, index=px.index)
            continue
        sub = rets[members]
        cs_mean = sub.mean(axis=1)
        cs_std = sub.std(axis=1).replace(0.0, np.nan)
        z = sub.sub(cs_mean, axis=0).div(cs_std, axis=0)
        fcast = (z * cfg.scalar).clip(-cap, cap)
        for s in members:
            out[s] = fcast[s]

    for s in prices_by_symbol:
        out.setdefault(s, pd.Series(0.0, index=prices_by_symbol[s].index
                                    if prices_by_symbol[s] is not None else px.index))
    return out
