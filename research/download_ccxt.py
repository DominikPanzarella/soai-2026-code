"""
═══════════════════════════════════════════════════════════════════════════════
  DOWNLOAD CCXT — minute-bar fetcher for local backtesting
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* CCXT unified API (fetch_ohlcv): https://docs.ccxt.com/#/README?id=ohlcv-candlestick-charts
* SoAI template CSV contract: data/{SYMBOL}_1m_spot.csv with columns
  open, high, low, close, volume, timestamp (ISO-8601, UTC).

What it does
------------
Pulls 1-minute spot OHLCV bars for a list of crypto bases (quoted in USDT/USD)
and writes one CSV per base into ``data/`` in exactly the shape the bundled
``backtest.py`` harness expects. This is a *development-only* utility — the
official SoAI evaluation feeds data itself via CCXT/Massive, so nothing here
runs during the competition.

Notes
-----
* Today is mid-2026 and the official trading window (Aug 2026) is in the future,
  so for local development we download a recent *past* window (default: the last
  ~40 days) to iterate against realistic microstructure.
* Exchanges are tried in order until one serves the pair — some venues geoblock
  or lack a given listing. Binance has the deepest free 1-min history; Kraken /
  Coinbase / OKX / Bybit are fallbacks.

Usage
-----
    python research/download_ccxt.py                      # defaults (BTC, ETH, ...)
    python research/download_ccxt.py --symbols BTC ETH SOL --days 40
    python research/download_ccxt.py --exchange kraken --quote USD
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

# ── defaults ───────────────────────────────────────────────────────────────
DEFAULT_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "LINK", "LTC", "DOGE"]
DEFAULT_EXCHANGES = ["binance", "okx", "bybit", "kraken", "coinbase"]
DEFAULT_QUOTE = "USDT"
DEFAULT_DAYS = 40
TIMEFRAME = "1m"
PAGE_LIMIT = 1000  # bars per fetch_ohlcv call (venue-dependent cap)


def _build_exchange(name: str):
    """Instantiate a CCXT exchange with rate-limiting enabled."""
    import ccxt  # lazy: keeps import cheap / optional

    klass = getattr(ccxt, name, None)
    if klass is None:
        raise ValueError(f"Unknown CCXT exchange: {name}")
    return klass({"enableRateLimit": True})


def _resolve_market(exchange, base: str, quote: str) -> str | None:
    """Return a tradable symbol for ``base`` on ``exchange``, or None."""
    exchange.load_markets()
    for q in (quote, "USDT", "USD", "USDC"):
        sym = f"{base}/{q}"
        if sym in exchange.markets:
            return sym
    return None


def _fetch_ohlcv(exchange, symbol: str, since_ms: int) -> list[list]:
    """Paginate fetch_ohlcv from ``since_ms`` up to now."""
    now_ms = exchange.milliseconds()
    tf_ms = exchange.parse_timeframe(TIMEFRAME) * 1000
    rows: list[list] = []
    cursor = since_ms
    while cursor < now_ms:
        batch = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, since=cursor, limit=PAGE_LIMIT)
        if not batch:
            break
        rows.extend(batch)
        cursor = batch[-1][0] + tf_ms
        if len(batch) < PAGE_LIMIT:
            # Fewer than a full page → we have caught up to the venue's head.
            if batch[-1][0] >= now_ms - tf_ms:
                break
        time.sleep(exchange.rateLimit / 1000.0)
    return rows


def _write_csv(base: str, rows: list[list]) -> Path:
    """Write OHLCV rows to data/{BASE}_1m_spot.csv in the canonical shape."""
    import pandas as pd

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates(subset="ts").sort_values("ts")
    df["timestamp"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df[["open", "high", "low", "close", "volume", "timestamp"]]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / f"{base}_1m_spot.csv"
    df.to_csv(out, index=False)
    return out


def download(symbols: list[str], exchanges: list[str], quote: str, days: int) -> None:
    since_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

    # Instantiate exchanges once, in preference order.
    live = []
    for name in exchanges:
        try:
            ex = _build_exchange(name)
            ex.load_markets()
            live.append(ex)
            print(f"[ok]   exchange ready: {name} ({len(ex.markets)} markets)")
        except Exception as exc:  # noqa: BLE001 — venue may geoblock / rate-limit
            print(f"[skip] {name}: {type(exc).__name__}: {exc}")

    if not live:
        sys.exit("No CCXT exchange reachable — check network / try --exchange kraken")

    for base in symbols:
        for ex in live:
            sym = _resolve_market(ex, base, quote)
            if sym is None:
                continue
            try:
                rows = _fetch_ohlcv(ex, sym, since_ms)
            except Exception as exc:  # noqa: BLE001
                print(f"[warn] {base} via {ex.id}: {type(exc).__name__}: {exc}")
                continue
            if not rows:
                continue
            out = _write_csv(base, rows)
            print(f"[data] {base:<5} {sym:<10} {len(rows):>7,} bars via {ex.id:<9} -> {out.name}")
            break
        else:
            print(f"[MISS] {base}: no exchange served a market")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download 1-min crypto bars for local backtesting.")
    p.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, help="Base tickers (e.g. BTC ETH).")
    p.add_argument("--exchange", dest="exchanges", nargs="+", default=DEFAULT_EXCHANGES,
                   help="CCXT exchange ids tried in order.")
    p.add_argument("--quote", default=DEFAULT_QUOTE, help="Preferred quote currency (falls back to USDT/USD/USDC).")
    p.add_argument("--days", type=int, default=DEFAULT_DAYS, help="History depth in days.")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    print(f"[cfg]  symbols={args.symbols} quote={args.quote} days={args.days}")
    download(args.symbols, args.exchanges, args.quote, args.days)
