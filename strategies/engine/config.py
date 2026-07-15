"""
═══════════════════════════════════════════════════════════════════════════════
  CONFIG — all tunable knobs for the systematic engine (Carver-framed)
═══════════════════════════════════════════════════════════════════════════════

Reference
---------
* R. Carver, *Systematic Trading* (2015): forecast scaling (§7), forecast
  combination + FDM (§8), volatility targeting & IDM (§9), position buffering.
* R. Carver, *Advanced Futures Trading Strategies* (2023): trend / breakout /
  mean-reversion rule families.

Design
------
Every default lives in a dataclass, never inline in the logic modules. The
top-level :class:`EngineConfig` composes the sub-configs. The engine is
**long/flat** (spot crypto cannot be shorted): direction rules still emit a
signed ±20 forecast; the portfolio clamps crypto to ≥ 0 (spot long/flat) and allows
a breadth-gated tactical short on shortable equities/ETFs in risk-off regimes.

Tournament posture
------------------
The competition scores a single metric — Terminal Return over one month — so the
book is FULLY DEPLOYED (~0.97 gross, no leverage) and concentrated on the selected
momentum winners, with convexity from eligible 3x leveraged ETFs. Note: ``deploy_full``
makes ``vol_target_annual`` and the IDM no-ops (they cancel in the gross renorm), and
the standalone convex sleeve is disabled after an A/B — see the respective configs.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ══════════════════════════════════════════════════════════════════════════
#  Forecast-rule sub-configs
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class ForecastConfig:
    """Base for every forecast rule. ``weight`` is its share in the combine."""
    weight: float = 1.0


# Family-budget weights (Carver forecast weights, catalog §4.2):
#   trend ~0.40 | breakout ~0.12 | reversion ~0.22 | xs-momentum ~0.18 | lottery ~0.08
# combine() renormalises over available rules, so these are relative.

@dataclass
class EWMACConfig(ForecastConfig):
    """
    Trend via EWMA crossover.  raw = (EWMA_fast - EWMA_slow) / σ_price
    scaled by ``scalar`` to a target average absolute forecast of ~10.

    ``pairs``: list of (fast_span, slow_span) in *bars* of the base timeframe.
    ``scalars``: Carver forecast scalar per pair (parallel list).
    """
    weight: float = 0.50        # TREND family (anchor; absorbed the retired low-MAX weight)
    pairs: tuple[tuple[int, int], ...] = ((8, 32), (16, 64), (32, 128), (64, 256))
    scalars: tuple[float, ...] = (5.95, 4.10, 2.79, 1.91)


@dataclass
class BreakoutConfig(ForecastConfig):
    """
    Donchian-style breakout: position of price within its rolling min/max
    channel, smoothed and scaled to ±20.  ``windows`` in bars.
    """
    weight: float = 0.0        # BREAKOUT family (best standalone Sharpe)
    windows: tuple[int, ...] = (40, 80, 160, 320)
    smooth_frac: float = 0.25   # EWMA smoothing span = smooth_frac * window
    scalar: float = 32.0        # maps normalized channel pos (~±0.5) into ±10


@dataclass
class MeanReversionConfig(ForecastConfig):
    """
    Fast mean-reversion: negative z-score of price vs its EWMA, capturing
    intraday chop. Sign is *contrarian* (stretched-up → negative forecast).
    """
    weight: float = 0.0        # REVERSION (plain z-score; small — safer_fast_mr is primary)
    span: int = 32              # EWMA span (bars) for the mean
    vol_span: int = 32          # EWMA span for the normalising vol
    scalar: float = 6.0         # scales z-score into ±10
    min_abs_trend: float = 0.0  # optional gating hook (0 = always on)


@dataclass
class ConnorsRSIConfig(ForecastConfig):
    """
    C1 — Connors cumulative-RSI mean-reversion (catalog C1). Long-only, gated
    above a slow SMA. cumRSI = sum of RSI(close, rsi_len) over ``cum_bars``;
    stretched-low cumRSI → long forecast. The single best diversifier vs trend.
    """
    weight: float = 0.00        # DISABLED: negative standalone Sharpe on 3y sample
    rsi_len: int = 3            # (kept for the code path; a regime diversifier for later)
    cum_bars: int = 2
    buy_threshold: float = 40.0   # cumRSI below this → long signal builds
    sma_gate: int = 200           # only long when close > SMA(sma_gate); 0 = off
    scalar: float = 0.30          # maps (buy_threshold - cumRSI) into ~±10


@dataclass
class XSMomentumConfig(ForecastConfig):
    """
    Cross-sectional momentum across the crypto basket: demeaned lookback
    return, ranked, mapped to ±20 (long strongest, flat/short weakest — the
    negative leg is clamped at the portfolio layer for spot).
    """
    weight: float = 0.12        # XS-MOMENTUM family (shared with residual)
    lookback: int = 480         # bars
    scalar: float = 20.0        # scales demeaned z of returns into ±10


@dataclass
class ResidualMomConfig(ForecastConfig):
    """
    D4 — Residual (idiosyncratic) cross-sectional momentum (catalog D4). Strip
    market/BTC beta, then rank the residual trend: the best-diversifying
    momentum variant vs the trend book. Beta from a rolling regression.
    """
    weight: float = 0.0        # XS-MOMENTUM family (shared with xs)
    lookback: int = 240         # bars for the residual-return window
    beta_window: int = 240      # bars for the rolling market-beta estimate
    scalar: float = 18.0        # scales cross-sectional z of residual mom into ±10


@dataclass
class MaxLotteryConfig(ForecastConfig):
    """
    F1 — MAX / lottery-demand (catalog F1). Cross-sectional: long the LOW-MAX
    names (avoid lottery-like coins). max_ret = max single-bar return over
    ``lookback``; low cross-sectional rank → long. A new orthogonal axis.
    """
    weight: float = 0.0         # RETIRED: low-MAX longs the CALMEST names — anti-convex for a
                                # variance-rewarding 1-month tournament (Bali/Grobys premium is an
                                # equilibrium-Sharpe anomaly). Weight moved to EWMAC trend anchor.
    lookback: int = 168         # bars (~7 days at 60M)
    scalar: float = 20.0        # maps (1 - 2*rank) into ±20


@dataclass
class SaferFastMRConfig(ForecastConfig):
    """
    Safer fast mean-reversion (Carver AFTS): fast reversion taken only WITH the
    trend and attenuated in high-vol regimes. Best terminal-return reversion keeper.
    """
    weight: float = 0.2        # REVERSION family (primary)
    span: int = 10              # fast EWMA for the deviation
    vol_span: int = 32
    fast_trend: int = 16        # regime filter (buy dips only in uptrend)
    slow_trend: int = 64
    scalar: float = 4.0         # scales the fast z into ~10
    vol_target_annual: float = 0.80   # attenuation reference


@dataclass
class AccelerationConfig(ForecastConfig):
    """Acceleration = ΔEWMAC forecast over N bars (Carver AFTS)."""
    weight: float = 0.0        # TREND family (near-free diversifier)
    N: int = 16
    scalar: float = 1.90


# ── book-v3 top-6 additions ────────────────────────────────────────────────
@dataclass
class MTFPullbackConfig(ForecastConfig):
    """v3 #1 — multi-timeframe pullback-continuation: buy dips WITH the HTF trend."""
    weight: float = 0.0
    htf_span: int = 200         # higher-timeframe trend gate (bars)
    fast_span: int = 20         # working-timeframe fast MA (measures the dip)
    vol_span: int = 32
    scalar: float = 3.0         # scales pullback depth (z) into ~10


