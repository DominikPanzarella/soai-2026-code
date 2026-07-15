"""
Daily multi-asset backtest → native Lumibot tearsheet for the WHOLE book.

The bundled ``backtest.py`` runs the crypto sleeve at 60M (only crypto has local
1-minute data). This harness instead runs the FULL universe (crypto + equities +
ETFs) on daily bars so Lumibot produces its standard QuantStats tearsheet for the
entire multi-asset portfolio.

To keep Lumibot's accounting single-currency (and avoid the mixed crypto/equity
quote issue), every instrument is registered as a USD ``STOCK`` here — crypto
price series are just BTC-USD etc. The strategy is told to match via
``parameters={"treat_all_as_stock": True, "sleeptime": "1D"}``. This affects the
LOCAL tearsheet only; the live competition run trades crypto as CRYPTO (also at 1D).

Data: run ``python research/download_daily.py --years 3`` first (writes
``data/daily/{ticker}.csv``). Output tearsheet HTML lands in ``logs/``.

    python backtest_daily.py
"""

from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from lumibot.backtesting import PandasDataBacktesting
from lumibot.entities import Asset, Data, TradingFee

from strategies.engine.instruments import load_universe
from strategies.strategy import Strategy

DAILY_DIR = Path(__file__).resolve().parent / "data" / "daily"
BUDGET = 1_000_000
BACKTEST_START = datetime(2024, 6, 1, tzinfo=timezone.utc)
BACKTEST_END = datetime(2026, 7, 10, tzinfo=timezone.utc)
PERCENT_FEE = 0.0005                      # 5 bps blended (daily turnover is low)
USD = Asset(symbol="USD", asset_type=Asset.AssetType.FOREX)


def _load(ticker: str) -> pd.DataFrame | None:
    path = DAILY_DIR / f"{ticker}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, usecols=["open", "high", "low", "close", "volume", "timestamp"])
    df["datetime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).drop(columns=["timestamp"]).set_index("datetime").sort_index()
    return df[["open", "high", "low", "close", "volume"]]


def run() -> None:
    instruments = load_universe(roles=("core", "convex"))
    pandas_data: dict[Asset, Data] = {}
    for ins in instruments:
        df = _load(ins.daily_ticker)
        if df is None or df.empty:
            print(f"[skip] {ins.symbol}: no daily CSV ({ins.daily_ticker})")
            continue
        asset = Asset(symbol=ins.symbol, asset_type=Asset.AssetType.STOCK)
        pandas_data[asset] = Data(asset, df, timestep="day", quote=USD)
    if not pandas_data:
        raise RuntimeError("No daily data — run research/download_daily.py first.")

    print(f"[INFO] Loaded {len(pandas_data)} daily instruments | window "
          f"{BACKTEST_START.date()} → {BACKTEST_END.date()}")

    fee = TradingFee(percent_fee=PERCENT_FEE, maker=True, taker=True)
    Strategy.run_backtest(
        PandasDataBacktesting,
        BACKTEST_START,
        BACKTEST_END,
        pandas_data=pandas_data,
        budget=BUDGET,
        quote_asset=USD,
        benchmark_asset=Asset(symbol="SPY", asset_type=Asset.AssetType.STOCK),
        parameters={"sleeptime": "1D", "treat_all_as_stock": True},
        buy_trading_fees=[fee],
        sell_trading_fees=[fee],
    )


if __name__ == "__main__":
    run()
