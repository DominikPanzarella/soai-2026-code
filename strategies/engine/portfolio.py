"""
═══════════════════════════════════════════════════════════════════════════════
  PORTFOLIO — volatility targeting → target weights (Carver §9, long/flat)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* R. Carver, *Systematic Trading* §9 — position sizing & volatility targeting.

Formula (per instrument i, as fraction of capital)
--------------------------------------------------
    w_i = (f_i / f_target) · (τ · IDM · iw_i) / σ_i

    f_i     = combined forecast (±cap)         σ_i = annualised instrument vol
    f_target= target avg |forecast| (≈10)      τ   = annual vol target
    iw_i    = instrument weight (Σ = 1)         IDM = instrument diversification mult.

Then: clamp ≥ 0 (spot has no short leg), cap per name, and scale the book so
gross exposure ≤ gross_cap − cash_buffer. The forecast sign still matters: a
negative forecast → 0 weight → the capital sits in cash (the risk-off asset).
"""

from __future__ import annotations

from .config import RiskConfig


def target_weights(combined: dict[str, float],
                   ann_vol: dict[str, float],
                   instrument_weights: dict[str, float],
                   risk: RiskConfig,
                   forecast_target: float = 10.0,
                   idm: float | None = None,
                   class_map: dict[str, str] | None = None,
                   long_only: dict[str, bool] | None = None,
                   allow_short: bool = False) -> dict[str, float]:
    """
    Map combined forecasts + vols into capped target weights.

    ``idm`` overrides ``risk.idm``. ``class_map`` enables the per-class cap.
    ``long_only`` (symbol → bool) enables long/SHORT: instruments flagged False
    (shortable equities/ETFs) keep a signed weight when ``allow_short`` is set;
    crypto spot (True) is always clamped ≥ 0. Missing → clamped ≥ 0.
    """
    idm_val = float(idm) if idm is not None else risk.idm
    raw: dict[str, float] = {}
    for sym, f in combined.items():
        sigma = max(float(ann_vol.get(sym, 0.0) or 0.0), risk.vol_floor_annual)
        iw = instrument_weights.get(sym, 0.0)
        if iw <= 0.0 or sigma <= 0.0:
            raw[sym] = 0.0
            continue
        w = (float(f) / forecast_target) * (risk.vol_target_annual * idm_val * iw) / sigma
        # shortable only if the instrument allows it AND the regime permits (risk-off)
        shortable = (long_only is not None and not long_only.get(sym, True) and allow_short)
        if not shortable:
            w = max(0.0, w)
        w = max(-risk.max_weight_per_asset, min(w, risk.max_weight_per_asset))  # signed cap
        raw[sym] = w

    # ── per-asset-class concentration cap (on absolute exposure) ──────────
    if class_map and risk.max_class_conc > 0:
        by_class: dict[str, float] = {}
        for s, w in raw.items():
            by_class[class_map.get(s, s)] = by_class.get(class_map.get(s, s), 0.0) + abs(w)
        for cls, tot in by_class.items():
            if tot > risk.max_class_conc and tot > 0:
                scale = risk.max_class_conc / tot
                for s in raw:
                    if class_map.get(s, s) == cls:
                        raw[s] *= scale

    # ── scale gross (Σ|w|) to the budget net of the cash buffer ───────────
    gross = sum(abs(w) for w in raw.values())
    budget = max(0.0, risk.gross_cap - risk.cash_buffer)
    if gross > 0.0:
        # ``deploy_full`` scales UP as well as down → put the budget to work in the
        # selected winners instead of sitting in cash (the terminal-return driver).
        if risk.deploy_full or gross > budget:
            scale = budget / gross
            raw = {s: w * scale for s, w in raw.items()}
    return raw