@dataclass
class ResidualMRConfig(ForecastConfig):
    """v3 #2 — regression-residual (beta-neutral) short-term mean-reversion."""
    weight: float = 0.0
    lookback: int = 24          # short residual window (bars)
    beta_window: int = 240
    scalar: float = 14.0


@dataclass
class LeadLagConfig(ForecastConfig):
    """v3 #3 — intraday intermarket lead-lag: leader (BTC) → laggard catch-up."""
    weight: float = 0.08
    lookback: int = 6           # bars for the leader/laggard return gap
    leader: str = "BTC"
    scalar: float = 20.0


@dataclass
class IntermarketDivConfig(ForecastConfig):
    """v3 #4 — intermarket divergence: fade the relative-price gap vs a benchmark."""
    weight: float = 0.0
    span: int = 48              # EWMA of the relative-price ratio
    scalar: float = 6.0
    crypto_benchmark: str = "BTC"
    equity_benchmark: str = "SPY"


@dataclass
class KAMAConfig(ForecastConfig):
    """v3 #6 — Kaufman Adaptive MA slope (adaptive-trend cell)."""
    weight: float = 0.0
    er_window: int = 20         # efficiency-ratio window
    fast: int = 2               # fast SC bound
    slow: int = 30              # slow SC bound
    vol_span: int = 32
    scalar: float = 8.0


