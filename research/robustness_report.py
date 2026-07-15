"""
═══════════════════════════════════════════════════════════════════════════════
  ROBUSTNESS REPORT — statistical stress-tests on the ENGINE's real return series
═══════════════════════════════════════════════════════════════════════════════

Operates on the daily portfolio-value series of the latest native Lumibot backtest
(logs/*_stats.parquet) — i.e. the GROUND-TRUTH engine P&L (full rule blend, tactical
short, costs), NOT the vectorised twin (which diverges from the engine). Produces:

  1. Walk-forward   — contiguous sub-periods; the edge must persist out-of-sample.
  2. Block bootstrap — 10k resampled paths (preserves momentum autocorrelation) →
     CI on full-period return / Sharpe / maxDD, AND the ~1-MONTH terminal-return
     distribution (the competition metric).
  3. Monte Carlo cost stress — extra bps/day drag → does the edge survive frictions.
  4. Regime conditional — performance in SPY up/down and high/low-vol regimes.

    python research/robustness_report.py
"""
from __future__ import annotations
import sys, glob
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import research.robustness as R  # block_bootstrap, metrics

REPO = Path(__file__).resolve().parent.parent
N_PATHS, BLOCK, SEED = 10_000, 10, 7


def load_engine_returns():
    sp = sorted(glob.glob(str(REPO / "logs" / "*stats.parquet")))
    if not sp:
        raise SystemExit("no logs/*stats.parquet — run backtest_daily.py first")
    df = pd.read_parquet(sp[-1]); df.index = pd.to_datetime(df.index)
    pv = df["portfolio_value"].astype(float)
    ret = pv.pct_change().dropna()
    return sp[-1].split("/")[-1], pv, ret


def bars_per(period_days, index):
    span_days = (index[-1] - index[0]).days
    return max(1, round(len(index) * period_days / span_days))


def ann(index):
    span = (index[-1] - index[0]).days / 365.25
    return len(index) / span if span > 0 else 252.0


def pct(x, q):
    return float(np.quantile(x, q))


def main():
    name, pv, ret = load_engine_returns()
    bpy = ann(ret.index)
    m = R.metrics(ret, bpy)
    print(f"══ ENGINE return series: {name} ══")
    print(f"   {len(ret)} bars | {ret.index[0].date()}→{ret.index[-1].date()} | ~{bpy:.0f} bars/yr")
    print(f"   HEADLINE: total {m['total_return']:+.1%} | Sharpe {m['sharpe']:.2f} | maxDD {m['max_dd']:+.1%} "
          f"| ann.vol {ret.std()*np.sqrt(bpy):.1%}")

    # ── 1. WALK-FORWARD (6 contiguous segments) ──
    print("\n══ 1) WALK-FORWARD (6 contiguous sub-periods — edge must persist) ══")
    print(f"   {'segment':<22}{'ret':>9}{'sharpe':>8}{'maxDD':>9}{'%pos-days':>10}")
    segs = np.array_split(np.arange(len(ret)), 6)
    pos_segments = 0
    for s in segs:
        r = ret.iloc[s]; mm = R.metrics(r, bpy)
        if mm["total_return"] > 0:
            pos_segments += 1
        print(f"   {r.index[0].date()}→{r.index[-1].date()}{mm['total_return']:>+9.1%}"
              f"{mm['sharpe']:>+8.2f}{mm['max_dd']:>+9.1%}{(r>0).mean():>10.0%}")
    print(f"   → {pos_segments}/6 sub-periods positive")

    # ── 2. BLOCK BOOTSTRAP ──
    print(f"\n══ 2) BLOCK BOOTSTRAP ({N_PATHS:,} paths, block={BLOCK}) ══")
    full = R.block_bootstrap(ret, BLOCK, N_PATHS, len(ret), seed=SEED)
    print(f"   FULL-PERIOD total return:  median {np.median(full):+.0%} | "
          f"5–95% CI [{pct(full,.05):+.0%}, {pct(full,.95):+.0%}] | P(>0) {(full>0).mean():.0%}")
    # tournament horizon (~1 month)
    h = bars_per(30, ret.index)
    term = R.block_bootstrap(ret, BLOCK, N_PATHS, h, seed=SEED)
    print(f"\n   ~1-MONTH TERMINAL RETURN (h={h} bars ≈ the competition window):")
    for q in (.05, .25, .50, .75, .90, .95):
        print(f"      p{int(q*100):<3} {pct(term,q):+.1%}")
    print(f"      P(>0) {(term>0).mean():.0%} | P(>+20%) {(term>0.20).mean():.0%} | "
          f"P(>+40%) {(term>0.40).mean():.0%} | P(<-15%) {(term<-0.15).mean():.0%} | worst {term.min():+.0%}")

    # ── 3. MONTE CARLO COST STRESS ──
    print("\n══ 3) COST STRESS (extra bps/day drag on returns; engine already at 5bps fee) ══")
    print(f"   {'extra drag':<14}{'full ret':>10}{'1-mo median':>13}{'1-mo P(>0)':>12}")
    for bps in (0, 2, 5, 10, 20):
        rr = ret - bps / 1e4
        fr = np.prod(1 + rr) - 1
        tt = R.block_bootstrap(rr, BLOCK, 4000, h, seed=SEED)
        print(f"   +{bps:>2} bps/day{fr:>10.0%}{np.median(tt):>+13.1%}{(tt>0).mean():>12.0%}")

    # ── 4. REGIME CONDITIONAL ──
    print("\n══ 4) REGIME CONDITIONAL (vs SPY direction & realised vol) ══")
    spy_f = REPO / "data" / "daily" / "SPY.csv"
    if spy_f.exists():
        spy = pd.read_csv(spy_f)
        tcol = [c for c in spy.columns if "date" in c.lower() or "time" in c.lower()][0]
        spy[tcol] = pd.to_datetime(spy[tcol], utc=True).dt.tz_localize(None)
        spy = spy.set_index(tcol)["close"].astype(float)
        spy_ret = spy.pct_change().reindex(ret.index).fillna(0.0)
        vol = ret.rolling(20).std()
        hi = vol > vol.median()
        for lbl, mask in [("SPY up-days   ", spy_ret > 0), ("SPY down-days ", spy_ret < 0),
                          ("high-vol regime", hi), ("low-vol regime ", ~hi)]:
            r = ret[mask]
            if len(r):
                print(f"   {lbl}: mean {r.mean()*1e4:+6.1f} bps/day | hit {(r>0).mean():.0%} | n={len(r)}")
    else:
        print("   (SPY.csv not found — skip)")

    print("\n══ VERDICT SUMMARY ══")
    print(f"   positive sub-periods: {pos_segments}/6 | bootstrap P(full>0): {(full>0).mean():.0%} | "
          f"1-mo P(>0): {(term>0).mean():.0%}, P(>+20%): {(term>0.20).mean():.0%}")


if __name__ == "__main__":
    main()
