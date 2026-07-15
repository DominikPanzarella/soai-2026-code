# Strategy Catalog — SoAI 2026 Systematic Multi-Strategy Bot

**Methodology:** Halls-Moore, *Successful Algorithmic Trading*, Ch. 5 (strategy identification → filtering → forecast construction) mapped onto a Carver *Advanced Futures Trading Strategies* (AFTS) / pysystemtrade forecast-combine engine.
**Objective:** maximise TERMINAL RETURN over one calendar month, winner-take-most → both convexity (fat right tail) and survival (no ruin) are priced.
**Hard constraints:** OHLCV only; ≥1-minute bars; crypto SPOT (long/flat, cash = risk-off) via CCXT + US equities/ETFs; volume-aware slippage.

---

## 1. Executive Summary — the Ch. 5 pipeline on our engine

Halls-Moore Ch. 5 is a *funnel*: enumerate candidate edges → filter each against data availability, look-ahead, transaction cost/liquidity, replicability, and overfitting → keep only what survives → express each survivor as a *rule* on a common risk scale → combine. Carver's engine is exactly that common risk scale. Every kept edge becomes a **forecast rule** emitting a value in the ±20 frame with target avg|f| ≈ 10, and the pipeline is:

```
                per rule r, per instrument i, per bar t
raw signal  ->  vol / scale standardisation  ->  x forecast_scalar S_r  ->  cap ±20 (soft)  -> f_{r,i,t}
   |                                                                                              |
   |  (S_r = 10 / pooled_mean(|raw|), long-window, pooled across instruments)                     |
   v                                                                                              v
SPOT clip f -> max(f,0)   (crypto & long-only equity sleeves)                                     |
                                                                                                  v
combined_i = FDM_i * sum_r( w_r * f_{r,i} )    ->    cap ±20                          [forecast-combine stage]
                                                                                                  |
                                                                                                  v
position_i = (combined_i / 10) * (tau * Capital) / (sigma_i * price_i) * v_i * IDM    [vol-target + IDM sizing]
                                                                                                  |
                                                                                                  v
greedy discrete rounding (min-notional, volume-aware fill, no-trade buffer)           [execution stage]
```

Design consequences specific to *this* contest:

- **Long/flat kills short-side crisis alpha.** All crypto forecasts are clipped to `[0,20]`; this roughly halves realised avg|f|, so forecast scalars must be re-fit on the *clipped* series to keep avg|f| ≈ 10. The short leg (and true market-neutrality) is only recoverable on the equity sleeve (inverse ETFs, dollar-neutral pairs).
- **Trend is one factor, not many.** EWMAC, plain TSMOM, Faber, crypto 10/40 MA, 52-week-high and CTREND are all the *same* time-series-trend premium at different speeds/constructions. They share ONE trend budget (~35–50% of forecast weight) allocated across the speed/construction grid — they do not stack.
- **Diversification is bought at the edges of the funnel.** The genuine correlation-reducers vs a trend-heavy book are: cross-sectional relative strength, mean-reversion (RSI/Bollinger/overnight/EOD reversal), the lottery/low-risk composite (MAX/RSkew/IdioVol), calendar/clock signals, and Kalman equity pairs. These are where incremental Sharpe and terminal-return convexity actually come from.
- **Convexity for the tournament** comes from: soft-capping forecasts (retain tail signal instead of a hard ±20 clip), a small leveraged-ETF satellite, squeeze breakouts, and a slightly-above-half-Kelly risk budget — all under a hard survival floor (drawdown gate + vol target).
- **Overlays are multipliers, never weighted forecasts.** Regime gates (HMM, efficiency-ratio, breadth), vol-managed scaling, drawdown control, and frog-in-the-pan quality all multiply an existing forecast/weight; counting them as independent forecast rules would double-count trend or double-count vol.

---

## 2. KEPT Strategies Catalog

Notation used throughout: `EWMA(x,n)` = exponential MA span n; `sigma_ret` = EWMA of returns (32-day span default) annualised (√365 crypto / √252 equity); `z(·)` = rolling/cross-sectional z-score; `cs_rank` ∈ [0,1]; `clip(x,a,b)`; SPOT clip = `max(f,0)`. Forecast scalar `S_r = 10 / pooled_mean(|raw_r|)` on a long expanding, cross-instrument-pooled window, re-fit slowly (NOT monthly).

---

### Family A — Trend (time-series). Shared budget ≈ 35–45% of total forecast weight.

#### A1. Carver Multi-Speed EWMAC — **ANCHOR (KEEP)**
- **Logic / formula.** For each span pair (fast,slow) ∈ {8/32, 16/64, 32/128, 64/256}:
  `raw = EWMA(close,fast) − EWMA(close,slow)`; vol-normalise `raw_vol = raw / (sigma_ret_35d · price)`; `f = clip(raw_vol · S, −20, 20)` with Carver priors S = {5.95, 4.10, 2.79, 1.91}. SPOT clip `[0,20]`. Combine 4 speeds equal-weight × FDM ≈ 1.25.
- **Sources.** Carver, *AFTS* / *Systematic Trading*; pysystemtrade code (qoppac.blogspot.com, github.com/robcarver17/pysystemtrade); Moskowitz-Ooi-Pedersen, *Time Series Momentum*, JFE 2012 — https://www.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf
- **Why it survives.** OHLCV-close only, fully causal, rule-property scalars (not fitted to returns) → low overfit; three independent citations. Fastest pair (8/32) survives volume-aware slippage only on BTC/ETH → restrict fast speeds to liquid majors.
- **Engine mapping.** As above. Re-fit S on the clipped series when targeting avg|f| = 10 net.
- **Weight.** ~0.35 of trend block (largest single allocation).
- **Sleeve.** Crypto core + equity/ETF core.
- **Diversification.** Self-correlation 1.0 — it *is* the trend the rest is measured against. Justified as anchor, not diversifier.

#### A2. TSMOM — continuous / vol-scaled (Moskowitz-Ooi-Pedersen) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Use the CONTINUOUS, vol-scaled form (not sign-only): `f = 20 · clip( r_{t−k} / (sigma_k · c), −1, 1)`, `sigma_k` = rolling stdev of the k-horizon return, c ≈ 2 sets the cap point. Diversify k ∈ {20,45,90}d equal-weight (add {5,10,60} intraday-bar-equivalents for faster books). SPOT clip. The edge is *materially the vol-scaling*, not the sign.
- **Sources.** MOP JFE 2012 (link above); Han-Kang-Ryu (crypto TS-mom robust to costs, SSRN 4675565); Liu-Tsyvinski, *Risks and Returns of Cryptocurrency*, RFS. NB the sciencedirect S1062940821000590 URL is Borgards, *not* MOP.
- **Why it survives.** OHLCV-only, causal, lower turnover than EWMAC crossover (cost-friendliest trend expression). Sign-only form discarded — it doubles correlation with EWMAC.
- **Caveats.** ~0.8+ correlated to EWMAC; single-k fragile (reversal at very short k). Keep only if k-tenors differ materially from EWMAC speeds.
- **Weight.** 0.05–0.10, or substitute part of EWMAC to cut turnover on 1–15M.
- **Diversification.** LOW vs EWMAC; marginal only through different lookback tenors.