@dataclass
class VolBreakoutConfig(ForecastConfig):
    """Volatility-channel (Keltner) breakout — the VOLATILITY family forecast."""
    weight: float = 0.10
    band_span: int = 40         # EWMA mid-line
    vol_span: int = 32
    k: float = 2.0              # channel width in realized-vol units
    scalar: float = 20.0


# ══════════════════════════════════════════════════════════════════════════
#  Risk / portfolio / execution sub-configs
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class RiskConfig:
    """Volatility targeting and position limits (Carver §9 + tournament tilt)."""
    vol_target_annual: float = 0.80   # terminal-return posture: deploy capital, less cash drag
    idm: float = 2.5                  # fallback IDM (used until estimated from correlations)
    idm_estimate: bool = True         # estimate IDM from instrument return correlations
    idm_cap: float = 2.5              # clamp on the estimated IDM
    fdm: float = 1.2                  # forecast diversification multiplier
    max_weight_per_asset: float = 0.35
    max_class_conc: float = 0.60      # allow crypto/equity to dominate (return-tilted)
    cash_buffer: float = 0.03         # keep ≥3% cash
    gross_cap: float = 1.00           # spot/cash → no leverage
    vol_span: int = 32                # EWMA span for σ% (bars)
    vol_floor_annual: float = 0.10    # floor on σ to avoid blow-up sizing
    deploy_full: bool = True          # scale the book UP to the gross budget (deploy cash into
                                      # the selected winners) — the return driver with selection
    # Tactical hedge: shortable equities go long-only in risk-ON regimes and are
    # allowed a short leg ONLY when market breadth is risk-OFF (avoids the
    # bull-market short drag while keeping downside diversification).
    tactical_short: bool = True
    breadth_ma: int = 100             # bars for each asset's trend filter
    breadth_thr: float = 0.35         # risk-off when < this fraction are above their MA
    # Regime gross scalar — NEUTRALISED (regime_lo=1.0 => always 1.0). The metric is
    # path-independent terminal return with NO drawdown penalty, so a lagging realised-
    # vol scalar can only cut exposure into strength (expected-negative). Two de-risk
    # overlays were measured and both cost return for no benefit; the tournament-correct
    # move is to REMOVE, not add, gross de-risking. Kept as a no-op knob for research.
    regime_target_vol: float = 0.30
    regime_lo: float = 1.00
    regime_vol_span: int = 20
    # Survival floor — CATASTROPHIC KILL-SWITCH ONLY. The one legitimate reason to cut
    # gross is the "a blow-up won't podium" elimination tail, so the ramp engages only
    # deep in the loss zone (mult=1 above -30%, floors to 0.40 by -50%). It no longer
    # bleeds return on ordinary, recoverable dips (that was pure drag for this metric).
    dd0: float = 0.30
    dd_max: float = 0.50
    dd_min: float = 0.40
    # HARD catastrophic kill-switch: below this drawdown from the running peak, fully
    # liquidate to cash (one-shot) — anti-elimination guard for the single-month terminal
    # measurement. Distinct from the gradual floor above: binary, fires only in a true
    # disaster, so it can't "sell low then drag the recovery" across ordinary dips.
    dd_kill: float = 0.35
    # Data-safety guard: if fewer than this many instruments have enough live history,
    # hold cash instead of trading a degenerate universe.
    min_tradeable: int = 5


