"""
═══════════════════════════════════════════════════════════════════════════════
  RESIDUAL MEAN-REVERSION (v3 #2 — beta-neutral short-term reversion)
═══════════════════════════════════════════════════════════════════════════════

Strip market/BTC beta (per asset-class group), then FADE the short-horizon
residual: the beta-neutral twin of residual momentum. Fires frequently across
the crypto/ETF universe; decorrelated from directional trend.

    mkt   = equal-weight group return;  beta = rollcov(r_i,mkt)/var(mkt)
    resid = r_i − beta·mkt
    s_i   = Σ resid over `lookback` / std(resid)
    f_i   = clip(−scalar · z_xs(s_i) , 0 , cap)   (long the beta-neutral laggards)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import ResidualMRConfig


def _group(px: pd.DataFrame, cfg: ResidualMRConfig, cap: float) -> pd.DataFrame:
    rets = px.pct_change(fill_method=None)
    mkt = rets.mean(axis=1)
    var_m = mkt.rolling(cfg.beta_window, min_periods=cfg.beta_window // 2).var()
    resid = {}
    for s in px.columns:
        cov = rets[s].rolling(cfg.beta_window, min_periods=cfg.beta_window // 2).cov(mkt)
        beta = (cov / var_m).clip(-4.0, 4.0)
        resid[s] = rets[s] - beta * mkt
    resid = pd.DataFrame(resid)
    cum = resid.rolling(cfg.lookback, min_periods=cfg.lookback // 2).sum()
    sd = resid.rolling(cfg.lookback, min_periods=cfg.lookback // 2).std().replace(0.0, np.nan)
    s = cum / sd
    z = s.sub(s.mean(axis=1), axis=0).div(s.std(axis=1).replace(0.0, np.nan), axis=0)
    return (-cfg.scalar * z).clip(0.0, cap)   # fade → long laggards, long/flat


def residual_mr_forecast(prices_by_symbol: dict[str, pd.Series], cfg: ResidualMRConfig,
                         cap: float = 20.0, groups: dict[str, str] | None = None
                         ) -> dict[str, pd.Series]:
    syms = [s for s, p in prices_by_symbol.items() if p is not None and len(p)]
    if len(syms) < 2:
        return {s: pd.Series(0.0, index=prices_by_symbol[s].index) for s in prices_by_symbol}
    px = pd.concat({s: prices_by_symbol[s].astype(float) for s in syms}, axis=1).sort_index()
    clusters = {"__all__": syms} if groups is None else {}
    if groups is not None:
        for s in syms:
            clusters.setdefault(groups.get(s, "__o__"), []).append(s)
    out = {}
    for members in clusters.values():
        if len(members) < 2:
            for s in members: out[s] = pd.Series(0.0, index=px.index)
            continue
        f = _group(px[members], cfg, cap)
        for s in members: out[s] = f[s]
    for s in prices_by_symbol:
        out.setdefault(s, pd.Series(0.0, index=px.index))
    return out
