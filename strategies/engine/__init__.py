"""
Systematic trading engine for the SoAI 2026 competition.

A Carver-style, staged pipeline that turns OHLCV bars into target portfolio
weights and then into Lumibot orders:

    data → volatility → forecasts (±20) → combine (weights + FDM) →
    portfolio (vol target + IDM + cap + long/flat) → convex sleeve → execution

The package is import-safe (no network / API keys at import time) so the
official environment can ``from strategies.strategy import Strategy`` cleanly.
"""
