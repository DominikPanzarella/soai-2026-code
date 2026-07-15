"""
═══════════════════════════════════════════════════════════════════════════════
  EXECUTION — target weights → orders (buffer + volume cap + gross guard)
═══════════════════════════════════════════════════════════════════════════════

Turns target weights into Lumibot market orders while respecting the frictions
that matter on the official (spot) engine:

* **No-trade buffer** (Carver): skip rebalances smaller than ``no_trade_buffer``
  weight units, so we do not churn the book (and pay costs) on noise.
* **Volume-aware sizing**: the official engine caps each child order at a
  fraction of the bar's real minute-volume — oversized orders do not fill. We
  pre-cap order notional at ``volume_cap_frac · recent_volume · price``.
* **Gross guard (no leverage)**: per-asset buffers let winners drift up without
  being trimmed, so book gross can creep past 100% — impossible on spot. Sells
  are submitted first (freeing cash) and buys are scaled to a budget that keeps
  post-trade gross ≤ ``max_gross`` (and cash ≥ the buffer). This is what makes
  the strategy genuinely long/flat rather than accidentally levered.
"""

from __future__ import annotations

import pandas as pd

from .config import ExecConfig


def rebalance(strategy, target_w: dict[str, float], assets: dict, quotes: dict,
              prices: dict[str, float], volumes: dict[str, pd.Series],
              cfg: ExecConfig, max_gross: float = 0.97) -> list:
    """
    Build and submit the orders needed to move current → target weights.

    ``quotes`` maps symbol → quote Asset (crypto) or None (equities).
    ``max_gross`` caps total post-trade risky exposure as a fraction of PV.
    Returns a list of (symbol, side, qty, notional) tuples for logging.
    """
    pv = strategy.get_portfolio_value()
    if pv is None or pv <= 0:
        return []
    cash = strategy.get_cash()
    cash = float(cash) if cash is not None else 0.0

    # ── 1) build candidate trades (buffer + volume cap) ───────────────────
    sells: list = []   # (sym, notional<0, price, asset)
    buys: list = []    # (sym, notional>0, price, asset)
    risky_value = 0.0
    for sym, tgt in target_w.items():
        asset = assets.get(sym)
        price = prices.get(sym)
        if asset is None or price is None or price <= 0:
            continue

        pos = strategy.get_position(asset)
        held_qty = float(pos.quantity) if pos is not None else 0.0
        risky_value += abs(held_qty * price)          # gross (long/short) exposure
        cur_w = (held_qty * price) / pv
        drift = tgt - cur_w
        if abs(drift) < cfg.no_trade_buffer:
            continue

        notional = drift * pv
        vol = volumes.get(sym)
        if vol is not None and len(vol):
            recent = float(vol.tail(cfg.volume_lookback).mean())
            cap = cfg.volume_cap_frac * recent * price
            if cap > 0:
                notional = max(-cap, min(cap, notional))

        if abs(notional) < cfg.min_order_notional:
            continue
        (buys if notional > 0 else sells).append((sym, notional, price, asset))

    # ── 1b) exit sweep: fully liquidate holdings no longer targeted ────────
    # Symbols dropped from the dynamic selection are absent from ``target_w``;
    # without this they would never be sold (position leak) AND their exposure
    # would escape the ``risky_value`` gross accounting above, letting book gross
    # silently breach the no-leverage cap. Sweep the live positions, sell any that
    # are held but no longer targeted, and count them toward gross.
    targeted = set(target_w.keys())
    try:
        live_positions = strategy.get_positions() or []
    except Exception:  # noqa: BLE001 — a broker hiccup here must not kill the step
        live_positions = []
    for pos in live_positions:
        asset = getattr(pos, "asset", None)
        sym = getattr(asset, "symbol", None)
        if sym is None or sym in targeted or sym not in assets:
            continue                                   # targeted / cash-quote / off-universe
        held_qty = float(getattr(pos, "quantity", 0.0) or 0.0)
        if held_qty == 0.0:
            continue
        price = prices.get(sym)
        if price is None or price <= 0:
            lp = strategy.get_last_price(asset)
            price = float(lp) if lp else 0.0
        if price <= 0:
            continue
        risky_value += abs(held_qty * price)           # count the leak toward gross
        notional = -held_qty * price                   # full exit
        vol = volumes.get(sym)
        if vol is not None and len(vol):
            recent = float(vol.tail(cfg.volume_lookback).mean())
            cap = cfg.volume_cap_frac * recent * price
            if cap > 0:
                notional = max(-cap, notional)         # volume-cap the sell (notional < 0)
        if abs(notional) < cfg.min_order_notional:
            continue
        sells.append((sym, notional, price, asset))

    # ── 2) gross guard: scale buys so post-trade gross ≤ max_gross ─────────
    sells_total = sum(-n for _, n, _, _ in sells)
    buys_total = sum(n for _, n, _, _ in buys)
    # Additional risky exposure we may add after the sells free up room.
    buy_budget = pv * max_gross - (risky_value - sells_total)
    scale = 1.0
    if buys_total > 0 and buys_total > buy_budget:
        scale = max(0.0, buy_budget) / buys_total

    # ── 2b) cost speed-limit: cap total book turnover per rebalance ────────
    max_turn = getattr(cfg, "max_turnover_per_step", 0.0)
    if max_turn and max_turn > 0:
        turnover = (sells_total + buys_total * scale) / pv
        if turnover > max_turn:
            tscale = max_turn / turnover
            scale *= tscale
            sells = [(s, n * tscale, p, a) for s, n, p, a in sells]

    # ── 3) submit sells first, then (scaled) buys ─────────────────────────
    def _order(sym, notional, price, asset):
        qty = abs(notional) / price
        if qty <= 0 or abs(notional) < cfg.min_order_notional:
            return None
        side = "buy" if notional > 0 else "sell"
        quote = quotes.get(sym)
        if quote is not None:
            return strategy.create_order(asset, qty, side, quote=quote)
        return strategy.create_order(asset, qty, side)

    orders = []
    trace = []
    for sym, notional, price, asset in sells:
        o = _order(sym, notional, price, asset)
        if o is not None:
            orders.append(o)
            trace.append((sym, "sell", abs(notional) / price, notional))
    for sym, notional, price, asset in buys:
        n = notional * scale
        o = _order(sym, n, price, asset)
        if o is not None:
            orders.append(o)
            trace.append((sym, "buy", abs(n) / price, n))

    if orders:
        strategy.submit_orders(orders)
    return trace
