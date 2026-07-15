"""
═══════════════════════════════════════════════════════════════════════════════
  CONNORS RSI — cumulative short-RSI mean-reversion (catalog C1)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* Connors & Alvarez, *Short Term Trading Strategies That Work* (2008).
* Catalog C1 — the single best diversifier vs the trend book (negative
  correlation), OHLCV-only, cheap.

Formula
-------
    RSI_t     = Wilder RSI(close, rsi_len)
    cumRSI_t  = mean(RSI over last cum_bars)          (∈ [0,100], smoother than RSI-2)
    gate_t    = 1 if close_t > SMA(close, sma_gate)   (long-only trend gate)
    raw_t     = max(buy_threshold - cumRSI_t, 0)      (deeper oversold → larger)
    f_t       = clip(raw_t · scalar · gate_t, 0, cap)

Long/flat by construction: a stretched-low oscillator inside an uptrend builds a
long forecast; otherwise zero (capital parks in cash). No hard stops (they
historically hurt RSI-2) — risk is controlled by vol-target sizing + the gate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import ConnorsRSIConfig


def _wilder_rsi(close: pd.Series, length: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / length, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1.0 / length, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).fillna(50.0)


def connors_forecast(prices: pd.Series, cfg: ConnorsRSIConfig,
                     cap: float = 20.0) -> pd.Series:
    """Long/flat cumulative-RSI reversion forecast in [0, cap]."""
    prices = prices.astype(float)
    rsi = _wilder_rsi(prices, cfg.rsi_len)
    cum_rsi = rsi.rolling(cfg.cum_bars, min_periods=1).mean()

    raw = (cfg.buy_threshold - cum_rsi).clip(lower=0.0)
    fcast = raw * cfg.scalar

    if cfg.sma_gate and cfg.sma_gate > 0:
        sma = prices.rolling(cfg.sma_gate, min_periods=cfg.sma_gate // 2).mean()
        fcast = fcast.where(prices > sma, 0.0)

    return fcast.clip(0.0, cap)
