"""
═══════════════════════════════════════════════════════════════════════════════
  DOWNLOAD DAILY — multi-asset daily bars (crypto + US equities + ETFs)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* yfinance: https://pypi.org/project/yfinance/

Why daily + multi-asset?
------------------------
Carver's framework is natively a *daily*, cross-asset-class portfolio. Free
1-minute equity history is scarce, but free *daily* history spans years across
crypto, US equities and ETFs — perfect for validating the multi-asset engine
structure (instrument weights, IDM, cross-asset diversification) over multiple
regimes. The official competition run supplies intraday equity data via Massive;
this downloader is for local structural validation only.

Writes one CSV per symbol to ``data/daily/{SYMBOL}.csv`` with columns
``open, high, low, close, volume, timestamp`` (UTC), matching the intraday
schema so the same loaders work.

Usage
-----
    python research/download_daily.py                 # default multi-asset universe
    python research/download_daily.py --years 3
    python research/download_daily.py --symbols SPY QQQ AAPL BTC-USD
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
DAILY_DIR = REPO / "data" / "daily"


def _universe_tickers() -> list[str]:
    """Derive the daily download list from strategies/config/universe.csv."""
    from strategies.engine.instruments import load_universe
    ins = load_universe(roles=("core", "convex"))
    tickers = [i.daily_ticker for i in ins]
    # benchmarks used by the tearsheet / robustness comparisons
    for b in ("SPY", "QQQ", "BTC-USD", "TLT"):
        if b not in tickers:
            tickers.append(b)
    return list(dict.fromkeys(tickers))


DEFAULT_UNIVERSE = _universe_tickers()


def _norm(sym: str) -> str:
    """Filesystem-safe stem; keep the ticker readable (BTC-USD -> BTC-USD)."""
    return sym.replace("/", "_")


def download(symbols: list[str], years: int) -> None:
    import pandas as pd
    import yfinance as yf

    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    period = f"{years}y"
    print(f"[cfg] {len(symbols)} symbols, period={period}")

    data = yf.download(symbols, period=period, interval="1d",
                       auto_adjust=True, group_by="ticker", progress=False, threads=True)

    ok = 0
    for sym in symbols:
        try:
            df = data[sym] if isinstance(data.columns, pd.MultiIndex) else data
        except KeyError:
            print(f"[MISS] {sym}: not in response")
            continue
        df = df.dropna(how="all")
        if df.empty:
            print(f"[MISS] {sym}: empty")
            continue
        out = pd.DataFrame({
            "open": df["Open"], "high": df["High"], "low": df["Low"],
            "close": df["Close"], "volume": df["Volume"],
        }).dropna()
        out["timestamp"] = pd.to_datetime(out.index, utc=True)
        out = out[["open", "high", "low", "close", "volume", "timestamp"]]
        path = DAILY_DIR / f"{_norm(sym)}.csv"
        out.to_csv(path, index=False)
        print(f"[data] {sym:<9} {len(out):>5} daily bars -> {path.name}")
        ok += 1
    print(f"[done] {ok}/{len(symbols)} symbols written to {DAILY_DIR}")


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download multi-asset daily bars.")
    p.add_argument("--symbols", nargs="+", default=DEFAULT_UNIVERSE)
    p.add_argument("--years", type=int, default=3)
    return p.parse_args()


if __name__ == "__main__":
    a = _parse()
    download(a.symbols, a.years)
