"""
═══════════════════════════════════════════════════════════════════════════════
  DATA — Lumibot bar adapter (OHLCV → clean pandas Series)
═══════════════════════════════════════════════════════════════════════════════

Thin, defensive adapter over ``Strategy.get_historical_prices`` that returns
plain pandas objects for the compute layers. Everything downstream (volatility,
forecasts) works on a close-price ``Series``; execution also needs volume.

The official feed is OHLCV bars only, delivered per-symbol at minute resolution.
Lumibot maintains the rolling window internally, so we simply request the last
``length`` bars each iteration and guard hard against missing / short data.
"""

from __future__ import annotations

import pandas as pd


def _bars_df(strategy, asset, length: int, timestep: str, quote) -> pd.DataFrame | None:
    """Fetch a bars DataFrame or None, swallowing data-source hiccups."""
    try:
        bars = strategy.get_historical_prices(asset, length, timestep=timestep, quote=quote)
    except Exception as exc:  # noqa: BLE001 — a single bad symbol must not kill the step
        strategy.log_message(f"[data] {getattr(asset, 'symbol', asset)} history error: {exc}")
        return None
    if bars is None or getattr(bars, "df", None) is None or bars.df.empty:
        return None
    return bars.df


def close_and_volume(strategy, asset, length: int, timestep: str, quote
                     ) -> tuple[pd.Series, pd.Series]:
    """Return (close, volume) Series aligned on the same index."""
    df = _bars_df(strategy, asset, length, timestep, quote)
    if df is None or "close" not in df.columns:
        empty = pd.Series(dtype=float)
        return empty, empty
    close = df["close"].astype(float)
    volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series(0.0, index=close.index)
    ok = close.notna()
    return close[ok], volume[ok]


# Map competition sleeptime codes to pandas resample rules.
_RESAMPLE_RULE = {"1M": "1min", "5M": "5min", "15M": "15min", "60M": "60min", "1D": "1D"}


def series_for_cadence(strategy, asset, cfg, quote) -> tuple[pd.Series, pd.Series]:
    """
    Fetch (close, volume) at the strategy cadence, choosing the right timestep:
    daily bars for a ``1D`` cadence (no resample), else minute bars resampled up.
    The submission runs at 1D; the resample path supports intraday cadences too.
    """
    if cfg.sleeptime == "1D":
        return close_and_volume(strategy, asset, cfg.history_bars, "day", quote)
    raw_c, raw_v = close_and_volume(strategy, asset, cfg.minute_fetch_length(), "minute", quote)
    return resample_to_cadence(raw_c, raw_v, cfg.sleeptime)


def resample_to_cadence(close: pd.Series, volume: pd.Series, sleeptime: str
                        ) -> tuple[pd.Series, pd.Series]:
    """
    Aggregate minute bars up to the strategy cadence so rule spans are counted
    in *cadence bars*, not minutes. Close → last, volume → sum. For a 1-minute
    cadence (or an unknown code) the series pass through unchanged.
    """
    rule = _RESAMPLE_RULE.get(sleeptime)
    if rule in (None, "1min") or close.empty:
        return close, volume
    c = close.resample(rule, label="right", closed="right").last().dropna()
    v = volume.resample(rule, label="right", closed="right").sum().reindex(c.index).fillna(0.0)
    return c, v
