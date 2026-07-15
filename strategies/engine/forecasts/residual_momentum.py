"""
═══════════════════════════════════════════════════════════════════════════════
  RESIDUAL MOMENTUM — beta-stripped cross-sectional momentum (catalog D4)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* Blitz, Huij & Martens, *Residual Momentum*, J. Emp. Finance 2011 —
  https://doi.org/10.1016/j.jempfin.2011.01.003 (roughly doubles the Sharpe of
  total-return momentum; used by Robeco/AQR).
* Catalog D4 — the best-diversifying momentum variant vs the trend book:
  stripping market/BTC beta removes the shared trend component, and the
  crash-damping serves survival.

Formula (per peer group)
------------------------
    mkt_t     = equal-weight mean return of the group (market proxy)
    beta_i    = rolling cov(r_i, mkt) / var(mkt)      over ``beta_window``
    resid_i   = r_i − beta_i · mkt                    (idiosyncratic return)
    resmom_i  = sum(resid_i over ``lookback``) / std(resid_i)
    f_i       = clip( scalar · z_xs(resmom_i) , 0 , cap )   (long/flat)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import ResidualMomConfig


def _group_forecast(px: pd.DataFrame, cfg: ResidualMomConfig, cap: float) -> pd.DataFrame:
    rets = px.pct_change(fill_method=None)
    mkt = rets.mean(axis=1)                      # equal-weight group market proxy
    var_m = mkt.rolling(cfg.beta_window, min_periods=cfg.beta_window // 2).var()

    resid = {}
    for s in px.columns:
        cov = rets[s].rolling(cfg.beta_window, min_periods=cfg.beta_window // 2).cov(mkt)
        beta = (cov / var_m).clip(-4.0, 4.0)     # guard against unstable betas
        resid[s] = rets[s] - beta * mkt
    resid = pd.DataFrame(resid)

    cum = resid.rolling(cfg.lookback, min_periods=cfg.lookback // 2).sum()
    sd = resid.rolling(cfg.lookback, min_periods=cfg.lookback // 2).std().replace(0.0, np.nan)
    resmom = cum / sd

    cs_mean = resmom.mean(axis=1)
    cs_std = resmom.std(axis=1).replace(0.0, np.nan)
    z = resmom.sub(cs_mean, axis=0).div(cs_std, axis=0)
    return (cfg.scalar * z).clip(0.0, cap)       # long/flat


def residual_momentum_forecast(prices_by_symbol: dict[str, pd.Series],
                               cfg: ResidualMomConfig,
                               cap: float = 20.0,
                               groups: dict[str, str] | None = None
                               ) -> dict[str, pd.Series]:
    """Residual (idiosyncratic) cross-sectional momentum per symbol, long/flat."""
    symbols = [s for s, p in prices_by_symbol.items() if p is not None and len(p)]
    if len(symbols) < 2:
        return {s: pd.Series(0.0, index=prices_by_symbol[s].index)
                for s in prices_by_symbol}

    px = pd.concat({s: prices_by_symbol[s].astype(float) for s in symbols}, axis=1).sort_index()

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
        f = _group_forecast(px[members], cfg, cap)
        for s in members:
            out[s] = f[s]

    for s in prices_by_symbol:
        out.setdefault(s, pd.Series(0.0, index=prices_by_symbol[s].index
                                    if prices_by_symbol[s] is not None else px.index))
    return out
