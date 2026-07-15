"""
═══════════════════════════════════════════════════════════════════════════════
  INSTRUMENTS — config-driven multi-asset universe (Carver instrument stage)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* pysystemtrade instrument config: data/futures/csvconfig/instrumentconfig.csv
  (Instrument, AssetClass, Pointsize, Currency, costs, Region).
* carver_zorro: Data/Carver/config/instruments_apex.csv (class, ticker,
  instrument_weight, cost_sr, long_only, ...), handcrafting = "equal asset-class
  risk weight".

What this provides
------------------
A CSV-driven universe (``strategies/config/universe.csv``) parsed into
``Instrument`` records carrying the asset-class metadata every downstream stage
needs, plus two Carver portfolio-construction helpers:

* ``handcraft_weights`` — top-down handcrafting: split risk equally across
  asset-class GROUPS, then equally within each group. This stops the 10-name
  crypto sleeve from dominating simply because it has more instruments.
* ``idm_from_returns`` — Instrument Diversification Multiplier estimated from
  the instrument return-correlation matrix: IDM = 1 / sqrt(wᵀ C w), capped.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
UNIVERSE_CSV = CONFIG_DIR / "universe.csv"


@dataclass(frozen=True)
class Instrument:
    symbol: str            # canonical / intraday ticker (e.g. "BTC", "SPY")
    daily_ticker: str      # yfinance daily ticker (e.g. "BTC-USD", "SPY")
    asset_class: str       # CRYPTO / EQUITY / METAL / ENERGY / BOND / INTL_EQUITY / LEVERAGED
    group: str             # correlation cluster for handcrafting
    lumibot_type: str      # "crypto" or "stock"
    long_only: bool
    cost_bps: float
    role: str              # "core" or "convex"
    active: bool

    @property
    def is_crypto(self) -> bool:
        return self.lumibot_type == "crypto"


# ── load ──────────────────────────────────────────────────────────────────
def load_universe(path: Path = UNIVERSE_CSV, roles: tuple[str, ...] = ("core",)
                  ) -> list[Instrument]:
    """Parse the universe CSV into active Instruments filtered by ``roles``."""
    out: list[Instrument] = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            if int(row["active"]) != 1:
                continue
            if row["role"] not in roles:
                continue
            out.append(Instrument(
                symbol=row["symbol"].strip(),
                daily_ticker=row["daily_ticker"].strip(),
                asset_class=row["asset_class"].strip(),
                group=row["group"].strip(),
                lumibot_type=row["lumibot_type"].strip(),
                long_only=bool(int(row["long_only"])),
                cost_bps=float(row["cost_bps"]),
                role=row["role"].strip(),
                active=True,
            ))
    return out


# Macro asset-class clustering for handcrafting (equal risk per macro class).
_MACRO = {
    "CRYPTO": "crypto",
    "EQUITY": "equity", "INTL_EQUITY": "equity", "LEVERAGED": "equity",
    "METAL": "commodity", "ENERGY": "commodity",
    "BOND": "bond",
}


def macro_class(asset_class: str) -> str:
    return _MACRO.get(asset_class, "other")


# ── handcrafting (Carver) ──────────────────────────────────────────────────
def handcraft_weights(instruments: list[Instrument],
                      macro_weights: dict[str, float] | None = None
                      ) -> dict[str, float]:
    """
    Hierarchical handcrafted instrument weights. Split a risk budget across MACRO
    classes (crypto / equity / commodity / bond), then equally within each class.
    Sums to 1.

    ``macro_weights``: per-macro-class budget. If None, equal risk per class
    (pure Carver handcrafting). A return-tilted profile (overweight crypto/equity)
    is used for the terminal-return tournament posture. Grouping by macro class
    (not the fine ``group`` field) avoids a singleton fine-group grabbing a share.
    """
    if not instruments:
        return {}
    macro: dict[str, list[str]] = {}
    for ins in instruments:
        macro.setdefault(macro_class(ins.asset_class), []).append(ins.symbol)

    if macro_weights:
        budget = {m: float(macro_weights.get(m, 0.0)) for m in macro}
    else:
        budget = {m: 1.0 for m in macro}
    total = sum(budget.values()) or 1.0

    weights: dict[str, float] = {}
    for m, syms in macro.items():
        m_w = budget[m] / total
        per = m_w / len(syms) if syms else 0.0
        for s in syms:
            weights[s] = per
    return weights


def idm_from_returns(returns: pd.DataFrame, weights: dict[str, float],
                     cap: float = 2.5, floor: float = 1.0) -> float:
    """
    Instrument Diversification Multiplier from the return-correlation matrix:
        IDM = 1 / sqrt(wᵀ C w),  clamped to [floor, cap].
    ``returns`` columns must cover ``weights`` keys; missing → dropped & renorm.
    """
    cols = [s for s in weights if s in returns.columns]
    if len(cols) < 2:
        return floor
    w = np.array([weights[s] for s in cols], dtype=float)
    if w.sum() <= 0:
        return floor
    w = w / w.sum()
    corr = returns[cols].corr().to_numpy()
    corr = np.nan_to_num(corr, nan=0.0)
    np.fill_diagonal(corr, 1.0)
    denom = float(np.sqrt(max(w @ corr @ w, 1e-9)))
    return float(np.clip(1.0 / denom, floor, cap))


def groups_map(instruments: list[Instrument]) -> dict[str, str]:
    """symbol → asset-class group (for class-aware cross-sectional rules)."""
    return {ins.symbol: ins.group for ins in instruments}


def class_map(instruments: list[Instrument]) -> dict[str, str]:
    """symbol → asset_class (for per-class concentration caps)."""
    return {ins.symbol: ins.asset_class for ins in instruments}


def long_only_map(instruments: list[Instrument]) -> dict[str, bool]:
    """symbol → long_only flag (crypto spot = True; shortable equities = False)."""
    return {ins.symbol: ins.long_only for ins in instruments}