@dataclass
class SelectionConfig:
    """Dynamic instrument selection — trade only the top-N trending names per class."""
    enabled: bool = True
    lookback: int = 90          # trailing bars for the selection metrics
    nmax_crypto: int = 4
    nmax_equity: int = 8
    vol_band_lo: float = 0.4    # keep names within [lo,hi]*sigma_target
    vol_band_hi: float = 6.0
    sigma_target: float = 0.35
    # NOTE: reselect cadence is DAILY (every iteration). A weekly/biweekly throttle was
    # A/B'd in the engine and hurt (+140%->+66/71%) — the fast daily rotation is the edge.


@dataclass
class VolManagedConfig:
    """
    G1 — vol-managed / crash-managed momentum overlay (catalog G1). Scales
    trend/breakout/xs-momentum forecasts by (target_vol / realised_vol),
    clamped: cuts risk when vol spikes (kills the left tail, adds convexity).
    Applied to directional-trend forecasts only, NOT reversion/pairs, and
    BEFORE the ±20 cap. Excluded from the portfolio vol-target denominator.
    """
    enabled: bool = True
    target_vol_annual: float = 0.80   # matches the higher vol target (less de-risking)
    clip_lo: float = 0.30
    clip_hi: float = 2.50
    applies_to: tuple[str, ...] = ("ewmac", "breakout", "xs")


@dataclass
class ConvexConfig:
    """Convex upside sleeve carved out of total capital.

    DISABLED: a leak-free A/B (Jul 2026) showed the sleeve DILUTES the tournament
    edge — carving 30% from the concentrated momentum core into a COIN/MSTR/KWEB/GDX
    basket cut total return +140%->+93%, Sharpe 1.79->1.25, and thinned the right
    tail (P(month>+20%) 4%->0%). Wiring is fixed and kept for research; left off."""
    enabled: bool = False
    fraction: float = 0.30            # share of capital in the convex sleeve (aggressive)
    top_n: int = 3                    # concentrate on N strongest names
    momentum_lookback: int = 90       # bars for the ranking signal (=90 days at the 1D cadence;
                                      # was 480 bars ≈ 1.9y at 1D → the sleeve was near-static)
    risk_off_to_cash: bool = True     # sleeve → cash when regime is negative


@dataclass
class ExecConfig:
    """Order generation: no-trade buffer + volume-aware sizing."""
    no_trade_buffer: float = 0.05     # position inertia: rebalance only if |Δweight| > buffer
    volume_cap_frac: float = 0.05     # cap order notional ≤ frac * recent bar volume·price
    volume_lookback: int = 20         # bars used to estimate available liquidity
    min_order_notional: float = 25.0  # skip dust orders (quote currency)
    max_turnover_per_step: float = 0.20  # cost speed-limit: cap total book turnover per rebalance


