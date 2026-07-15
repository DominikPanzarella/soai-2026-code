"""
═══════════════════════════════════════════════════════════════════════════════
  BACKTEST DYNAMIC — does monthly instrument re-selection increase return?
═══════════════════════════════════════════════════════════════════════════════

Walk-forward test of the systematic universe selection (research/select_universe.py)
against the FIXED broad universe, on daily data. Each month we re-rank the
universe on the trailing window and trade ONLY the top-N per class (optionally
momentum/score-tilted), then compare terminal return vs the fixed book.

Goal: raise total return by concentrating on what is actually trending, instead
of diluting across a fixed 59-asset universe.

    python research/backtest_dynamic.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

import robustness as R
from strategies.engine.config import EngineConfig
from strategies.engine.instruments import (
    load_universe, handcraft_weights, groups_map, class_map, macro_class,
)

WINDOW = 90          # trailing days for selection metrics
STEP = 5             # rebalance cadence (≈ weekly)
NMAX = {"crypto": 4, "equity": 8, "commodity": 3}
BAND = (0.4, 6.0)    # allow high-vol leveraged ETFs into the selection
SIGMA_TARGET = 0.35
# NOTE: this vectorized twin is an EXPLORATORY SCREEN only. It disagrees with the real
# engine on selection dynamics (e.g. it wrongly favoured less-frequent reselect); the
# native Lumibot tearsheet (backtest_daily.py) is the GROUND TRUTH. Params below mirror
# the locked engine config so the screen is at least directionally aligned.
REGIME_TARGET = 0.30   # book-vol target for the regime gross scalar
REGIME_LO = 1.00       # regime scalar neutralised (matches locked config: no vol de-risk)
DD_FLOOR = (0.30, 0.50, 0.40)   # (dd0, dmax, mmin): catastrophic-only kill-switch (locked)


def _score_at(px: pd.DataFrame, cutoff: int, syms: list, macro: dict) -> dict:
    """Per-asset (score, eligible) using data up to `cutoff` (trailing WINDOW)."""
    w = px.iloc[max(0, cutoff - WINDOW):cutoff]
    out = {}
    for s in syms:
        c = w[s].dropna()
        if len(c) < WINDOW * 0.6:
            continue
        ret = np.log(c / c.shift(1)).dropna()
        if ret.std() == 0:
            continue
        tsmom = c.iloc[-1] / c.iloc[0] - 1.0
        er = abs(c.iloc[-1] - c.iloc[0]) / c.diff().abs().sum() if c.diff().abs().sum() else 0.0
        vol = ret.std() * np.sqrt(252)
        out[s] = dict(tsmom=tsmom, er=er, vol=vol)
    return out


def _select(scores: dict, macro: dict, nmax: dict) -> list:
    picks = []
    df = pd.DataFrame(scores).T
    if df.empty:
        return picks
    for cls in set(macro.get(s) for s in df.index):
        sub = df[[macro.get(s) == cls for s in df.index]].copy()
        # gate: tradeable vol band + long/flat eligibility
        sub = sub[(sub["vol"].between(BAND[0]*SIGMA_TARGET, BAND[1]*SIGMA_TARGET)) & (sub["tsmom"] > 0)]
        if sub.empty:
            continue
        zer = (sub["er"]-sub["er"].mean())/ (sub["er"].std() or 1)
        zmom = (sub["tsmom"]-sub["tsmom"].mean())/ (sub["tsmom"].std() or 1)
        sub["score"] = 0.5*zer + 0.5*zmom
        picks += list(sub.sort_values("score", ascending=False).head(nmax.get(cls, 6)).index)
    return picks


def run():
    cfg = EngineConfig()
    core = load_universe(roles=("core",))
    iw = handcraft_weights(core, cfg.macro_weights)
    groups, classes = groups_map(core), class_map(core)
    macro = {ins.symbol: macro_class(ins.asset_class) for ins in core}
    px, is_crypto = R.load_daily(core)
    syms = list(px.columns)

    tgt_fixed, idm = R.target_weights_frame(px, cfg, iw, groups, classes, is_crypto, True)
    budget = cfg.risk.gross_cap - cfg.risk.cash_buffer

    # walk-forward monthly selection mask + score-tilt
    mask = pd.DataFrame(0.0, index=px.index, columns=syms)
    tilt = pd.DataFrame(1.0, index=px.index, columns=syms)
    cutoffs = list(range(WINDOW, len(px), STEP))
    for i, cut in enumerate(cutoffs):
        sc = _score_at(px, cut, syms, macro)
        picks = _select(sc, macro, NMAX)
        end = cutoffs[i+1] if i+1 < len(cutoffs) else len(px)
        if picks:
            mask.iloc[cut:end, [syms.index(p) for p in picks]] = 1.0
            # momentum tilt: overweight higher-momentum picks (rank in [0.5,1.5])
            moms = pd.Series({p: sc[p]["tsmom"] for p in picks})
            r = moms.rank(pct=True)
            for p in picks:
                tilt.iloc[cut:end, syms.index(p)] = 0.5 + r[p]

    def _renorm(t, full=False):
        g = t.abs().sum(axis=1)
        if full:                              # scale to budget both ways (deploy fully)
            sc = (budget / g).replace([np.inf, -np.inf], 0.0).fillna(0.0)
        else:                                 # cap only (leave cash when under-deployed)
            sc = (budget / g).clip(upper=1.0).replace([np.inf, -np.inf], 0.0).fillna(0.0)
        return t.mul(sc, axis=0)

    tgt_dyn = _renorm(tgt_fixed * mask)
    tgt_dyn_tilt = _renorm(tgt_fixed * mask * tilt)

    # regime gross scalar (vol-conditioned): full risk when the book is calm,
    # cut when market vol spikes. mult = clip(target / realized_book_vol, LO, 1).
    mkt_ret = px.pct_change(fill_method=None).mean(axis=1)
    mkt_vol = mkt_ret.rolling(20).std() * np.sqrt(252)
    regime = (REGIME_TARGET / mkt_vol).clip(REGIME_LO, 1.0).fillna(1.0)

    dyn_full = _renorm(tgt_fixed * mask, full=True)
    dyn_regime = dyn_full.mul(regime, axis=0)

    buf, mt = cfg.execution.no_trade_buffer, cfg.execution.max_turnover_per_step
    variants = {
        "FIXED universe": (tgt_fixed, None),
        "DYN + full-deploy": (dyn_full, None),
        "  + regime vol-scalar": (dyn_regime, None),
        "  + survival floor": (dyn_full, DD_FLOOR),
        "  + regime + floor": (dyn_regime, DD_FLOOR),
    }
    print(f"[data] {len(syms)} assets x {len(px)} days | weekly reselect, trailing {WINDOW}d, leveraged in selection")
    print(f"{'variant':<26}{'ret':>9}{'sharpe':>8}{'maxDD':>9}{'avgGross':>9}{'#held':>7}")
    for name, (t, ddf) in variants.items():
        net = R.simulate(px, t, R.FEE, buffer=buf, max_turnover=mt, dd_floor=ddf)
        m = R.metrics(net, 252.0)
        held = (t.abs() > 1e-4).sum(axis=1).mean()
        print(f"{name:<26}{m['total_return']:>+8.1%}{m['sharpe']:>+8.2f}{m['max_dd']:>+9.1%}"
              f"{t.abs().sum(axis=1).mean():>9.2f}{held:>7.1f}")


if __name__ == "__main__":
    run()
