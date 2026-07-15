"""
═══════════════════════════════════════════════════════════════════════════════
  SoAI 2026 — participant entrypoint (Carver-style multi-asset engine)
═══════════════════════════════════════════════════════════════════════════════

The official environment imports ``Strategy`` from this module, so the class
name and import path (``from strategies.strategy import Strategy``) are fixed.

This file is a *thin orchestrator* over the staged engine in
:mod:`strategies.engine`, mirroring the pysystemtrade / carver_zorro pipeline:

    data → volatility → rules (forecasts ±20) → forecast combine (weights + FDM) →
    position sizing (vol target) → portfolio (handcrafted weights + IDM +
    per-class caps + long/flat) → convex sleeve → execution (buffer + vol cap)

Multi-asset by construction: the universe (crypto spot + US equities + ETFs) is
config-driven via ``strategies/config/universe.csv``. Instruments that have no
data on a given run (e.g. equities in a crypto-only local backtest) are skipped
by the warm-up guard, so the SAME code runs live and in any single-class backtest.

Long/flat: spot crypto (and, conservatively, equities) are traded long-or-flat;
a bearish forecast parks capital in cash. Heavy imports are deferred so
``import strategies.strategy`` needs no network or API keys.
"""

from __future__ import annotations

from lumibot.strategies import Strategy as _LumibotStrategy
from lumibot.entities import Asset


