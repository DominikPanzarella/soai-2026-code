"""
═══════════════════════════════════════════════════════════════════════════════
  SELECT UNIVERSE — systematic instrument selection (gate → rank → diversify)
═══════════════════════════════════════════════════════════════════════════════

Implements research/instrument_selection.md: pick WHICH assets the bot should
trade next month, from trailing OHLCV only. Three stages, per asset class:

  1) GATE   — liquidity floor (ADDV pctile), tradeable-vol band, min history,
              long/flat eligibility (trailing return > 0 for the spot mandate).
  2) RANK   — composite z-score: trend-strength (Efficiency Ratio + drift t-stat),
              signed momentum, liquidity (−Amihud), low-beta tilt, vol-band closeness.
  3) DIVERSIFY — greedy pick that maximises independent bets (IDM from the
              trailing correlation matrix), with a per-cluster cap.

Sources: Carver AFTS/qoppac (selection, cost-in-SR, diversification); Kaufman ER;
Lo-MacKinlay variance ratio; Amihud (2002); Moskowitz-Ooi-Pedersen; Harvey et al.
(vol targeting); Gu-Kelly-Xiu (momentum/liquidity/vol dominate). See the doc.

Usage
-----
    python research/select_universe.py                # dry-run: print the recommendation
    python research/select_universe.py --apply        # also write active flags into universe.csv
    python research/select_universe.py --window 90 --nmax-crypto 5 --nmax-equity 9
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from strategies.engine.instruments import load_universe, macro_class

REPO = Path(__file__).resolve().parent.parent
DAILY = REPO / "data" / "daily"
UNI = REPO / "strategies" / "config" / "universe.csv"
BPY = 252.0

# blunt defaults (do NOT tune on tournament data)
SIGMA_TARGET = 0.35          # annualised; tradeable-vol band centre
VOL_BAND = (0.4, 6.0)        # keep names within [lo,hi]*sigma_target = [14%, 210%].
                             # MUST match SelectionConfig.vol_band_hi=6.0 in the engine:
                             # the old (0.4, 3.0)=[14%,105%] screened OUT the 3x leveraged
                             # ETFs (SOXL ~115%) — the convex drivers — a real bug.
ADDV_PCTILE = 0.40           # liquidity floor within class
COMP_W = dict(trend=0.35, mom=0.25, liq=0.15, cost=0.10, beta=0.10, vol=0.05)
CLUSTER_CORR = 0.90          # drop a candidate correlated > this with a picked name
BENCH = {"crypto": "BTC", "equity": "SPY", "commodity": "GLD"}


def _load(ins) -> pd.DataFrame | None:
    f = DAILY / f"{ins.daily_ticker}.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f, parse_dates=["timestamp"]).set_index("timestamp").sort_index()
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def _metrics(df: pd.DataFrame, mkt_ret: pd.Series, window: int) -> dict:
    d = df.tail(window)
    c, h, l, v = d["close"], d["high"], d["low"], d["volume"]
    ret = np.log(c / c.shift(1)).dropna()
    n = len(ret)
    if n < 30:
        return {}
    addv = float((c * v).median())
    illiq = float((ret.abs() / (c * v).reindex(ret.index).replace(0, np.nan)).mean())
    park = float(np.sqrt((1 / (4 * np.log(2))) * (np.log(h / l) ** 2).mean()) * np.sqrt(BPY))
    er = float(abs(c.iloc[-1] - c.iloc[0]) / c.diff().abs().sum()) if c.diff().abs().sum() else 0.0
    snr = float(ret.mean() / ret.std() * np.sqrt(n)) if ret.std() else 0.0
    tsmom = float(c.iloc[-1] / c.iloc[0] - 1.0)
    r_skip = float(c.iloc[-2] / c.iloc[0] - 1.0) if n > 2 else tsmom
    # beta vs class benchmark (shrunk toward 1)
    m = mkt_ret.reindex(ret.index)
    beta = 1.0
    if m.notna().sum() > 10 and m.var() > 0:
        beta = float(np.cov(ret.fillna(0), m.fillna(0))[0, 1] / m.var())
    beta = 0.6 * beta + 0.4 * 1.0
    return dict(addv=addv, illiq=illiq, vol=park, er=er, snr=snr,
                tsmom=tsmom, r_skip=r_skip, beta=beta, ret=ret)


def _z(s: pd.Series) -> pd.Series:
    sd = s.std()
    return ((s - s.mean()) / sd).clip(-3, 3) if sd and sd > 0 else s * 0.0


def select(window: int, nmax_crypto: int, nmax_equity: int, cost_budget: float = 0.10):
    core = load_universe(roles=("core",))
    data = {ins.symbol: _load(ins) for ins in core}
    macro = {ins.symbol: macro_class(ins.asset_class) for ins in core}
    cost_bps = {ins.symbol: ins.cost_bps for ins in core}

    # class benchmark returns
    bench_ret = {}
    for cls, bsym in BENCH.items():
        if bsym in data and data[bsym] is not None:
            bc = data[bsym]["close"].tail(window)
            bench_ret[cls] = np.log(bc / bc.shift(1))

    # metrics per asset
    rows, retmap = {}, {}
    for s, df in data.items():
        if df is None or len(df) < 500:
            continue
        cls = macro.get(s, "other")
        met = _metrics(df, bench_ret.get(cls, pd.Series(dtype=float)), window)
        if not met:
            continue
        met["cost_sr"] = (cost_bps[s] / 1e4) * 50.0 / max(met["vol"], 0.05)  # ann cost/vol proxy
        rows[s] = met
        retmap[s] = met.pop("ret")

    M = pd.DataFrame(rows).T
    selected = {}
    for cls in sorted(set(macro[s] for s in M.index)):
        sub = M[[macro[s] == cls for s in M.index]].copy()
        if sub.empty:
            continue
        # ── Stage 1: gates ─────────────────────────────────────────────
        addv_floor = sub["addv"].quantile(ADDV_PCTILE)
        keep = (
            (sub["addv"] >= addv_floor)
            & (sub["vol"].between(VOL_BAND[0] * SIGMA_TARGET, VOL_BAND[1] * SIGMA_TARGET))
            & (sub["cost_sr"] <= cost_budget)
            & (sub["tsmom"] > 0)          # long/flat eligibility
        )
        g = sub[keep]
        if g.empty:
            continue
        # ── Stage 2: composite score ───────────────────────────────────
        score = (COMP_W["trend"] * _z(0.5 * g["er"] + 0.5 * _z(g["snr"].abs()))
                 + COMP_W["mom"] * _z(np.sign(g["tsmom"]) * g["r_skip"])
                 + COMP_W["liq"] * _z(-g["illiq"])
                 + COMP_W["cost"] * _z(-g["cost_sr"])
                 + COMP_W["beta"] * _z(-g["beta"])
                 + COMP_W["vol"] * _z(-(np.log(g["vol"] / SIGMA_TARGET)).abs()))
        g = g.assign(score=score).sort_values("score", ascending=False)
        # ── Stage 3: greedy correlation-diversification ────────────────
        nmax = nmax_crypto if cls == "crypto" else nmax_equity
        ret_df = pd.DataFrame({s: retmap[s] for s in g.index}).dropna(how="all")
        corr = ret_df.corr()
        picks = [g.index[0]]
        for cand in g.index[1:]:
            if len(picks) >= nmax:
                break
            cmax = max((abs(corr.loc[cand, p]) for p in picks if p in corr.columns
                        and cand in corr.columns), default=0.0)
            if cmax < CLUSTER_CORR:               # per-cluster cap
                picks.append(cand)
        selected[cls] = [(s, float(g.loc[s, "score"]), float(g.loc[s, "vol"]),
                          float(g.loc[s, "tsmom"]), float(g.loc[s, "er"])) for s in picks]
    return selected, M


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=90)
    ap.add_argument("--nmax-crypto", type=int, default=5)
    ap.add_argument("--nmax-equity", type=int, default=9)
    ap.add_argument("--apply", action="store_true", help="write active flags into universe.csv")
    a = ap.parse_args()

    sel, M = select(a.window, a.nmax_crypto, a.nmax_equity)
    chosen = set()
    print(f"═══ SELECTED UNIVERSE (trailing {a.window}d, gate→rank→diversify) ═══")
    for cls, items in sel.items():
        print(f"\n{cls.upper()}  (picked {len(items)})")
        print(f"  {'sym':<7}{'score':>7}{'vol':>7}{'mom':>8}{'ER':>6}")
        for s, sc, vol, mom, er in items:
            print(f"  {s:<7}{sc:>7.2f}{vol:>7.0%}{mom:>8.1%}{er:>6.2f}")
            chosen.add(s)

    if a.apply:
        lines = UNI.read_text().rstrip("\n").splitlines()
        out = [lines[0]]
        for ln in lines[1:]:
            f = ln.split(",")
            if f[7] == "core":                    # only re-flag core rows
                f[8] = "1" if f[0] in chosen else "0"
            out.append(",".join(f))
        UNI.write_text("\n".join(out) + "\n")
        print(f"\n[applied] wrote active flags for {len(chosen)} selected core instruments to {UNI.name}")
    else:
        print(f"\n[dry-run] {len(chosen)} instruments recommended active. Re-run with --apply to write.")


if __name__ == "__main__":
    main()
