"""
═══════════════════════════════════════════════════════════════════════════════
  INTERMARKET DIVERGENCE (v3 #4 — Katsanos; relative-price catch-up)
═══════════════════════════════════════════════════════════════════════════════

Fade the divergence of an asset's relative price vs a benchmark (BTC for crypto,
SPY for equities): when an asset has stretched BELOW its usual ratio to the
benchmark, expect catch-up. Cross-sectional MR family, decorrelated from trend.

    ratio_i = price_i / price_benchmark
    z_i     = (ratio_i − EWMA(ratio_i, span)) / rolling_std
    f_i     = clip(−scalar · z_i , 0 , cap)     (long the laggard; long/flat)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import IntermarketDivConfig


def intermarket_div_forecast(prices_by_symbol: dict[str, pd.Series], cfg: IntermarketDivConfig,
                             cap: float = 20.0, groups: dict[str, str] | None = None,
                             is_crypto: dict[str, bool] | None = None
                             ) -> dict[str, pd.Series]:
    out = {s: pd.Series(0.0, index=prices_by_symbol[s].index)
           for s in prices_by_symbol if prices_by_symbol[s] is not None}
    syms = [s for s in out]
    if not syms:
        return out
    px = pd.concat({s: prices_by_symbol[s].astype(float) for s in syms}, axis=1).sort_index()

    def _bench(sym):
        cr = is_crypto.get(sym, False) if is_crypto else False
        return cfg.crypto_benchmark if cr else cfg.equity_benchmark

    for s in syms:
        b = _bench(s)
        if b not in px.columns or s == b:
            continue
        ratio = (px[s] / px[b]).replace([np.inf, -np.inf], np.nan)
        mean = ratio.ewm(span=cfg.span, min_periods=cfg.span // 2).mean()
        sd = ratio.rolling(cfg.span, min_periods=cfg.span // 2).std().replace(0.0, np.nan)
        z = (ratio - mean) / sd
        out[s] = (-cfg.scalar * z).clip(0.0, cap).reindex(out[s].index).fillna(0.0)
    return out