class Strategy(_LumibotStrategy):
    # ══════════════════════════════════════════════════════════════════════
    #  Lifecycle: setup
    # ══════════════════════════════════════════════════════════════════════
    def initialize(self):
        from strategies.engine.config import EngineConfig
        from strategies.engine.instruments import (
            load_universe, handcraft_weights, groups_map, class_map, long_only_map,
        )

        self.cfg = EngineConfig()
        # Optional overrides passed via Lumibot ``parameters`` (used by the local
        # daily multi-asset tearsheet harness; live run uses the defaults).
        params = getattr(self, "parameters", None) or {}
        if params.get("sleeptime"):
            self.cfg.sleeptime = params["sleeptime"]
        # ``treat_all_as_stock`` runs the whole universe in one USD account so the
        # local Lumibot tearsheet has clean single-currency accounting (avoids the
        # mixed crypto/equity quote issue). Live crypto still trades as CRYPTO.
        self._all_stock = bool(params.get("treat_all_as_stock", False))
        self.sleeptime = self.cfg.sleeptime

        core = load_universe(roles=self.cfg.universe_roles)
        convex = load_universe(roles=("convex",))
        self.instruments = {ins.symbol: ins for ins in core}
        self.convex_instruments = {ins.symbol: ins for ins in convex}

        self.crypto_quote = Asset(symbol=self.cfg.crypto_quote,
                                  asset_type=Asset.AssetType.CRYPTO)
        self.assets = {s: self._asset(ins) for s, ins in {**self.instruments,
                                                          **self.convex_instruments}.items()}
        self.quotes = {s: (None if self._all_stock else (self.crypto_quote if ins.is_crypto else None))
                       for s, ins in {**self.instruments, **self.convex_instruments}.items()}

        self.instrument_weights = handcraft_weights(core, self.cfg.macro_weights)  # sums to 1
        self.groups = groups_map(core)                      # symbol → cluster (class-aware XS)
        self.class_map = class_map(core)                    # symbol → asset class (caps)
        self.long_only = long_only_map(core)                # symbol → long/flat (crypto) vs shortable
        self._peak_pv = 0.0                                   # for the survival-floor drawdown

        self.log_message(
            f"Engine initialised: {len(core)} core + {len(convex)} convex instruments, "
            f"sleeptime={self.sleeptime}, vol_target={self.cfg.risk.vol_target_annual:.0%}"
        )

    def _asset(self, ins) -> Asset:
        if self._all_stock:
            return Asset(symbol=ins.symbol, asset_type=Asset.AssetType.STOCK)
        t = Asset.AssetType.CRYPTO if ins.is_crypto else Asset.AssetType.STOCK
        return Asset(symbol=ins.symbol, asset_type=t)

    # ══════════════════════════════════════════════════════════════════════
    #  Lifecycle: per-step decision making
    # ══════════════════════════════════════════════════════════════════════
    def on_trading_iteration(self):
        import pandas as pd
        from strategies.engine import data, volatility, portfolio, execution
        from strategies.engine.instruments import idm_from_returns
        from strategies.engine.convex import convex_weights
        from strategies.engine.combine import combine_forecasts
        from strategies.engine.overlays import (last_vol_managed_mult, market_breadth_last,
                                                 regime_gross_scalar, drawdown_scalar)
        from strategies.engine.forecasts.trend_ewmac import ewmac_forecast
        from strategies.engine.forecasts.breakout import breakout_forecast
        from strategies.engine.forecasts.mean_reversion import mean_reversion_forecast
        from strategies.engine.forecasts.connors_rsi import connors_forecast
        from strategies.engine.forecasts.xs_momentum import xs_momentum_forecast
        from strategies.engine.forecasts.residual_momentum import residual_momentum_forecast
        from strategies.engine.forecasts.lottery_max import max_lottery_forecast
        from strategies.engine.forecasts.safer_fast_mr import safer_fast_mr_forecast
        from strategies.engine.forecasts.acceleration import acceleration_forecast
        from strategies.engine.forecasts.mtf_pullback import mtf_pullback_forecast
        from strategies.engine.forecasts.kama import kama_forecast
        from strategies.engine.forecasts.residual_mr import residual_mr_forecast
        from strategies.engine.forecasts.leadlag import leadlag_forecast
        from strategies.engine.forecasts.intermarket_div import intermarket_div_forecast
        from strategies.engine.forecasts.vol_breakout import vol_breakout_forecast

        cfg = self.cfg
        # Warm-up from the ACTIVE rules (vol σ + the EWMAC trend anchor), not from the
        # disabled connors/mean-reversion rules. Kept < the shortest convex driver's
        # history (FNGU ~360 daily bars) so the leveraged names are never dropped.
        min_bars = max(50, cfg.risk.vol_span, cfg.ewmac.pairs[-1][1] // 2)

        # ── 1) data + volatility (core universe) ──────────────────────────
        closes, volumes, prices, ann_vol = {}, {}, {}, {}
        for sym, ins in self.instruments.items():
            close, vol = data.series_for_cadence(self, self.assets[sym], cfg, self.quotes[sym])
            if len(close) < min_bars:
                continue
            closes[sym] = close
            volumes[sym] = vol
            prices[sym] = float(close.iloc[-1])
            per_bar = volatility.last_vol(close, cfg.risk.vol_span, floor=0.0)
            bpy = cfg.bars_per_year(ins.is_crypto)
            ann_vol[sym] = (volatility.annualise(per_bar, bpy)
                            if per_bar > 0 else cfg.risk.vol_floor_annual)
        if not closes:
            return

        # ── 2) class-aware cross-sectional rules (whole basket) ───────────
        is_crypto_map = {s: self.instruments[s].is_crypto for s in closes}
        xs = xs_momentum_forecast(closes, cfg.xs_momentum, cap=cfg.forecast_cap, groups=self.groups)
        resid = residual_momentum_forecast(closes, cfg.residual_mom, cap=cfg.forecast_cap, groups=self.groups)
        maxlot = max_lottery_forecast(closes, cfg.max_lottery, cap=cfg.forecast_cap, groups=self.groups)
        resid_mr = residual_mr_forecast(closes, cfg.residual_mr, cap=cfg.forecast_cap, groups=self.groups)
        leadlag = leadlag_forecast(closes, cfg.leadlag, cap=cfg.forecast_cap, groups=self.groups)
        intmkt = intermarket_div_forecast(closes, cfg.intermarket_div, cap=cfg.forecast_cap,
                                          groups=self.groups, is_crypto=is_crypto_map)

        # ── 3) rules → combined forecast (soft-capped ±20) ────────────────
        rule_w = {
            "ewmac": cfg.ewmac.weight, "acceleration": cfg.acceleration.weight,
            "breakout": cfg.breakout.weight, "mr": cfg.mean_reversion.weight,
            "connors": cfg.connors.weight, "safer_mr": cfg.safer_fast_mr.weight,
            "xs": cfg.xs_momentum.weight, "residual": cfg.residual_mom.weight,
            "maxlot": cfg.max_lottery.weight, "mtf": cfg.mtf_pullback.weight,
            "kama": cfg.kama.weight, "residual_mr": cfg.residual_mr.weight,
            "leadlag": cfg.leadlag.weight, "intmkt": cfg.intermarket_div.weight,
            "volbrk": cfg.vol_breakout.weight,
        }
        combined = {}
        for sym, close in closes.items():
            is_crypto = self.instruments[sym].is_crypto
            bpy = cfg.bars_per_year(is_crypto)
            # G1 vol-managed multiplier applied to directional trend/momentum only.
            vm = last_vol_managed_mult(close, cfg.vol_managed, cfg.risk.vol_span, bpy)

            def _apply(name, val):
                return val * vm if name in cfg.vol_managed.applies_to else val

            def _last(series):
                return float(series.iloc[-1]) if series is not None and len(series) else 0.0

            forecasts = {
                "ewmac": _apply("ewmac", ewmac_forecast(close, cfg.ewmac, cfg.risk.vol_span, cfg.forecast_cap).iloc[-1]),
                "acceleration": _apply("ewmac", acceleration_forecast(close, cfg.ewmac, cfg.acceleration, cfg.risk.vol_span, cfg.forecast_cap).iloc[-1]),
                "breakout": _apply("breakout", breakout_forecast(close, cfg.breakout, cfg.forecast_cap).iloc[-1]),
                "mr": mean_reversion_forecast(close, cfg.mean_reversion, cfg.forecast_cap).iloc[-1],
                "connors": connors_forecast(close, cfg.connors, cfg.forecast_cap).iloc[-1],
                "safer_mr": safer_fast_mr_forecast(close, cfg.safer_fast_mr, cfg.risk.vol_span, bpy, cfg.forecast_cap).iloc[-1],
                "xs": _apply("xs", _last(xs.get(sym))),
                "residual": _last(resid.get(sym)),
                "maxlot": _last(maxlot.get(sym)),
                "mtf": _apply("ewmac", mtf_pullback_forecast(close, cfg.mtf_pullback, cfg.forecast_cap).iloc[-1]),
                "kama": _apply("ewmac", kama_forecast(close, cfg.kama, cfg.forecast_cap).iloc[-1]),
                "residual_mr": _last(resid_mr.get(sym)),
                "leadlag": _last(leadlag.get(sym)),
                "intmkt": _last(intmkt.get(sym)),
                "volbrk": _apply("ewmac", vol_breakout_forecast(close, cfg.vol_breakout, cfg.forecast_cap).iloc[-1]),
            }
            combined[sym] = combine_forecasts(forecasts, rule_w, cfg.risk.fdm,
                                              cfg.forecast_cap, soft=cfg.soft_cap)

        # ── 3b) dynamic instrument selection — trade only the trending winners ─
        from strategies.engine.selection import select_symbols
        from strategies.engine.instruments import macro_class
        macro = {s: macro_class(self.instruments[s].asset_class) for s in closes}
        bpy_map = {s: cfg.bars_per_year(self.instruments[s].is_crypto) for s in closes}
        # DAILY reselect (every iteration). A throttle (weekly/biweekly) was A/B'd in the
        # engine and HURT badly (+140%->+66/71%): the fast daily rotation onto fresh winners
        # — esp. the 3x ETFs — IS the edge; freezing the universe loses it. Kept daily.
        selected = set(select_symbols(closes, macro, cfg.selection,
                                      cfg.selection.sigma_target, bpy_map))
        combined = {s: v for s, v in combined.items() if s in selected}
        if not combined:
            return

        # ── 4) position sizing + portfolio (handcraft weights, IDM, caps) ─
        iw = {s: self.instrument_weights.get(s, 0.0) for s in combined}
        tot = sum(iw.values())
        if tot > 0:
            iw = {s: w / tot for s, w in iw.items()}

        idm = None
        if cfg.risk.idm_estimate and len(closes) >= 2:
            rets = pd.DataFrame({s: closes[s].pct_change(fill_method=None) for s in closes})
            idm = idm_from_returns(rets.tail(500), iw, cap=cfg.risk.idm_cap)

        # tactical hedge: allow the equity short leg only in a risk-off regime
        breadth = market_breadth_last(closes, cfg.risk.breadth_ma)
        allow_short = bool(cfg.risk.tactical_short and breadth < cfg.risk.breadth_thr)
        core = portfolio.target_weights(combined, ann_vol, iw, cfg.risk,
                                        cfg.forecast_target, idm=idm, class_map=self.class_map,
                                        long_only={s: self.long_only.get(s, True) for s in closes},
                                        allow_short=allow_short)

        # ── 4b) convex upside sleeve — ranked over the DEDICATED convex names ─
        # (bug fix: previously ranked over the CORE closes, so COIN/MSTR/KWEB/GDX
        # never traded and the sleeve just doubled up core momentum names).
        conv_closes, conv_prices, conv_volumes = {}, {}, {}
        for sym, ins in self.convex_instruments.items():
            cc, cv = data.series_for_cadence(self, self.assets[sym], cfg, self.quotes[sym])
            if len(cc) < min_bars:
                continue
            conv_closes[sym] = cc
            conv_volumes[sym] = cv
            conv_prices[sym] = float(cc.iloc[-1])
        # execution needs price/volume for every convex name it may enter OR exit
        prices.update(conv_prices)
        volumes.update(conv_volumes)
        sleeve = convex_weights(conv_closes, cfg.convex)
        frac = cfg.convex.fraction if (cfg.convex.enabled and sleeve) else 0.0
        tgt = {s: w * (1.0 - frac) for s, w in core.items()}
        for s in conv_closes:                     # 0-target rotated-out convex names → sold
            tgt.setdefault(s, 0.0)
        for s, w in sleeve.items():
            tgt[s] = tgt.get(s, 0.0) + w

        # ── 4c) tournament risk scaling: vol-conditioned regime × survival floor ─
        pv_now = self.get_portfolio_value() or 0.0
        self._peak_pv = max(self._peak_pv, pv_now)
        dd = (pv_now / self._peak_pv - 1.0) if self._peak_pv > 0 else 0.0
        regime_mult = regime_gross_scalar(closes, cfg.risk.regime_target_vol,
                                          cfg.risk.regime_lo, cfg.risk.regime_vol_span,
                                          cfg.bars_per_year(True))
        dd_mult = drawdown_scalar(dd, cfg.risk.dd0, cfg.risk.dd_max, cfg.risk.dd_min)
        risk_scalar = regime_mult * dd_mult
        if risk_scalar < 1.0:
            tgt = {s: w * risk_scalar for s, w in tgt.items()}

        # ── 5) execution (buffer + volume cap + no-leverage gross guard) ──
        max_gross = cfg.risk.gross_cap - cfg.risk.cash_buffer
        trace = execution.rebalance(self, tgt, self.assets, self.quotes,
                                    prices, volumes, cfg.execution, max_gross=max_gross)

        # ── 6) log ────────────────────────────────────────────────────────
        pv = self.get_portfolio_value()
        active = {s: round(w, 3) for s, w in tgt.items() if abs(w) > 1e-4}  # incl. tactical shorts
        self.log_message(
            f"pv=${pv:,.0f} idm={idm if idm else cfg.risk.idm:.2f} "
            f"targets={active} orders={len(trace)}"
        )
