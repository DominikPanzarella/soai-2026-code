"""
═══════════════════════════════════════════════════════════════════════════════
  LEAD-LAG CATCH-UP (v3 #3 — BTC leads altcoins; Guo et al.)
═══════════════════════════════════════════════════════════════════════════════

Slow-diffusion spillover: when the leader (BTC) moves up, alts that lagged tend
to catch up. Cross-sectional within the crypto group, long/flat, high shot-count
on 60M.

    lead_ret = leader return over `lookback`
    gap_i    = lead_ret − ret_i(lookback)      (laggards have gap > 0)
    f_i      = clip(scalar·(2·rank(gap_i)−1) , 0 , cap)  IF lead_ret > 0 else 0
"""

from __future__ import annotations

import pandas as pd

from ..config import LeadLagConfig


def leadlag_forecast(prices_by_symbol: dict[str, pd.Series], cfg: LeadLagConfig,
                     cap: float = 20.0, groups: dict[str, str] | None = None
                     ) -> dict[str, pd.Series]:
    syms = [s for s, p in prices_by_symbol.items() if p is not None and len(p)]
    out = {s: pd.Series(0.0, index=prices_by_symbol[s].index)
           for s in prices_by_symbol if prices_by_symbol[s] is not None}
    if cfg.leader not in syms or len(syms) < 2:
        return out
    px = pd.concat({s: prices_by_symbol[s].astype(float) for s in syms}, axis=1).sort_index()
    ret = px / px.shift(cfg.lookback) - 1.0
    lead = ret[cfg.leader]
    # restrict ranking to the leader's cluster (crypto) when groups given
    members = syms
    if groups is not None:
        gl = groups.get(cfg.leader)
        members = [s for s in syms if groups.get(s) == gl]
    gap = (-ret[members]).add(lead, axis=0)          # lead_ret − ret_i
    rank = gap.rank(axis=1, pct=True)
    f = (cfg.scalar * (2.0 * rank - 1.0)).clip(0.0, cap)
    f = f.where(lead > 0, 0.0)                        # only when leader is up
    for s in members:
        out[s] = f[s].reindex(out[s].index).fillna(0.0) if s in out else f[s]
    return out