# ══════════════════════════════════════════════════════════════════════════
#  Top-level engine config
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class EngineConfig:
    """Everything the engine needs, in one place."""

    # ── universe ──────────────────────────────────────────────────────────
    # The tradable universe is config-driven via strategies/config/universe.csv
    # (see engine/instruments.py). ``universe_roles`` selects which sleeves the
    # core engine trades; the convex sleeve pulls "convex" role names separately.
    universe_roles: tuple[str, ...] = ("core",)
    crypto_quote: str = "USD"                     # Lumibot crypto quote asset

    # Return-tilted macro-class risk budget for handcrafting (terminal-return
    # posture): overweight crypto+equity, keep bonds/commodity as small
    # diversifiers. Set all equal to recover pure equal-risk Carver handcrafting.
    # Bonds removed for the terminal-return tournament: cash (the long/flat
    # risk-off asset) already covers downside, and bonds only dilute return.
    # Redeployed to the return drivers (crypto / equity), small commodity tilt.
    macro_weights: dict = field(default_factory=lambda: {
        "crypto": 0.30, "equity": 0.55, "commodity": 0.15,
    })

    # ── cadence ───────────────────────────────────────────────────────────
    sleeptime: str = "1D"                         # 1M/5M/15M/60M/1D — DAILY: matches the
                                                  # validated tearsheet (selection.lookback=90 => 90
                                                  # calendar days). At 60M it would be 90 bars ≈ 3.75
                                                  # days — an UNvalidated, far noisier signal.
    history_bars: int = 600                       # rolling buffer length per asset

    # ── forecast rules ────────────────────────────────────────────────────
    ewmac: EWMACConfig = field(default_factory=EWMACConfig)                    # trend
    breakout: BreakoutConfig = field(default_factory=BreakoutConfig)          # breakout
    mean_reversion: MeanReversionConfig = field(default_factory=MeanReversionConfig)  # reversion
    connors: ConnorsRSIConfig = field(default_factory=ConnorsRSIConfig)       # reversion (C1)
    xs_momentum: XSMomentumConfig = field(default_factory=XSMomentumConfig)   # xs-momentum
    residual_mom: ResidualMomConfig = field(default_factory=ResidualMomConfig)  # xs-momentum (D4)
    max_lottery: MaxLotteryConfig = field(default_factory=MaxLotteryConfig)   # lottery (F1)
    safer_fast_mr: SaferFastMRConfig = field(default_factory=SaferFastMRConfig)  # reversion (Carver)
    acceleration: AccelerationConfig = field(default_factory=AccelerationConfig)  # trend (Carver)
    mtf_pullback: MTFPullbackConfig = field(default_factory=MTFPullbackConfig)   # v3 #1 trend
    residual_mr: ResidualMRConfig = field(default_factory=ResidualMRConfig)      # v3 #2 xs-MR
    leadlag: LeadLagConfig = field(default_factory=LeadLagConfig)                # v3 #3 crypto xs
    intermarket_div: IntermarketDivConfig = field(default_factory=IntermarketDivConfig)  # v3 #4 xs-MR
    kama: KAMAConfig = field(default_factory=KAMAConfig)                         # v3 #6 adaptive trend
    vol_breakout: VolBreakoutConfig = field(default_factory=VolBreakoutConfig)   # volatility family

    # ── risk / overlays / execution / convex ──────────────────────────────
    risk: RiskConfig = field(default_factory=RiskConfig)
    selection: SelectionConfig = field(default_factory=SelectionConfig)       # dynamic universe
    vol_managed: VolManagedConfig = field(default_factory=VolManagedConfig)   # G1 overlay
    convex: ConvexConfig = field(default_factory=ConvexConfig)
    execution: ExecConfig = field(default_factory=ExecConfig)

    # ── forecast frame ────────────────────────────────────────────────────
    forecast_cap: float = 20.0                    # Carver ±20 cap
    forecast_target: float = 10.0                 # target avg abs forecast
    soft_cap: bool = True                         # tanh soft-cap (retain tail convexity)

    # ── derived helpers ───────────────────────────────────────────────────
    @property
    def cadence_minutes(self) -> int:
        """Minutes per strategy step for the current sleeptime."""
        return {"1M": 1, "5M": 5, "15M": 15, "60M": 60, "1D": 1440}[self.sleeptime]

    def minute_fetch_length(self, warmup_mult: float = 1.2) -> int:
        """How many 1-min bars to request so ``history_bars`` cadence bars exist."""
        return int(self.history_bars * self.cadence_minutes * warmup_mult) + self.cadence_minutes

    def bars_per_year(self, is_crypto: bool = True) -> float:
        """Annualisation factor for vol scaling given the sleeptime cadence."""
        minutes = {"1M": 1, "5M": 5, "15M": 15, "60M": 60, "1D": 1440}[self.sleeptime]
        if self.sleeptime == "1D":
            return 365.0 if is_crypto else 252.0
        if is_crypto:                              # 24/7 markets
            return (60 / minutes) * 24 * 365
        return (60 / minutes) * 6.5 * 252          # US RTH ≈ 6.5h/day
