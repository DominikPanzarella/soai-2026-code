"""
═══════════════════════════════════════════════════════════════════════════════
  MAX LOTTERY — cross-sectional low-MAX premium (catalog F1)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* Bali, Cakici & Whitelaw, *Maxing Out*, JFE 2011 — https://doi.org/10.1016/j.jfineco.2010.08.014
* Grobys & Junttila 2021 (crypto MAX premium). Catalog F1 — a NEW orthogonal
  (lottery-demand) axis vs the trend/momentum book.

Formula (at each timestamp, within each peer group)
---------------------------------------------------
    MAX_i  = max single-bar return over ``lookback`` bars
    rank_i = cross-sectional rank(MAX_i) ∈ [0,1]   (1 = most lottery-like)
    f_i    = clip( scalar · (1 − 2·rank_i) , 0 , cap )   (long-only low-MAX)

Long the calm (low-MAX) names, avoid the lottery-like ones. Peer-grouped
(class-aware) so a crypto coin is compared to crypto, an ETF to ETFs.
"""

from __future__ import annotations

import pandas as pd

from ..config import MaxLotteryConfig


def max_lottery_forecast(prices_by_symbol: dict[str, pd.Series],
                         cfg: MaxLotteryConfig,
                         cap: float = 20.0,
                         groups: dict[str, str] | None = None
                         ) -> dict[str, pd.Series]:
    """Cross-sectional low-MAX (lottery) forecast per symbol, long/flat."""
    symbols = [s for s, p in prices_by_symbol.items() if p is not None and len(p)]
    if len(symbols) < 2:
        return {s: pd.Series(0.0, index=prices_by_symbol[s].index)
                for s in prices_by_symbol}

    px = pd.concat({s: prices_by_symbol[s].astype(float) for s in symbols}, axis=1).sort_index()
    rets = px.pct_change(fill_method=None)
    max_ret = rets.rolling(cfg.lookback, min_periods=max(3, cfg.lookback // 4)).max()

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
        rank = max_ret[members].rank(axis=1, pct=True)   # 1 = most lottery-like
        fcast = (cfg.scalar * (1.0 - 2.0 * rank)).clip(0.0, cap)
        for s in members:
            out[s] = fcast[s]

    for s in prices_by_symbol:
        out.setdefault(s, pd.Series(0.0, index=prices_by_symbol[s].index
                                    if prices_by_symbol[s] is not None else px.index))
    return out
