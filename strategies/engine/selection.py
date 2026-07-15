"""
═══════════════════════════════════════════════════════════════════════════════
  SELECTION — dynamic instrument selection (trade only what is trending)
═══════════════════════════════════════════════════════════════════════════════

Runtime version of research/select_universe.py, used by the orchestrator to
restrict trading to the top-N trending, liquid, tradeable assets PER CLASS each
rebalance. Combined with full deployment (portfolio ``deploy_full``), this
concentrates the whole risk budget on the current winners — the change that
raised backtested terminal return from +27% (fixed 59) to +44% (dynamic).

Gate (vol band + long/flat eligibility) → rank (Efficiency Ratio + momentum) →
top-N per macro class. Computed from trailing closes only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import SelectionConfig


def _score(close: pd.Series, lookback: int, sigma_target: float, bpy: float):
    c = close.dropna().tail(lookback)
    if len(c) < max(20, lookback // 2):
        return None
    ret = c.pct_change(fill_method=None).dropna()
    if ret.std() == 0:
        return None
    tsmom = float(c.iloc[-1] / c.iloc[0] - 1.0)
    denom = float(c.diff().abs().sum())
    er = float(abs(c.iloc[-1] - c.iloc[0]) / denom) if denom else 0.0
    vol = float(ret.std() * np.sqrt(bpy))
    return tsmom, er, vol


def select_symbols(closes: dict, macro: dict, cfg: SelectionConfig,
                   sigma_target: float, bpy_map: dict) -> list[str]:
    """Return the selected symbols (top-N per macro class) to trade this rebalance."""
    if not cfg.enabled:
        return list(closes.keys())
    metrics = {}
    for s, c in closes.items():
        m = _score(c, cfg.lookback, sigma_target, bpy_map.get(s, 252.0))
        if m is not None:
            metrics[s] = m
    if not metrics:
        return list(closes.keys())

    picks: list[str] = []
    classes = set(macro.get(s, "other") for s in metrics)
    lo, hi = cfg.vol_band_lo * sigma_target, cfg.vol_band_hi * sigma_target
    for cls in classes:
        rows = {s: metrics[s] for s in metrics if macro.get(s, "other") == cls}
        # gate: tradeable vol band + long/flat eligibility (positive trailing trend)
        elig = {s: v for s, v in rows.items() if lo <= v[2] <= hi and v[0] > 0}
        if not elig:
            continue
        er = pd.Series({s: v[1] for s, v in elig.items()})
        mom = pd.Series({s: v[0] for s, v in elig.items()})
        def z(x):
            sd = x.std()
            return (x - x.mean()) / sd if sd and sd > 0 else x * 0.0
        score = 0.5 * z(er) + 0.5 * z(mom)
        n = cfg.nmax_crypto if cls == "crypto" else cfg.nmax_equity
        picks += list(score.sort_values(ascending=False).head(n).index)
    return picks or list(closes.keys())