#### A3. Crypto TSMOM 10/40-MA (Grobys) — **KEEP**
- **Logic / formula.** EWMAC-style on crypto SPOT: `f = clip(S · (EMA_fast − EMA_slow)/(price·sigma_daily), 0, 20)` with pairs ≈ 10/40d (plus 8/32, 16/64); per-pair scalars. Drop to 60M bars for a faster intraday variant. Gate universe by CCXT dollar volume.
- **Sources.** Grobys et al. 2020, *arXiv:2009.12155* — https://arxiv.org/abs/2009.12155 (10 & 40-day SMAs best, Sharpe ~0.5–1.5, robust 2011–2019).
- **Why it survives.** arXiv-verified, CCXT-native, long/flat native — the natural core engine for the crypto SPOT sleeve (competition's main universe). NB the headline 255% is regime-specific (2011–19 infancy) → it's a *speed of the EWMAC bank*, not independent alpha.
- **Weight.** Largest crypto-sleeve allocation ~20–25%, **shared** with A1/A2 (do not double-count).
- **Diversification.** LOW vs trend book; it is the crypto trend core.

#### A4. Faber Asset-Class Trend (10-mo / 200-day MA) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Register as the *slowest* trend speed: `f = clip(S · (Close − SMA_n)/(price·sigma_daily), −20, 20)`, SPOT clip; SMA 100/200. Binary overlay form: `1{Close>SMA200}`.
- **Sources.** Faber, *A Quantitative Approach to Tactical Asset Allocation*, 2007 (most-downloaded SSRN paper) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461
- **Why it survives.** Robust, one-line, very low turnover. Almost fully redundant with slow EWMAC → folded into trend grid (~5–8% notional share) OR used purely as a 0/1 risk-off filter. Lags at turns / drags in bull months → don't over-use as a de-risk gate in a 1-month sprint.

#### A5. 52-Week-High (Nearness-to-High) Momentum — **KEEP-WITH-CAVEATS**
- **Logic / formula.** `NH_i = close / max(High, trailing 252d)` (crypto: 365d or shorter rolling high). Time-series form preferred for SPOT: `f = clip(k·(NH − thresh), −20, 20)` scaled so NH∈[0.97,1.0]→~+20, NH≈0.80→~+10, →0 well below. Feed into the trend-rule group (not a new group).
- **Sources.** George & Hwang, *The 52-Week High and Momentum Investing*, JF 2004 — https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.2004.00695.x
- **Why it survives.** Nearness-to-high dominates JT past-return momentum and does NOT reverse long-run → better-behaved trend anchor with attractive terminal-return convexity. OHLCV-only, low turnover.
- **Caveat.** After a bear market a stale ATH pins the whole universe to low NH (breadth collapse) → use a shorter rolling high on crypto.
- **Weight.** Moderate-small, drawn from the existing trend budget. **Diversification.** LOW vs EWMAC — measure incremental correlation before granting weight.

#### A6. Carver Adjusted / Accelerating Trend — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Take scaled EWMAC forecast. Adjusted: `f_adj = EWMAC_scaled − EWMA(EWMAC_scaled, slow)`. Accelerating: `accel = EWMAC_scaled_t − EWMAC_scaled_{t−n}`, vol-normalise, **re-fit scalar** (differencing collapses the scale), cap ±20 / SPOT clip. 1–2 speeds only.
- **Sources.** Carver, *AFTS*; QuantConnect replications of accelerating trend.
- **Why it survives.** Faster exits + acceleration capture improve convexity (directly valuable for terminal return). But it is derived FROM EWMAC → highly correlated, higher turnover, and can exit persistent month-long crypto runs too early (the exact scenario the contest rewards holding) → slow/medium speeds only, majors preferred.
- **Weight.** 0.10 as an overlay/accelerator on the trend block. **Diversification.** LOW-MODERATE (a derivative of EWMAC).

#### A7. Bitcoin Intraday TSMOM (early-block → intraday) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Fix a UTC-day anchor. `r_early` = return over first block (e.g. first 60min). `f = 20·clip( r_early / (rolling sigma of r_early ~60d), −1, 1 )`, linearly decay f→0 by session end. Amplify (×≤1.5, re-capped) on volume>rolling-avg days. One position/day, BTC/ETH only.
- **Sources.** Gao, Han, Li, Zhou, *Market Intraday Momentum*, JFE 2018 — https://doi.org/10.1016/j.jfineco.2018.05.009 ; Shen/Urquhart/Wang, *Financial Review* 2022 (crypto intraday momentum).
- **Why it survives.** Intraday horizon + early-return signal near-orthogonal to daily trend → independent return stream and convexity that matter for a 1-month contest.
- **Caveats.** Session-anchor fragility (crypto has no true open/close); competing intraday-reversal evidence. Restrict to majors so daily round-trips survive slippage.
- **Weight.** 0.10, capped until walk-forward confirms the anchor. **Diversification.** HIGH — different horizon, low correlation to daily trend.

#### A8. CTREND Crypto Trend Factor (multi-horizon MA cross-section) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Per coin build `A_i = [MA(L)/price − 1]` for L∈{3,5,10,20,50,100,200}d. Rolling Fama-MacBeth cross-sectional regression of next-period return on A (ridge/shrinkage), fitted `E[r_i]` = composite trend score. `f_i = clip(S·z(E[r_i]), 0, 20)`. Weekly rebalance, liquid majors only.
- **Sources.** CTREND, *JFQA* (crypto trend factor survives costs, persists in big/liquid coins, renders most momentum insignificant except 2-week).
- **Why it survives.** Rare cost-robustness in liquid names — a direct answer to the Han-Kang-Ryu cost critique. Overfitting risk real (original uses ML across 3000+ coins) → simplified regularised regression on liquid universe only.
- **Weight.** 6–9% crypto (top of the crypto satellite budget). **Diversification.** LOW-MODERATE vs trend — treat as an *upgrade* to crypto trend, not an orthogonal stream.

---

### Family B — Breakout. Shared budget ≈ 15–25% (part convex sleeve).

#### B1. Donchian / Turtle Channel Breakout (Carver continuous form) — **KEEP**
- **Logic / formula.** `H_N=rolling max, L_N=rolling min, mid=(H_N+L_N)/2`; `raw = 40·(close−mid)/(H_N−L_N)` (∈≈±20); smooth `EWMA(span≈N/4)` (essential — unsmoothed flips on every new extreme); cap ±20, SPOT clip. Ensemble N∈{20,40,80,160} equal-weight × FDM. Optional 55-mid trend gate.
- **Sources.** Carver breakout rule + blog (correlation ~0.93 to same-speed EWMAC verified); Poluri, SSRN 2026; Turtle/Faith evidence on BTC.
- **Why it survives.** Uses only high/low, causal; signal *geometry* (position in range) differs from MA-distance → genuine partial diversification (~0.5–0.7 corr vs EWMAC across *widely separated* speeds). Breakout candle is the slippage risk → volume-aware fill, skip thin bars.
- **Weight.** ~0.10–0.20 of trend block, **only** for speed buckets EWMAC doesn't occupy (shares the trend budget). **Diversification.** MODERATE within trend family; strongest single diversifier among pure-trend candidates, but ~0.9 same-speed → never stack same-speed on EWMAC.

#### B2. Volatility-Contraction / Squeeze Breakout (+ breakout-from-consolidation) — **KEEP**
- **Logic / formula.** Squeeze flag = Bollinger BandWidth or ATR/price in bottom ~20th percentile over 120 bars OR NR7 → arm. On body-close beyond band with `volume > rolling median`: `f = clip((close − upper_band)/(k·ATR), 0, 20)`, k chosen so avg|f| on triggered bars ≈ 10; decay linearly to 0 over N bars without follow-through; f=0 otherwise. Trail exit via opposite Donchian/ATR.
- **Sources.** Trading Setups Review / Unofficed NR7 (practitioner); volatility-clustering basis (Bollinger squeeze). Consolidation refinement folds in here.
- **Why it survives.** Best intraday-native genuinely diversifying candidate — entry/event timing orthogonal to continuous TSMOM; captures fresh expansion (convexity). Two mandates: (1) body-close + volume confirmation vs false breakouts; (2) volume-capped fills so oversized orders don't "fill" at the print. Gate with HMM/trend to avoid ranging whipsaw.
- **Caveat.** Signal-sparse — can produce ZERO valid setups in a month; PREFER implementing the compression flag as a ×1.0→×1.5 boost on B1 to avoid dead months.
- **Weight.** Moderate ~15–25% of book if standalone; 0 if folded into B1. **Diversification.** HIGH (event timing) standalone; LOW vs B1 if a subset.

#### B3. Filtered Opening-Range Breakout (ORB) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** `d_signed = (close − OR_high)/ATR14` above range (negative below). `f = clip(k·d_signed, −20, 20)`, SPOT upside only. **AND-gate to 0** unless ALL pass: RVOL_OR > 1.5× trailing-20 mean, OR_width > median recent width, price on trend side of prior-day close/VWAP. Exit at close or stop back inside range. Keep range length fixed a priori.
- **Sources.** Zarattini/Barbon/Aziz 2023 (5-min OR, stocks-in-play) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416622 ; MNQ falsification (arXiv 2605.04004) shows *raw* ORB is dead — the edge is entirely in the filters.
- **Why it survives (barely).** Only heavily-gated, on liquid index products (QQQ/TQQQ), fixed parameters. Most execution/slippage-sensitive candidate → tiny, liquid-only.
- **Weight.** 2–8%. **Diversification.** LOW (correlated with intraday momentum + trend); mostly redundant.

---

### Family C — Mean-Reversion. Shared reversion budget ≈ 20–25%.

#### C1. Connors Cumulative-RSI (adopt IN PLACE OF raw RSI-2) — **KEEP**
- **Logic / formula.** `cumRSI = sum of RSI(close,3) over last 2 bars`. Gate long-only where `close > SMA(200)`. `raw = (buy_threshold − cumRSI)` normalised to [−1,1]; `f = clip(max(raw,0)·S, 0, 20)`, S≈15–20 (bars cluster near 0); exit as cumRSI > ~65. Equities allow short. NO hard stops (they historically hurt RSI-2) — size via vol-target, rely on SMA200 filter for tail control.
- **Sources.** Connors & Alvarez, *Short Term Trading Strategies That Work*, 2008; Quantitativo (cumulative RSI improves profit factor, fewer false signals).
- **Why it survives.** OHLCV-only, cheap, the single best true diversifier vs the trend book (fights chop bleed). Smoother than RSI(2) → fewer whipsaw trades. Anti-convex payoff (small wins, occasional big losses) → SMA200 gate + vol sizing mandatory.
- **Weight.** ~0.10, as the chosen reversion oscillator. **Diversification.** HIGH vs trend (negative/mildly-negative corr); but ~0.7–0.9 vs Bollinger → ONE reversion budget.

#### C2. Bollinger / Z-Score Reversion with Regime Gate — **KEEP-WITH-CAVEATS**
- **Logic / formula.** `z = (close − SMA20)/std20`; `raw = −z` (fade). Continuous regime factor `g∈[0,1]` from ADX (g=1 when ADX<20, ramp to 0 by ADX>30). `f = clip(raw·g·S, 0, 20)` (SPOT), exit as z→0. Winsorise/cap z on gaps.
- **Sources.** Bollinger; community BTC 4H evidence (profit factor 1.62 ranging vs −0.74 trending — the gate dominates the outcome).
- **Why it survives.** The regime gate is what makes reversion viable vs a coin-flip in trends. Calibrate S on gated-ON bars to keep avg|f| ≈ 10.
- **Weight.** ~0.10 within the shared reversion budget (the preferred reversion *position* expression). **Diversification.** HIGH vs trend, ~0.6–0.8 vs C1 → share budget.

#### C3. Overnight-Intraday Reversal — **KEEP-WITH-CAVEATS**
- **Logic / formula.** `r_on = open_t/close_{t−1} − 1`. Time-series: `f = clip(−k·z(r_on), 0, 20)` SPOT. Cross-sectional (equity): `f = clip(−k·z_xs(r_on), −20, 20)`, dollar-neutral. Crypto synthetic overnight = 00:00–08:00 UTC low-liquidity window return. Open at session open, close at session close.
- **Sources.** Liu, Liu, Wang, Zhou & Zhu, *Overnight-Intraday Reversal Everywhere*, SSRN 2730304 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2730304 (Sharpe 2–5× traditional reversal, robust OOS, liquidity-provision mechanism); corroborated by Della Corte & Kosowski.
- **Why it survives.** Genuine mean-reversion, structurally anti-correlated to trend → one of the best diversifiers in the set. Premium concentrated in illiquid names → volume-aware fills critical, restrict crypto to majors / equities to liquid mid-large caps.
- **Weight.** 10–15% (higher-conviction diversifier). **Diversification.** HIGH.

#### C4. End-of-Day Cross-Sectional Reversal — **KEEP-WITH-CAVEATS**
- **Logic / formula.** `r_early` = return open→~12th half-hour per name; `z_xs` = cross-sectional z each day; `f = clip(−k·z_xs(r_early), −20, 20)`. SPOT keep f>0 (buy relative laggards into the close); equity sleeve runs the short (relative-winner) leg. Open at start of final bucket, close at close. **CRITICAL:** register as cross-sectional/relative so the combiner does NOT net it against A7/Market-Intraday-Momentum (time-series).
- **Sources.** Bogousslavsky, *Infrequent Rebalancing*, JF 2016 — https://onlinelibrary.wiley.com/doi/10.1111/jofi.12436 ; Baltussen, Da & Soebhag, *End-of-Day Reversal*.
- **Why it survives.** Cross-sectional reversal orthogonal to time-series trend; strong ballast if scoped correctly. Concentrated in rebalancing-flow (slippage-heavy) names → volume-aware fills + liquid screen.
- **Weight.** 8–12% on equity cross-section. **Diversification.** HIGH.

#### C5. VWAP-Band Mean Reversion — **KEEP-WITH-CAVEATS**
- **Logic / formula.** `z = (close − sessionVWAP)/vwap_sigma`; `f = clip(−k·z, 0, 20)` SPOT (below VWAP → long); **gate to 0 unless VWAP slope > 0**. Target exit z→0. Wide bands (fewer, higher-conviction fades) + strict volume-aware slippage.
- **Sources.** Practitioner only (Scanz/Forextester: ~63% reversion from 2σ extensions) — NOT peer-reviewed; treat effect size sceptically.
- **Why it survives (marginally).** OHLCV-feasible, trend-gated. Do not run naked fades. Low weight given weak evidence base.
- **Weight.** 4–8%. **Diversification.** MODERATE; partly overlaps C3/C4 → control aggregate reversion weight.

#### C6. Short-Horizon Cross-Sectional Reversal (1-week / 1-month losers) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Trailing 5d (Lehmann) or 21d (Jegadeesh) return R_i. `f = clip(−20·(2·cs_rank(R_i)−1), 0, 20)` SPOT (long recent losers). MUST be regime/breadth-gated (suppress in trending/risk-off states). Use close/trade prices (not mid) to avoid bid-ask-bounce inflation.
- **Sources.** Jegadeesh 1990 (JF); Lehmann 1990 (QJE).
- **Why it survives (barely).** High diversification in principle (anti-correlated to momentum) — its only justification. But the gross profit IS the liquidity-provision premium in high-slippage names → largely eroded net of volume-aware fills, and it fights EWMAC directly.
- **Weight.** Very small, regime-gated, near-zero when breadth is strongly positive. **Diversification.** HIGH but whipsaw-prone if ungated.

#### C7. Kalman-Filter Dynamic-Hedge Pairs (equity/ETF stat-arb) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** State-space `y_t = beta_t·x_t + intercept_t`, states random-walk; online Kalman filter → spread `e_t`, conditional std `sqrt(Q_t)`; `raw = −e_t/sqrt(Q_t)`; `f = clip(S·raw, −20, 20)`, S≈10; hard stop when |raw|>4 (cointegration-break). Equity/ETF (SPY/IWM, sector pairs): true dollar-neutral. Crypto: relative long/flat tilt only (never outright short).
- **Sources.** Halls-Moore / QuantStart Kalman pairs — https://www.quantstart.com/articles/State-Space-Models-and-the-Kalman-Filter-for-Time-Series-Analysis/ (and the cointegration/Kalman pairs series).
- **Why it survives.** Halls-Moore's own documented system; online update avoids rolling-OLS look-ahead. Highest-value diversifier — market-neutral spread, near-zero correlation to trend. Caveats: crypto no-short destroys neutrality (→ BTC-beta tilt, low value); delta (process/measurement variance) is a sensitive overfit knob; pair selection multiple-testing-prone.
- **Weight.** ~0.10 on equity/ETF sleeve; small/optional on crypto. **Diversification.** HIGHEST in the book (on equities).

---

### Family D — Cross-Sectional Momentum / Relative Strength. Shared XS budget.

#### D1. Crypto 30d/7d Cross-Sectional Momentum (top-cohort long/flat) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Weekly (Thu 00:00 UTC) rebalance, liquidity-screened basket. `R_i = close_t/close_{t−30d} − 1`; `z_i` cross-sectional; `f_i = clip(scale·z_i, 0, 20)`, negative→flat. scale ≈ 12.5 (positive-half-normal mean ≈ 0.8 → avg|f| ≈ 10).
- **Sources.** Drogen/Hoffstein/Otte, SSRN 4322637 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4322637 (long-only top cohort −2.35% vs BTC −37.82%, Mar21–Nov22). Countered by Han-Kang-Ryu (SSRN 4675565): crypto XS momentum is the WEAK leg after costs; edge concentrates in LARGE winners.
- **Why it survives (marginally).** Cross-sectional dispersion is a different axis from time-series direction → real diversifier. Cost-survivable ONLY with ≥$5M ADV multi-venue screen + weekly rebalance. Severe survivorship/listing bias.
- **Weight.** 5–8% crypto sleeve. **Diversification.** MODERATE-LOW (~0.4–0.6 to 20–60d TS-momentum).

#### D2. Crypto Short-Horizon XS Momentum + Long-Horizon Reversal Screen — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Weekly. `z_short` = xs-z of 14–28d return; `z_long` = xs-z of 90–180d return. `f_i = clip(scale·(z_short − lambda·max(z_long,0)), 0, 20)`, lambda ≈ 0.5 fixed (do NOT optimise per-asset).
- **Sources.** Dobrynskaya, SSRN 3913263 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3913263 (2–4wk crypto momentum; reversal beyond ~1mo driven by past LOSERS).
- **Why it survives.** Reversal screen makes it the most differentiated of the crypto-XS trio; long/flat sidesteps the worst (loser) leg. High turnover → majors + hysteresis band. Split the crypto-XS budget between D1 and D2 (they overlap — do not run both at full size).
- **Weight.** 4–6% crypto. **Diversification.** MODERATE (~0.3–0.5 to slow TS trend).

#### D3. Equity/ETF 12-1 Cross-Sectional Momentum — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Monthly. `R_i = close_{t−21}/close_{t−252} − 1` (skip last 21 bars — essential or it inverts to short-term reversal). `z_i` cross-sectional; `f_i = clip(scale·z_i, 0, 20)`, negative→cash. Top decile/quintile.
- **Sources.** Jegadeesh & Titman 1993 (JF); Alpha Architect 30-yr OOS — https://alphaarchitect.com/
- **Why it survives.** One of the most robust anomalies in finance (~1%/mo top-minus-bottom); long leg captures ~half with no borrow friction; passes every filter. Sturdiest single XS candidate. Only mandate weakness: 12M/monthly barely turns over in a 1-month tournament → near-static bet on last year's winners, exposed to momentum-crash rebounds → ballast, weak convexity engine.
- **Weight.** 8–12% equity sleeve. **Diversification.** MODERATE — cross-asset diversification just by being equities.

#### D4. Residual (Idiosyncratic) Cross-Sectional Momentum — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Rolling regress `r_i = a + b·mkt + e_i` (mkt = cap-weighted basket / BTC). `resmom_i = mean(e over t−252..t−21)/std(e)`; cross-sectional z; `f_i = clip(scale·z, 0, 20)`. Monthly equity / weekly crypto. Use beta shrinkage.
- **Sources.** Blitz, Huij & Martens, *Residual Momentum*, J. Emp. Finance 2011 — https://doi.org/10.1016/j.jempfin.2011.01.003 (~doubles Sharpe of total-return momentum; used by Robeco/AQR).
- **Why it survives.** Strips market/BTC beta → the BEST diversifier in the momentum family vs the TS-trend already in the book; crash-damping serves survival. Rolling-beta noisy on short crypto history → shrinkage + well-specified market proxy mandatory.
- **Weight.** 8–10% equity, 3–5% crypto. **Diversification.** HIGH (highest of momentum family).

#### D5. Sector / Asset-Class ETF Rotation (top-N 12M momentum) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Monthly rank ~10 sector/asset-class ETFs by 12M return; `f_i = clip(scale·z(R12_i), 0, 20)` for top-N (N=3), rest flat. Bolt on absolute-momentum/cash gate. Rank via `f = clip(20·(2·rank_pct − 1), 0, 20)`.
- **Sources.** Quantpedia sector rotation (CAGR ~13.9%, Sharpe 0.54, MaxDD −46% without cash gate) — https://quantpedia.com/strategies/sector-momentum-rotational-system/ ; Jegadeesh-Titman lineage.
- **Why it survives.** Distinctive add = breadth into non-equity risk premia (bonds, gold, REIT, commodity ETFs) — real asset-class diversification nothing else touches. Mechanically = D3 + D6 on an ETF set → keep ONLY as the cross-asset breadth vehicle; needs the absolute-momentum/cash gate or −46% DD.
- **Weight.** 3–5%. **Diversification.** MODERATE (redundant on momentum factor, real via non-equity ETFs).

#### D6. Dual Momentum / GEM (relative + absolute cash gate) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Relative leg = cross-sectional z of 12M return; absolute gate `= 1{R12_i > cash proxy}`. `f_i = clip(scale·z(R12_i), 0, 20)·gate` (gate fail → cash). **Average over lookbacks {6,9,12M} and 3 staggered rebalance days** to kill timing fragility — implement as a continuous forecast, never a binary switch.
- **Sources.** Antonacci, *Dual Momentum Investing* — https://www.optimalmomentum.com/ ; Newfound/ThinkNewfound on specification fragility — https://www.thinknewfound.com/
- **Why it survives.** The absolute gate = built-in trend/regime filter → survival + downside-cash-switch convexity, maps perfectly onto long/flat SPOT. Value is the regime gate, not incremental return. Absolute gate ≈ time-series trend → overlaps trend heavily; do not double-count the relative leg (already in D1–D4).
- **Weight.** 0% as standalone forecast in a 1-month sprint; use the absolute leg as a 0/1 gate. **Diversification.** LOW vs trend.

#### D7. Accelerating (Multi-Lookback) Dual Momentum — **KEEP-WITH-CAVEATS**
- **Logic / formula.** `S = r1m + r3m + r6m`; `f = clip(scale·(S_asset − S_cash)/sigma_S, 0, 20)`. Better: register r1m/r3m/r6m as three separate Carver rules and let FDM/weights blend (down-weight the noisy 1M leg).
- **Sources.** Engineered Portfolio, *Accelerating Dual Momentum* (blog-grade) — https://engineeredportfolio.com/2018/05/02/accelerating-dual-momentum-investing/
- **Why it survives.** Multi-horizon averaging is the robustness fix for D6 → prefer over plain GEM. Still monthly (few decisions/month), overlaps trend.
- **Weight.** 3–5% equity. **Diversification.** LOW-MODERATE (1M leg injects short-horizon reversal info).

#### D8. BTC-Leads-Altcoins Lead-Lag — **KEEP-WITH-CAVEATS**
- **Logic / formula (parsimonious, PREFERRED).** `gap_i = BTC_ret_L − alt_ret_L` over L=1–4h; `f_i = clip(20·(2·cs_rank(gap_i)−1), −20, 20)` conditioned on `BTC_ret_L > 0` (longs only when leader up), else 0. Rebalance 1H–4H. Do NOT ship the full lagged-panel/LASSO in-competition (overfit + latency).
- **Sources.** Guo, Sang, Tu & Wang, JEDC 2024 (strong cross-crypto predictability from lagged returns, robust to adaptive-LASSO/PCA, sizable long-short OOS net of costs; larger alpha in low-attention coins).
- **Why it survives.** A slow-diffusion mechanism distinct from trend and lottery → a NEW axis on the crypto book (gets fresh forecast weight). Low-attention laggards illiquid + fast decay → volume-gate fills, stay in the more liquid alt tier; sign regime-dependent → gate by breadth.
- **Weight.** Moderate within crypto sleeve. **Diversification.** GOOD.

---

### Family E — Intraday Seasonality / Calendar. Combined calendar budget ≈ 5–7% (merge to avoid double-counting).

#### E1. Market Intraday Momentum (first-bucket → last-bucket) — **KEEP**
- **Logic / formula.** `r_open = (first-bucket close / prior-session close − 1)` (INCLUDES overnight gap); `sigma_bucket` = rolling ~60-session stdev of same-index bucket. Blend `f_raw = 0.6·z(r_open) + 0.4·z(r_12th)`; ×S so avg|f| ≈ 10; cap ±20. Condition ×`min(RVOL_today, cap)` so it fires on high-volume days (where the JFE edge lives). SPOT: f≤0→flat. Hold = final bucket only.
- **Sources.** Gao, Han, Li & Zhou, JFE 2018 — https://doi.org/10.1016/j.jfineco.2018.05.009 (R²~1.6%, ~2.6% blended). NB 2026 MNQ falsification (arXiv 2605.04004): many variants fail net-of-cost t≥2 → cost discipline + high-vol/high-volume conditioning mandatory.
- **Why it survives.** Strongest academic pedigree in the intraday set; single daily round-trip keeps cost low; no look-ahead (close-to-open gap). Restrict to SPY/QQQ + BTC/ETH.
- **Weight.** 15–20% of the intraday/seasonality channel (apply FDM at channel level). **Diversification.** MODERATE-LOW (intraday horizon, overnight-anchored) — horizon-diversifier, not a true diversifier.

#### E2. Crypto Time-of-Day (Hour-of-Day) Seasonality — **KEEP-WITH-CAVEATS**
- **Logic / formula.** `f = k·z(rolling/expanding mean return of bucket h)`, re-estimated monthly (expanding, avoid look-ahead). Robust variant: `f ≈ +15` only for the documented 21:00–23:00 UTC cluster, 0 elsewhere. SPOT long/flat, hold 2–3h cluster (not single hours).
- **Sources.** Quantpedia / QuantifiedStrategies — https://quantpedia.com/ (22:00–23:00 UTC most significant, Sharpe ~1.58, 2015–2021; worst 03:00–04:00 UTC).
- **Why it survives (marginally).** Naturally long-biased → SPOT-friendly; pure clock signal → near-orthogonal to price rules. Classic 24-bucket data-mining risk → very low weight, monthly re-estimate, top hours only.
- **Weight.** 3–5%. **Diversification.** HIGH (orthogonal, low magnitude). **Merge with E3 into one day×hour surface.**

#### E3. Day-of-Week Seasonality — **KEEP-WITH-CAVEATS**
- **Logic / formula.** `f = k·z(rolling mean return of upcoming weekday)`, expanding, monthly re-est. Equity Monday-reversal refinement: `f = −k·z(prior-week return)` in the Monday-PM 30M bucket only. Implement jointly with E2 as a day×hour lookup table → one combined seasonal forecast.
- **Sources.** ML Quants intraday study; Quantpedia (Fri–Sun crypto strength; equity Monday reversal in afternoons).
- **Why it survives.** OHLCV-feasible, low cost. Crypto weekend effect decaying post-institutions → low weight.
- **Weight.** 2–4% (or fold into E2 for ~5–7% total). **Diversification.** HIGH vs trend but strongly overlaps E2 → treat as ONE calendar factor.

#### E4. Turn-of-the-Month Calendar Overlay — **KEEP-WITH-CAVEATS**
- **Logic / formula.** `f = +C (mapped to ~+15)` during trading days [−1,+1,+2,+3] around month-end, 0 outside. Optional gate: only take the long if 20-day trend > 0. Enter close of day −1, exit close of day +3.
- **Sources.** Quantpedia ToM — https://quantpedia.com/strategies/turn-of-the-month-in-equity-indexes/ (SPY buy day −1/sell day +3 → ~7.2% ann, Sharpe ~1.04, persists 31/35 countries).
- **Why it survives.** Robust, calendar-only (no look-ahead), trivial cost (~1 round-trip/month). But over a single tournament month it fires ~4 days → binary high-variance bet; value it as diversification, NOT ballast. No strong crypto evidence.
- **Weight.** 3–5% equity tilt. **Diversification.** HIGH (orthogonal calendar).

---

### Family F — Factor / Lottery / Low-Risk. Fold F1–F3 into ONE composite (avg the sub-forecasts, single combined weight ~5–10%).

#### F1. MAX / Lottery-Demand (long low-MAX) — **KEEP-WITH-CAVEATS — composite ANCHOR**
- **Logic / formula.** `MAX_i` = max daily/intraday log-return over trailing 7d (crypto) or top-5 avg over 21d (equity). `f_i = clip(−20·(2·cs_rank(MAX_i)−1), 0, 20)`. Dominant share (~1/2) of the lottery composite.
- **Sources.** Bali, Cakici & Whitelaw, *Maxing Out*, JFE 2011 — https://doi.org/10.1016/j.jfineco.2010.08.014 (>1%/mo, robust); Grobys & Junttila 2021 (crypto: raw MAX spread ~3.03%/wk, risk-adj ~1.99%).
- **Why it survives.** Strongest, most robust lottery member; independently confirmed in crypto. Long-only still captures the profitable low-MAX leg. Low-MAX longs are the more tradeable end → acceptable fills.
- **Diversification.** GOOD vs trend; redundant with F2/F3 → composite.

#### F2. Cross-Sectional Realized Skewness (negative-skew premium) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** `RSkew_i = (√N·Σr³)/RVar^{3/2}` from 15M–1H intraday log-returns; `f_i = clip(−20·(2·cs_rank(RSkew_i)−1), 0, 20)`. ~1/3 of composite.
- **Sources.** Amaya, Christoffersen, Jacobs & Vasquez, JFE 2015 — https://doi.org/10.1016/j.jfineco.2015.02.009 (~19bps/wk, t=3.70, not spanned by FF/Carhart).
- **Why it survives.** 3rd-moment asymmetry orthogonal to 1st/2nd-moment trend. Tiny per-week, noisy → composite only. Collinear with F1/F3.

#### F3. Idiosyncratic-Volatility Anomaly (long low-idio-vol) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Rolling 21–60d market-model regression, `IdioVol_i = std(eps)`; `f_i = clip(−20·(2·cs_rank(IdioVol_i)−1), 0, 20)`. ~1/6 of composite (least additive once F1 in).
- **Sources.** Ang, Hodrick, Xing & Zhang, JF 2006 — https://doi.org/10.1111/j.1540-6261.2006.00836.x (high-minus-low ~−1.06%/mo; international −1.31%/mo).
- **Why it survives.** Robust equity anomaly; residualisation is the only thing it adds over total-vol. Crypto market factor ill-defined → depends on unstable BTC-beta.

#### F4. Cross-Sectional Low-Volatility / Betting-Against-Beta — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Trailing 60–120d realised vol/beta; `f_i = clip(scale·z(−sigma_i), 0, 20)` (calmest names largest long). Monthly equity / weekly crypto. Or a 0.7–1.3 defensive multiplier on momentum forecasts.
- **Sources.** Frazzini & Pedersen, *Betting Against Beta*, NBER w16601 / JFE 2014 — https://www.nber.org/papers/w16601
- **Why it survives (as small tilt).** Highest-diversification, lowest momentum-correlation candidate. BUT long-only discards the leverage-constraint mechanism (muted alpha) and low-vol structurally LAGS bull rallies — at odds with a convexity-seeking 1-month contest. Value is survival, not terminal return. Weak/polluted in crypto.
- **Weight.** 3–5% equity, ≤2% crypto or omit.

#### F5. Low-Volatility XS Tilt / Inverse-Vol Base Weighting (crypto) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** Each rebalance rank by trailing realised vol; overweight low-vol tercile / inverse-vol weight (base weights ∝ 1/sigma_i), let IDM/vol-target size. Deliberately carve out an explicit **high-vol convex satellite** alongside.
- **Sources.** Harvey et al.; Quantpedia risk-parity/inverse-vol (mechanism behind much of TSMOM's risk-adjusted return).
- **Why it survives.** Standard survival/risk-parity base weighting. Key caveat AGAINST objective: underweights the most explosive coins → run the high-vol satellite so it doesn't cap tournament upside.
- **Weight.** Moderate as base weighting, capped. **Diversification.** MODERATE (cross-sectional axis).

#### F6. Turnover / Abnormal-Volume Anomaly (long low-abnormal-volume) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** `AbnVol_i = current volume / trailing 20-period avg volume`; `f_i = clip(−20·(2·cs_rank(AbnVol_i)−1), 0, 20)` (crypto has no clean float). Optionally fold into the low-risk composite.
- **Sources.** Datar, Naik & Radcliffe, JFM 1998; Hou-Xue-Zhang replication (mixed/weaker in modern samples).
- **Why it survives (minimally).** Marginal, replication-fragile, low-turnover names are thinner → slippage screen. Keep tiny if at all. **Diversification.** LOW (correlated with F3/illiquidity).

#### F7. Good/Bad Realized Semivariance (signed-jump) — **KEEP-WITH-CAVEATS**
- **Logic / formula.** `RSV = (RS⁺ − RS⁻)/RV` from 5M/15M intrabar squared returns over the rebalance window; z-score to own history; small tilt `f = clip(z·k, −10, 10)` (SPOT floor 0), OR a pure de-risk multiplier on RS⁻ (downside-jump) spikes. Cap tighter than trend rules. Pin sign convention to the cited paper.
- **Sources.** Crypto realized semivariance cross-section, IRFA 2023.
- **Why it survives (as small gate/tilt).** Real but economically small and sign-UNSTABLE (TS vs XS sign differs) → not a primary rule.
- **Weight.** ~5–10% of book as tilt/gate. **Diversification.** MODERATE.

---

### Family G — Overlays / Conditioners (multipliers, NOT weighted forecasts)

| Overlay | Formula | Source | Applied to | Notes / caveat |
|---|---|---|---|---|
| **G1. Vol-managed / crash-managed momentum** (Barroso-Santa-Clara / Moreira-Muir / Hoyle-Shephard) | `m_t = clip(sigma_target/RV_t, 0.2, 2.5)`; `f_adj = m_t·f_trend` BEFORE ±20 cap; `sigma_target` set so median multiplier ≈ 1 | Barroso & Santa-Clara, *Momentum Has Its Moments*, JFE 2015 https://doi.org/10.1016/j.jfineco.2014.11.003 ; Moreira & Muir JF 2017 | **Trend/momentum forecasts ONLY** (A, B, D). NOT reversion/pairs. | Sharpe 0.53→0.97, kurtosis 18.24→2.68 — kills the left tail, adds convexity (highest EV addition for the tournament). Exclude from global vol-target denominator to avoid double vol-scaling. |
| **G2. HMM 2-state regime gate** | 2-state Gaussian HMM on rolling bar returns (+realised range); label lowest-variance state = risk-on (never by index); `f_final = f_combined · smoothed P(risk-on)`; refit weekly | QuantStart HMM demo | Post-FDM combined forecast, portfolio level | Look-ahead is the dominant risk → rolling refit + variance labelling. 60M/1D only (unstable intraday). Matches S31 HMM. |
| **G3. Efficiency-ratio / dynamic-TSMOM conditioner** | `ER = |close_t−close_{t−N}| / Σ|Δclose|`; `w_t = 0.5 + clip(ER−0.5, −0.5, 0.5)` ∈ [0.5,1.0]; `final = base_trend·w_t` | Borgards 2021, N.Am.J.Econ.Fin. (NOT JIMF) | Combined **trend** forecast (not per-rule) | Never fully 0 — regime estimators lag and can gate out right before the big winning move. **Pick ONE of G2/G3/G5.** |
| **G4. Hurst trend/MR selector** | `w_trend = smoothstep(H; 0.45,0.55)`; H via variance-of-lagged-differences (100–500 bars), EWMA-smoothed | Macrosynergy 2023; arXiv 2205.11122 | Rule-family magnitudes | Near 0.5 in crypto → weak there. Soft gate only; low priority (overlaps G2). |
| **G5. Vol-regime ATR gate** | soft `m ∈ [0.5,1.0]`, taper only in extreme TOP ATR decile (not a hard cut) | community BTC evidence | Trend forecast | **DROP the ATR *sizing* leg** (double-counts engine vol-target). Redundant with G3 → weight 0 if G3 adopted. |
| **G6. Drawdown-control (CPPI-like)** | `m(DD) ∈ [0.2,1]`: m=1 for DD<~8–10%, linear to m_min at DD~25–30%, ratchet up on recovery | Harvey et al.; AQR tail-hedge trend | Post-FDM combined forecast | Pro-cyclical (can lock losses at the bottom) → shallow floor, fast snap-back; don't stack with G1/G2/vol-target all de-risking at once. |
| **G7. Frog-in-the-Pan quality** | `ID = sign(PRET)·(%neg − %pos)`; `m_i = clip(1 − k·cs_rank(ID), 0.5, 1.5)` × trend/XS-mom forecast, then re-target avg|f|=10 | Da, Gurun & Warachka, *Frog in the Pan*, RFS 2014 https://doi.org/10.1093/rfs/hht116 | Trend & XS-momentum forecasts | Continuous-info momentum (+5.94%) doesn't reverse; discrete-info (−2.07%) does. Cheap OHLCV quality filter, cost-neutral. |
| **G8. Factor/Rule Momentum (meta-weighting)** | trailing risk-adj P&L per rule → `g(s_j) ∈ [0.5,1.5]`; `w_j_eff = w_j_base · g(s_j)`, renormalise; ≥3–6mo formation | Ehsani & Linnainmaa, *Factor Momentum*, JF 2022 https://doi.org/10.1111/jofi.13131 | Rule *weights* (pre-FDM) | Keep base handcrafted weights dominant; cap the tilt so no rule collapses FDM diversification. |
| **G9. Market-Breadth risk-on/off** | `B(t)` = fraction of universe with close>trailing long MA; `GrossScalar = clip(a+b·B, floor, cap)` | StockCharts/Schwab (practitioner) | **Gross exposure** after combine+vol-target | Ensemble with G2/G6 via MIN or product-with-floor (do NOT additively double-cut). Small crypto universe → noisy; pair with faster confirmation. |

---

### Family H — Engine / Sizing / Portfolio-Construction (always-on stages)

These are not forecasts — see Section 4 for the full construction. Kept engine stages:

- **H1. Forecast scalar calibration & capping** (KEEP) — `S_r = 10/pooled_mean(|raw|)`, then **soft** cap toward ±20 (tanh-style) to retain tail convexity for the tournament rather than a hard clip. AFTS; the7circles walkthrough.
- **H2. FDM** (KEEP) — Section 4. qoppac: `ewma_span 125`, `floor_at_zero True`, cap ~2.5.
- **H3. IDM** (KEEP-WITH-CAVEATS) — Section 4. Cap ~1.5 crypto-heavy → 2.5 balanced; weekly-return correlations.
- **H4. Handcrafting** (KEEP) — PRIMARY weighting scheme (Section 4).
- **H5. Volatility targeting** (KEEP) — the risk backbone: `units = (f/10)·(tau·Capital·IDM·v_i)/(sigma_i·price_i)`; blend 70% fast (32d EWMA) + 30% slow vol. `tau` set for survival first.
- **H6. GARCH(1,1) sizing denominator** (KEEP-WITH-CAVEATS) — replace vol-target denominator with `sigma_hat_{t+1}`; EWMA fallback; 1D/60M only (breaks on intraday seasonality). Leverages your S26 ARIMA+GARCH work.
- **H7. Dynamic optimization (greedy tracking-error min)** (KEEP-WITH-CAVEATS) — execution/rounding stage for small account + crypto min-notional; `min sqrt(gap'Σgap) + 10·cost(gap)`, greedy add-one-lot, no-trade buffer, `w≥0`.
- **H8. Weighting alternatives** (KEEP-WITH-CAVEATS, pick ONE with H4): bootstrapped MVO w/ shrinkage (qoppac: monte_runs 100, shrinkage_SR 0.90, shrinkage_corr 0.50, pool True); ERC (Maillard-Roncalli-Teiletche); cluster risk parity (López de Prado HRP) — preferred over plain ERC when universe grows; GMV/min-correlation w/ Ledoit-Wolf shrinkage (blend `w = λ·w_GMV + (1−λ)·w_forecast`, minority λ).
- **H9. Fractional-Kelly top-level risk budget** (KEEP-WITH-CAVEATS) — `F = C⁻¹M` across strategy FAMILIES only; ≤0.5 Kelly haircut; hard-clip to SPOT 1x + survival floor. Never sizes individual positions.
- **H10. Diversification-return / rebalancing premium** (KEEP-WITH-CAVEATS) — construction hygiene: drift-band (not calendar) rebalancing on decorrelated long/flat sleeves. Do NOT trim EWMAC winners (fights trend/convexity). Willenbrock FAJ 2011; Bouchey et al. JWM 2012; AQR 2017 caveat.
- **H11. Narang construction framework** (KEEP-WITH-CAVEATS) — organising lens (alpha optimist / risk pessimist / cost accountant); default to the rule-based branch (= H4+H3+H7). Optimizer branch only where turnover dominates, with `w≥0` + real cost model.

---

## 3. REJECTED Strategies

| Strategy | Family | Ch. 5 filter that killed it | Detail |
|---|---|---|---|
| Decade-evidence long-only crypto trend (single slow-MA) | trend | **Overfit / redundancy** | Degenerate special case of the EWMAC bank's 64/256 pair clipped [0,20]; ~0 incremental diversification, headline 255% is 2011–19 regime-specific. |
| Cross-Sectional Crypto Momentum (standalone L/S) | xs-momentum | **Transaction cost / short-constraint** | Han-Kang-Ryu: XS momentum WEAK in crypto, portfolios liquidated after realistic costs; long-only truncation halves the spread; crowded XS reversal risk. |
| Cointegration Crypto Pairs (BTC-ETH class, static OLS hedge) | stat-arb | **Overfit + look-ahead + no-short** | ~100% win rates = in-sample; collapses to disguised BTC-beta tilt under no-short; rolling-OLS reintroduces look-ahead Kalman (C7) already solves. Strictly dominated. |
| Crypto Size Tilt (CSMB) | factor | **Data availability + cost + survivorship** | No reliable circulating-supply/market-cap under OHLCV-only; dollar-volume proxy conflates size with liquidity; small-cap slippage + rug/blow-up risk = anti-convex. |
| Opening-Gap Fade / Gap-and-Go | mean-reversion | **Falsified edge + no-short + no crypto session** | MNQ falsification: gap-fill fade fails at every entry time; "gaps always fill" is false; crypto has no 24/7 session gap; large gaps are news-driven (invisible in OHLCV). |
| Quarter-Hour / Periodic-Clock Momentum | microstructure | **Data availability (order-flow, not OHLCV)** | Kim & Hansen (arXiv 2607.09426) predictor is ORDER IMBALANCE — requires tick/order-flow we don't have; OHLCV proxy unvalidated; duplicates E1. |
| Overnight Drift (buy MOC / sell MOO) | seasonality | **Data quality + transaction cost + decay** | Edge measured vs a 9:31 print our OHLCV "open" can't reliably hit; NY Fed *Disappearing Overnight Drift*; NightShares ETFs closed in 14 months; 2 trades/day cost drag. |
| Amihud Illiquidity Premium | factor | **Transaction cost / liquidity (structural)** | The premium IS compensation for illiquidity; volume-aware fills gut it; screening for fillability removes exactly the names carrying it. Self-destructing. |
| Pre-FOMC Drift Overlay | seasonality | **Signal decay + event-sparse + no crypto** | Lucca-Moench 49bps largely gone post-2015 (Kurov et al. 2021); ~8 dates/yr may not fall in the contest month; US-equity-only. |
| Volatility-of-Volatility regime gate | vol | **Overfit + redundancy** | Nested estimator noisy/laggy; collinear with vol level + HMM/drawdown/vol-target; defensive-only, no standalone alpha — a 4th overlapping de-risk gate dilutes. |

---

## 4. Carver-Style Portfolio Construction for the Enlarged Set

### 4.1 Forecast scalars (per rule, entry gate)
Each rule's raw output is put on the common frame first:
```
S_r = 10 / mean_pooled(|raw_r|)      # long expanding window, pooled across instruments
f_{r,i,t} = softcap( S_r * raw_{r,i,t} , 20 )    # softcap ~ 20*tanh(x/20) retains tail convexity
SPOT: f_{r,i,t} = max(f_{r,i,t}, 0)              # re-fit S_r on the clipped series to restore avg|f|=10
```

### 4.2 Forecast weights `w_r` — handcrafting (PRIMARY)
Build a hierarchical tree by *rule family*, equal-risk within group, correlation-uncertainty-aware:
```
Trend { EWMAC(4 speeds), TSMOM, crypto10/40, Faber-slow, 52wHigh, Adj/Accel, BTC-intraday, CTREND }
Breakout { Donchian(N-ensemble), Squeeze, ORB }
Mean-reversion { cumRSI, Bollinger-gated, Overnight-rev, EOD-XS-rev, VWAP, ST-XS-rev, Kalman-pairs }
XS-momentum { crypto30/7, crypto-ST+reversal, eq12-1, residual, sector-ETF, GEM-gate, accel-DM, BTC-leadlag }
Calendar { MktIntradayMom, hour×day surface, ToM }
Lottery/low-risk { MAX, RSkew, IdioVol }  ->  ONE composite sub-forecast
```
- Equal-risk within each group using precomputed 2-/3-asset candidate matrices; Fisher-transform correlations, `se = 1/sqrt(n−3)`, evaluate at confidence points, average, apply weight floor, renormalise, propagate parent×child down the tree.
- Family-level budget targets: **Trend ~35–45%**, Reversion ~20–25%, XS-momentum ~15–20%, Breakout ~10–15%, Calendar ~5–7%, Lottery-composite ~5–10%. Overlays (Family G) carry NO forecast weight.
- Alternatives (choose ONE, do not stack): bootstrapped MVO (H8) or correlation-clustering handcraft variant for backtests (removes the subjective grouping). Optional mild Sharpe tilt only if you trust the estimates.

### 4.3 Forecast Diversification Multiplier (FDM)
After the weighted sum, the combined forecast is systematically under-scaled; restore it:
```
combined_raw_i = sum_r( w_r * f_{r,i} )
FDM = 1 / sqrt( w' C w )          # C = EWMA(span 125) corr matrix of the SCALED rule forecasts
                                  # negatives floored at zero; pool C across instruments; cap FDM <= 2.5
combined_i = softcap( FDM * combined_raw_i , 20 )
```
FDM restores avg|f| back toward 10 after diversification under-scales the sum. Re-estimated monthly/quarterly (near-zero turnover). Defaults to 1.0 on insufficient data.

### 4.4 Instrument weights `v_i` + IDM
```
v_i  : handcrafted (or cluster-risk-parity) tree over instruments:
        { crypto-majors } { crypto-alts } { equity-sectors } { cross-asset ETFs }
IDM = 1 / sqrt( v' C_s v )        # C_s = EWMA corr of instrument SUBSYSTEM returns
                                  # use WEEKLY returns (daily crypto/equity corr biased low by async closes)
                                  # negatives floored; cap ~1.5 crypto-heavy, up to ~2.0–2.5 once equities carry weight
```
Crypto-specific reality: majors run 0.7–0.9 correlated → few independent bets → IDM must be capped LOW; in risk-off SPOT regimes all crypto is long-beta so realised IDM collapses exactly when needed. **The equity/ETF sleeve is the genuine IDM lift.**

### 4.5 Final position
```
position_i = (combined_i / 10) * (tau * Capital) / (sigma_i * price_i) * v_i * IDM
then greedy discrete rounding (H7): min-notional, volume-aware fill cap, no-trade buffer, w>=0
```

### 4.6 Scaling as N rules / N assets grow
- **More rules:** FDM rises automatically toward its ~2.5 cap as genuinely uncorrelated families are added; the cap prevents a cluster of collinear trend rules from inflating it. Add rules to *existing* family groups so handcrafting equal-risk-within-group dilutes correlated additions.
- **More assets:** switch instrument weighting from hand-checkable handcrafting to **cluster risk parity** (HRP) once the universe outgrows manual grouping — it prevents 10 correlated altcoins from hijacking portfolio risk. IDM cap can rise as real cross-asset breadth (equities, bonds/gold ETFs) enters.
- **Small account:** enable H7 greedy optimization only when targets don't round cleanly; otherwise buffered rounding suffices.
- **Top-level:** fractional-Kelly (H9) across families sets `tau` and family risk budget; slightly-above-half-Kelly for convexity, subject to the drawdown floor (G6) and SPOT 1x cap.

---

## 5. Prioritized Implementation Roadmap → `strategies/engine/forecasts/`

Ordered by **diversification (correlation-reduction + terminal-return convexity) per unit of effort**. Effort assumes the ±20 forecast frame, vol-target, FDM/IDM stages already exist.

### Tier 0 — Engine prerequisites (must exist before any rule is meaningful)
1. **Forecast scalar + soft-cap (H1)** — nothing combines without avg|f|≈10 on a common frame; soft-cap buys tournament tail convexity for free. *Config:* `forecast_scalar_window`, `softcap_style: tanh`, `spot_clip: true`.
2. **FDM (H2) + handcrafting (H4) + IDM (H3) + vol-target (H5)** — the mandated combine/size stages. *Config:* `fdm_ewma_span 125`, `fdm_floor_at_zero true`, `fdm_cap 2.5`, `idm_cap 1.5`, `idm_corr_freq weekly`, `tau`, `vol_blend {fast:0.7@32d, slow:0.3}`.

### Tier 1 — Anchor + cheapest diversifiers (build first)
3. **A1 Carver Multi-Speed EWMAC** — the backbone; everything is measured against it. Deterministic public code. *Effort: low.*
4. **A3 Crypto 10/40 EWMAC (Grobys)** — same code as A1, crypto-tuned; anchors the main (crypto) sleeve. *Effort: trivial once A1 exists.*
5. **B1 Donchian ensemble** — reuses rolling max/min; ~0.5–0.7 corr vs EWMAC across separated speeds → the cheapest genuine trend diversifier. *Effort: low.*
6. **C1 Connors cumulative-RSI (+ SMA200 gate)** — the single best diversifier vs the trend book (negative correlation), cheap, OHLCV-only. Fights chop bleed → smoother equity curve. *Effort: low.*

### Tier 2 — High-value orthogonal streams
7. **F1–F3 Lottery/low-risk composite (MAX anchor)** — one composite = a new orthogonal (3rd-moment / low-risk) axis for one weight slot; MAX is low-overfit and crypto-confirmed. *Effort: medium (cross-sectional plumbing).*
8. **D4 Residual momentum** (equity) — the best-diversifying momentum variant (beta-stripped), crash-damping for survival. *Effort: medium (rolling regression + shrinkage).*
9. **C3 Overnight-Intraday Reversal** — strongest mean-reversion pedigree (Sharpe 2–5× traditional), structurally anti-trend. *Effort: medium (session anchor + volume-aware fills).*
10. **D8 BTC-leads-altcoins lead-lag** — a genuinely NEW crypto axis (slow diffusion), gets fresh forecast weight; use the parsimonious gap form only. *Effort: medium.*

### Tier 3 — Convexity + survival machinery for the tournament
11. **G1 Vol-managed/crash-managed momentum overlay** — highest single EV addition (kills left tail, adds convexity) at ~zero data cost; wire once, apply to trend/momentum only. *Config:* `volman_sigma_target`, `volman_clip {0.2,2.5}`, `volman_apply_to: [trend,breakout,xsmom]`.
12. **B2 Squeeze breakout** (or as a ×1.5 booster on B1) — the primary intraday convexity contributor; avoid dead months by folding into B1. *Effort: medium (compression detection + volume-confirm fills).*
13. **G6 Drawdown-control + G9 breadth gate (ensembled)** — survival floor for terminal wealth; ensemble via MIN/product, don't double-cut. *Config:* `dd_floor {d0:0.08, d_max:0.28, m_min:0.25}`, `breadth_ma 200`, `regime_ensemble: min`.
14. **H9 fractional-Kelly family budget + slightly-above-half-Kelly `tau`** — convexity dial under the survival floor. *Config:* `kelly_fraction 0.5`, `spot_max_leverage 1.0`.

### Tier 4 — Equity-sleeve breadth (real IDM lift) + calendar
15. **D3 Equity 12-1 momentum** — sturdiest single XS candidate; brings asset-class diversification and IDM. *Effort: low.*
16. **C7 Kalman equity pairs** — highest-value market-neutral diversifier (equities only). *Effort: high (state-space + pair selection + delta tuning).*
17. **D5 Sector/asset-class ETF rotation w/ cash gate** — the vehicle for non-equity breadth (bonds/gold/commodities) nothing else touches. *Effort: low.*
18. **E1 Market Intraday Momentum + E2/E3 day×hour surface + E4 ToM** — orthogonal calendar/clock signals; merge E2/E3 into one surface to avoid double-counting. *Effort: medium.*

### Tier 5 — Refinements / conditioners (once base rules are live and measured)
19. **G7 Frog-in-the-Pan quality gate** on trend/XS-mom — cost-neutral convexity/reversal-risk improvement. *Effort: low.*
20. **A5 52-week-high, A6 Adj/Accel trend, A7 BTC intraday, A8 CTREND** — fill trend-grid speed/construction buckets; measure incremental correlation before granting weight (mostly redundant). *Effort: low–medium.*
21. **D1/D2 crypto XS momentum, C2 Bollinger-gated, C4 EOD-XS-rev, C5 VWAP, C6 ST-XS-rev, D6/D7 dual-momentum, F4–F7 factor tilts** — remaining budget-sharing members; add only after confirming they clear volume-aware slippage and add correlation-diversification vs Tier 1–2. *Effort: varies.*
22. **G2 HMM gate / G3 efficiency-ratio / G4 Hurst** — pick ONE regime overlay (G2 recommended, matches S31); 60M/1D only. **H6 GARCH denominator** — 1D/60M with EWMA fallback (reuses S26). **H7 greedy optimizer** — only if the account is small vs min-notionals. **H8 cluster risk parity** — only when the universe outgrows handcrafting. *Effort: high; defer until base book is validated.*

**New config knobs summary** (`forecasts/config.yaml`): per-rule `forecast_scalar` + `softcap`; per-family `forecast_weight` budgets; `fdm_{ewma_span,floor_at_zero,cap}`; `idm_{cap,corr_freq}`; `tau`, `vol_blend`, `kelly_fraction`, `spot_max_leverage`; overlay switches `volman_*`, `regime_gate {type, states, refit_freq}`, `dd_floor_*`, `breadth_*`; execution `min_notional`, `volume_fill_cap`, `no_trade_buffer`; universe `dollar_volume_screen`, `crypto_majors_only_for {fast_ewmac, intraday}`.