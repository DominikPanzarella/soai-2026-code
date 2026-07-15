"""
═══════════════════════════════════════════════════════════════════════════════
  ROBUSTNESS — vectorised multi-asset engine simulator (regime / MC / cost)
═══════════════════════════════════════════════════════════════════════════════

Reproduces the engine's target weights VECTORISED (reusing the same forecast
functions, handcrafted instrument weights, class-aware XS momentum, estimated
IDM and per-class caps) and simulates a faithful long/flat book with a Carver
no-trade buffer. Used to validate the Carver multi-asset STRUCTURE and its
robustness — NOT to overfit a single window.

Modes
-----
* ``daily``  (default): full multi-asset universe (crypto + equities + ETFs)
  from ``data/daily/*.csv`` over multiple years — the right test for the
  cross-asset portfolio construction.
* ``crypto`` : crypto-only intraday from ``data/{SYM}_1m_spot.csv`` resampled
  to the strategy cadence — execution-realistic sleeve check.

Usage
-----
    python research/robustness.py            # daily multi-asset
    python research/robustness.py --mode crypto
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from strategies.engine.config import EngineConfig
from strategies.engine import data as D
from strategies.engine.instruments import (
    load_universe, handcraft_weights, groups_map, class_map, idm_from_returns,
)
from strategies.engine.volatility import ewma_vol
from strategies.engine.forecasts.trend_ewmac import ewmac_forecast
from strategies.engine.forecasts.breakout import breakout_forecast
from strategies.engine.forecasts.mean_reversion import mean_reversion_forecast
from strategies.engine.forecasts.connors_rsi import connors_forecast
from strategies.engine.forecasts.xs_momentum import xs_momentum_forecast
from strategies.engine.forecasts.residual_momentum import residual_momentum_forecast
from strategies.engine.forecasts.lottery_max import max_lottery_forecast
from strategies.engine.forecasts.safer_fast_mr import safer_fast_mr_forecast
from strategies.engine.forecasts.acceleration import acceleration_forecast
from strategies.engine.forecasts.mtf_pullback import mtf_pullback_forecast
from strategies.engine.forecasts.kama import kama_forecast
from strategies.engine.forecasts.residual_mr import residual_mr_forecast
from strategies.engine.forecasts.leadlag import leadlag_forecast
from strategies.engine.forecasts.intermarket_div import intermarket_div_forecast
from strategies.engine.forecasts.vol_breakout import vol_breakout_forecast

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
DAILY = DATA / "daily"
FEE = 0.0010


# ── data loading ─────────────────────────────────────────────────────────────
def load_daily(instruments) -> tuple[pd.DataFrame, dict]:
    cols, is_crypto = {}, {}
    for ins in instruments:
        f = DAILY / f"{ins.daily_ticker}.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f, parse_dates=["timestamp"]).set_index("timestamp")
        cols[ins.symbol] = df["close"].astype(float)
        is_crypto[ins.symbol] = ins.is_crypto
    px = pd.DataFrame(cols).sort_index()
    # Common business-day calendar: crypto sampled at weekday close, so equity
    # vols/forecasts are not diluted by weekend crypto bars.
    px = px.ffill()
    bidx = pd.bdate_range(px.index.min(), px.index.max(), tz=px.index.tz)
    px = px.reindex(bidx).dropna(how="all")
    return px, is_crypto


def load_crypto_intraday(instruments, cfg) -> tuple[pd.DataFrame, dict]:
    cols, is_crypto = {}, {}
    for ins in instruments:
        if not ins.is_crypto:
            continue
        f = DATA / f"{ins.symbol}_1m_spot.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f, parse_dates=["timestamp"]).set_index("timestamp")
        c, _ = D.resample_to_cadence(df["close"].astype(float),
                                     df["volume"].astype(float), cfg.sleeptime)
        cols[ins.symbol] = c
        is_crypto[ins.symbol] = True
    px = pd.DataFrame(cols).sort_index().dropna(how="all")
    return px, is_crypto


# ── vectorised target weights (twin of strategy.py, multi-asset) ────────────
def target_weights_frame(px: pd.DataFrame, cfg: EngineConfig, iw: dict,
                         groups: dict, classes: dict, is_crypto: dict,
                         bars_per_year_daily: bool) -> pd.DataFrame:
    syms = list(px.columns)
    cap = cfg.forecast_cap

    sf_bpy = 252.0 if bars_per_year_daily else cfg.bars_per_year(True)
    ew = pd.DataFrame({s: ewmac_forecast(px[s], cfg.ewmac, cfg.risk.vol_span, cap) for s in syms})
    ac = pd.DataFrame({s: acceleration_forecast(px[s], cfg.ewmac, cfg.acceleration, cfg.risk.vol_span, cap) for s in syms})
    bo = pd.DataFrame({s: breakout_forecast(px[s], cfg.breakout, cap) for s in syms})
    mr = pd.DataFrame({s: mean_reversion_forecast(px[s], cfg.mean_reversion, cap) for s in syms})
    cn = pd.DataFrame({s: connors_forecast(px[s], cfg.connors, cap) for s in syms})
    sf = pd.DataFrame({s: safer_fast_mr_forecast(px[s], cfg.safer_fast_mr, cfg.risk.vol_span, sf_bpy, cap) for s in syms})
    mt = pd.DataFrame({s: mtf_pullback_forecast(px[s], cfg.mtf_pullback, cap) for s in syms})
    km = pd.DataFrame({s: kama_forecast(px[s], cfg.kama, cap) for s in syms})
    rmr = pd.DataFrame(residual_mr_forecast({s: px[s] for s in syms}, cfg.residual_mr, cap, groups=groups))
    ll = pd.DataFrame(leadlag_forecast({s: px[s] for s in syms}, cfg.leadlag, cap, groups=groups))
    im = pd.DataFrame(intermarket_div_forecast({s: px[s] for s in syms}, cfg.intermarket_div, cap, groups=groups, is_crypto=is_crypto))
    vb = pd.DataFrame({s: vol_breakout_forecast(px[s], cfg.vol_breakout, cap) for s in syms})
    xs = pd.DataFrame(xs_momentum_forecast({s: px[s] for s in syms}, cfg.xs_momentum, cap, groups=groups))
    rm = pd.DataFrame(residual_momentum_forecast({s: px[s] for s in syms}, cfg.residual_mom, cap, groups=groups))
    ml = pd.DataFrame(max_lottery_forecast({s: px[s] for s in syms}, cfg.max_lottery, cap, groups=groups))

    # annualised vol per asset (asset-class-aware bars/year)
    def bpy(sym):
        if bars_per_year_daily:
            return 252.0  # business-day calendar for all classes
        return cfg.bars_per_year(is_crypto.get(sym, True))
    vol = pd.DataFrame({s: (ewma_vol(px[s], cfg.risk.vol_span) * np.sqrt(bpy(s)))
                        for s in syms}).clip(lower=cfg.risk.vol_floor_annual)

    # G1 vol-managed overlay on directional trend/momentum forecasts.
    if cfg.vol_managed.enabled:
        vm = (cfg.vol_managed.target_vol_annual / vol).clip(cfg.vol_managed.clip_lo, cfg.vol_managed.clip_hi)
        if "ewmac" in cfg.vol_managed.applies_to:
            ew = ew * vm; ac = ac * vm; mt = mt * vm; km = km * vm; vb = vb * vm
        if "breakout" in cfg.vol_managed.applies_to: bo = bo * vm
        if "xs" in cfg.vol_managed.applies_to: xs = xs * vm

    w = {"ewmac": cfg.ewmac.weight, "acceleration": cfg.acceleration.weight,
         "breakout": cfg.breakout.weight, "mr": cfg.mean_reversion.weight,
         "connors": cfg.connors.weight, "safer_mr": cfg.safer_fast_mr.weight,
         "xs": cfg.xs_momentum.weight, "residual": cfg.residual_mom.weight,
         "maxlot": cfg.max_lottery.weight, "mtf": cfg.mtf_pullback.weight,
         "kama": cfg.kama.weight, "residual_mr": cfg.residual_mr.weight,
         "leadlag": cfg.leadlag.weight, "intmkt": cfg.intermarket_div.weight,
         "volbrk": cfg.vol_breakout.weight}
    wsum = sum(w.values())
    raw_comb = cfg.risk.fdm * (w["ewmac"]*ew + w["acceleration"]*ac + w["breakout"]*bo
                               + w["mr"]*mr + w["connors"]*cn + w["safer_mr"]*sf
                               + w["xs"]*xs + w["residual"]*rm + w["maxlot"]*ml
                               + w["mtf"]*mt + w["kama"]*km + w["residual_mr"]*rmr
                               + w["leadlag"]*ll + w["intmkt"]*im + w["volbrk"]*vb) / wsum
    combined = (cap * np.tanh(raw_comb / cap)) if cfg.soft_cap else raw_comb.clip(-cap, cap)

    # estimated IDM (static, full-sample) from instrument return correlations
    rets = px.pct_change(fill_method=None)
    idm = idm_from_returns(rets, iw, cap=cfg.risk.idm_cap) if cfg.risk.idm_estimate else cfg.risk.idm

    iw_s = pd.Series({s: iw.get(s, 0.0) for s in syms})
    raw = (combined / cfg.forecast_target) * (cfg.risk.vol_target_annual * idm) * iw_s / vol
    # per-instrument long/short with a tactical regime gate: crypto is always
    # long/flat; equities may short ONLY on risk-off bars (breadth < threshold).
    breadth = (px > px.rolling(cfg.risk.breadth_ma).mean()).mean(axis=1)
    risk_off = breadth < cfg.risk.breadth_thr
    for s in syms:
        if is_crypto.get(s, True) or not cfg.risk.tactical_short:
            raw[s] = raw[s].clip(lower=0.0)
        else:
            raw[s] = raw[s].where(risk_off, raw[s].clip(lower=0.0))  # signed only when risk-off
    raw = raw.clip(-cfg.risk.max_weight_per_asset, cfg.risk.max_weight_per_asset)

    # per-asset-class concentration cap on ABSOLUTE exposure (row-wise)
    if cfg.risk.max_class_conc > 0:
        for cls in set(classes.get(s, s) for s in syms):
            cols = [s for s in syms if classes.get(s, s) == cls]
            csum = raw[cols].abs().sum(axis=1)
            scale = (cfg.risk.max_class_conc / csum).clip(upper=1.0).replace([np.inf, -np.inf], 1.0).fillna(1.0)
            raw[cols] = raw[cols].mul(scale, axis=0)

    budget = cfg.risk.gross_cap - cfg.risk.cash_buffer
    gross = raw.abs().sum(axis=1)                       # Σ|w| for long/short
    scale = (budget / gross).clip(upper=1.0).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    core = raw.mul(scale, axis=0)
    return core.fillna(0.0), idm


def add_convex(px_conv: pd.DataFrame, core: pd.DataFrame, cfg: EngineConfig) -> pd.DataFrame:
    if not cfg.convex.enabled or cfg.convex.fraction <= 0 or px_conv.empty:
        return core
    mom = px_conv / px_conv.shift(cfg.convex.momentum_lookback) - 1.0
    mom_pos = mom.where(mom > 0)
    rank = mom_pos.rank(axis=1, ascending=False)
    sel = (rank <= cfg.convex.top_n) & mom_pos.notna()
    count = sel.sum(axis=1)
    conv = sel.astype(float).div(count.replace(0, np.nan), axis=0) * cfg.convex.fraction
    conv = conv.reindex(core.index).fillna(0.0)
    frac = (count > 0).astype(float).reindex(core.index).fillna(0.0) * cfg.convex.fraction
    blended = core.mul(1.0 - frac, axis=0)
    for c in conv.columns:
        blended[c] = blended.get(c, 0.0) + conv[c]
    return blended.fillna(0.0)


# ── simulation & metrics ─────────────────────────────────────────────────────
def simulate(px: pd.DataFrame, tgt: pd.DataFrame, fee: float, buffer: float = 0.0,
             max_turnover: float = 0.0, dd_floor: tuple | None = None) -> pd.Series:
    """`dd_floor=(dd0,dmax,mmin)` scales exposure down after a drawdown: mult=1 for
    dd>-dd0, ramps to mmin at dd<=-dmax (survival kill-switch)."""
    px = px.reindex(columns=tgt.columns)
    rets = px.pct_change(fill_method=None).fillna(0.0).values
    T = np.nan_to_num(tgt.values)
    n_t, n_a = T.shape
    w = np.zeros(n_a)
    net = np.zeros(n_t)
    eq, peak = 1.0, 1.0
    for t in range(n_t):
        r = rets[t]
        growth = 1.0 + float(np.dot(w, r))
        step_ret = growth - 1.0
        if growth != 0.0:
            w = w * (1.0 + r) / growth
        # survival floor: shrink the target by a drawdown multiplier
        tgt_t = T[t]
        if dd_floor is not None:
            dd0, dmax, mmin = dd_floor
            dd = eq / peak - 1.0
            if dd < -dd0:
                m = max(mmin, 1.0 - (1.0 - mmin) * (-dd - dd0) / max(dmax - dd0, 1e-9))
                tgt_t = tgt_t * m
        delta = tgt_t - w
        mask = np.abs(delta) > buffer
        cost = 0.0
        if mask.any():
            traded = np.where(mask, delta, 0.0)
            turn = float(np.abs(traded).sum())
            if max_turnover and max_turnover > 0 and turn > max_turnover:
                traded *= max_turnover / turn
                turn = max_turnover
            cost = fee * turn
            w = w + traded
        net[t] = step_ret - cost
        eq *= (1.0 + net[t]); peak = max(peak, eq)
    return pd.Series(net, index=tgt.index)


def metrics(net: pd.Series, bpy: float) -> dict:
    eq = (1.0 + net).cumprod()
    dd = (eq / eq.cummax() - 1.0).min()
    sd = net.std()
    sharpe = (net.mean() / sd * np.sqrt(bpy)) if sd > 0 else 0.0
    return {"total_return": eq.iloc[-1] - 1.0, "sharpe": sharpe, "max_dd": dd}


def block_bootstrap(net, block, n_paths, horizon, seed=7):
    rng = np.random.default_rng(seed)
    arr = net.values
    n = len(arr)
    out = np.empty(n_paths)
    for p in range(n_paths):
        acc = []
        while len(acc) < horizon:
            start = rng.integers(0, max(1, n - block))
            acc.extend(arr[start:start + block])
        out[p] = np.prod(1.0 + np.array(acc[:horizon])) - 1.0
    return out


def _fmt(m):
    return f"ret={m['total_return']:+8.2%}  sharpe={m['sharpe']:+5.2f}  maxDD={m['max_dd']:+7.2%}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["daily", "crypto"], default="daily")
    ap.add_argument("--cadence", choices=["5M", "15M", "60M", "1D"], default=None,
                    help="override the engine sleeptime (crypto mode resamples to it)")
    args = ap.parse_args()

    cfg = EngineConfig()
    if args.cadence:
        cfg.sleeptime = args.cadence
    core_ins = load_universe(roles=("core",))
    conv_ins = load_universe(roles=("convex",))
    iw = handcraft_weights(core_ins, cfg.macro_weights)
    groups = groups_map(core_ins)
    classes = class_map(core_ins)

    if args.mode == "daily":
        px, is_crypto = load_daily(core_ins)
        px_conv, _ = load_daily(conv_ins)
        ann_bpy = 252.0
        daily = True
    else:
        px, is_crypto = load_crypto_intraday(core_ins, cfg)
        px_conv = pd.DataFrame()
        ann_bpy = cfg.bars_per_year(True)
        daily = False

    px = px.dropna(how="all")
    print(f"[data] mode={args.mode}  {px.shape[1]} assets x {px.shape[0]} bars "
          f"({px.index[0].date()} → {px.index[-1].date()})")
    print(f"[handcraft] groups={len(set(groups.values()))}  "
          f"top weights={dict(sorted(iw.items(), key=lambda kv: -kv[1])[:3])}")

    core, idm = target_weights_frame(px, cfg, iw, groups, classes, is_crypto, daily)
    if not px_conv.empty:
        px_conv = px_conv.reindex(px.index).ffill()
    tgt = add_convex(px_conv, core, cfg)
    px_all = px.join(px_conv[[c for c in px_conv.columns if c not in px.columns]]) if not px_conv.empty else px

    buf = cfg.execution.no_trade_buffer
    mt = cfg.execution.max_turnover_per_step
    net = simulate(px_all, tgt, FEE, buffer=buf, max_turnover=mt)
    gross = simulate(px_all, tgt, 0.0, buffer=buf, max_turnover=mt)

    print(f"[IDM estimated] {idm:.2f}  |  cadence={cfg.sleeptime}  buffer={buf}  turnover_cap={mt}")
    print("\n═══ FULL PERIOD ═══")
    print("  net-of-cost:", _fmt(metrics(net, ann_bpy)))
    print("  gross(0fee):", _fmt(metrics(gross, ann_bpy)))
    print(f"  avg gross exposure={tgt.sum(axis=1).mean():.2f}  max={tgt.sum(axis=1).max():.2f}")

    print("\n═══ WALK-FORWARD (contiguous thirds) ═══")
    for i, chunk in enumerate(np.array_split(net, 3), 1):
        print(f"  window {i}: {_fmt(metrics(chunk, ann_bpy))}")

    print("\n═══ COST PESSIMISM ═══")
    for mult in (1, 2, 3):
        print(f"  {mult}x fees: {_fmt(metrics(simulate(px_all, tgt, FEE*mult, buffer=buf, max_turnover=mt), ann_bpy))}")

    print("\n═══ MONTE CARLO block bootstrap (1-month terminal return) ═══")
    horizon = int(ann_bpy / 12)
    dist = block_bootstrap(net, block=max(5, int(ann_bpy/52)), n_paths=2000, horizon=horizon)
    for q in (5, 25, 50, 75, 95):
        print(f"  p{q:>2}: {np.percentile(dist, q):+8.2%}")
    print(f"  P(positive month) = {(dist > 0).mean():.1%}")


if __name__ == "__main__":
    main()
