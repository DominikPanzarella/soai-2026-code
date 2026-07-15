# Book-Sourced Strategy Catalog (Local Library)

*Companion to `research/strategy_catalog.md`. Covers only strategies that are NEW or materially-better book-specified variants vs the academic catalog. Every entry is OHLCV-feasible and cast as a Carver +/-20 forecast rule (or an explicit engine/overlay). Crypto = long/flat (floor f at 0); equities/ETFs may use both sides (inverse ETFs for the short leg). Line refs are to the verified source files under `/scratchpad/books`.*

---

## 1. Executive Summary — what the local library adds, by family

- **Trend / momentum.** The academic catalog's trend sleeve is EWMAC/Donchian/TSMOM-centric. The books add (a) a **continuous, deliberately un-vol-normalised breakout** (Carver) that decorrelates from EWMAC, (b) **Acceleration** = the discrete derivative of the EWMAC forecast (near-free, corr <=0.76 to parent), (c) several **price-action / pullback-in-trend entries** that are lower-turnover and 5M-cost-friendly (25ema pullback, dual-window pullback, close-in-upper-range hold-N, powerbar/combi breaks), and (d) a **sign-flipped intraday-hourly z-score** that trends where the daily version reverts.
- **Volatility.** The single biggest gap: the catalog has a vol-*managed* overlay but **no OHLC range estimator** and **no vol-of-vol / term-structure / leverage-effect** signals. Yang-Zhang RV is an engine-wide input upgrade; the leverage-effect vol-change rule is the cleanest genuinely-directional new vol rule; term-structure slope and overnight-variance-share add regime gates. A cycle/bandpass reversion adds an entirely absent "rhythm" family.
- **Mean-reversion.** Adds **confirmation-based** reversions (close-through of an extreme bar, failed-breakout snapbacks) distinct from naked z-score fades: HOLP/LOHP, smash-day / hidden smash-day, Specialists' Trap, OOPS, outside-day, GSV band, IBS, floor-trader-pivot R3/S3 fade. Plus two spec upgrades to the existing z-score rule (half-life-calibrated lookback; linear continuous position). The headline keeper is the **trend-gated, vol-attenuated "Safer Fast MR."**
- **Carry.** Genuine catalog gap, but OHLCV-only bites: only the **equity/ETF dividend-yield carry** is implementable. Crypto perp-funding and futures roll-return carry are out of scope.
- **Value.** Rejected for a one-month objective (5-year signal horizon, ~zero monthly contribution).
- **Sectoral / relative-strength.** Adds a **gap-excluded intraday opening-drive XS rank**, a **realized-correlation/dispersion gate**, and a general **empirical bar-scoring composite** (bin -> forward-return combiner that maps natively to the +/-20 frame).
- **Engine backbone.** The books supply the *plumbing* the catalog assumes but never specified: **position inertia** (no-trade buffer), **half-Kelly vol targeting**, **FDM cap 2.5 + final +/-20 cap**, a **cost-based turnover speed limit** (the direct answer to 5M cost-survivability), a **constant-+10 "no-rule" beta sleeve**, and a global **0.5-ATR forecast hysteresis**. These are the highest-leverage adds for an intraday tournament bot.

---

## 2. KEPT-NEW strategies (grouped by family)

Format per entry: **source** | **params** | **5M/60M fit** | **forecast mapping (signal -> standardise -> scalar -> cap)** | **weight** | **sleeve** | **diversification**.

### 2A. Trend / Momentum

**Carver Continuous Breakout** — Carver Adv. Futures, L15146-15300. Params: `h in {10,20,40,80,160,320}`; roll_max_h/roll_min_h of close. Fit: 5M (h>=40 only), 60M, daily. Mapping: `raw = 40*(close - (rmax+rmin)/2)/(rmax - rmin)`; **NO vol-standardise** (range already encodes vol — deliberate, to decorrelate from EWMAC); `f = EWMA(raw, span=h/4)`; scalar by h `{10:0.60,20:0.67,40:0.70,80:0.73,160:0.74,320:0.74}`; cap +/-20; crypto `f=max(f,0)`. Weight: **10-12%** (own divergent bucket, split across kept horizons). Sleeve: all. Diversification: catalog only has *binary* Donchian/ORB/squeeze; this is a graded, un-normalised +/-20 that builds position gradually (corr ~0.83 to itself across h, distinct from EWMAC).

**Acceleration** — Carver Adv. Futures, L16172-16260. Params: `N in {8,16,32,64}`. Fit: 60M/daily; on 5M slow variants (32/64) only. Mapping: take scaled EWMAC(N,4N) forecast `f` (already avg|f|~10); `accel = f_t - f_{t-N}`; **no further standardise**; scalar `{8:1.87,16:1.90,32:1.98,64:2.05}`; cap +/-20; crypto `max(accel,0)`. Weight: **5-7%** (near-free given EWMAC built). Sleeve: all. Diversification: 2nd derivative of the trend forecast; corr <=0.76 to parent EWMAC; distinct from catalog's accelerating/adjusted-trend (which reweight the MA).

**Dual-window pullback-in-trend** — Chan, Ch.6, L6068-6074. Params: lookbacks `{30,40}` bars. Fit: scale-free — 60M (30h/40h) or 5M, multi-bar holds. Mapping: long-eligible if `close<close[-30] AND close>close[-40]` (uptrend + recent dip); `f = clip(k * [(close-close[-40])/vol_long] * (-(close-close[-30])/vol_short), -20, +20)`; crypto floor 0. Weight: **~5%** (0.5x trend bucket). Sleeve: all. Diversification: explicit "long-term up + short-term dip" gate; Chan reports adding this MR filter to 12m TSMOM improved Sharpe and added 7 profitable contracts. Cheap turnover -> 5M-viable.

**Fitschen Intraday Hourly z-Score Trend** — Fitschen Ch.3, L3187-3214 (Table 3.8). Params: SMA10, stdev10 on **60M** bars. Fit: 60M primary; 5M only with the day-close exit. Mapping: `z = (close - SMA10)/stdev10` (already vol-normalised); `f = z * scalar` (avg|f|~10); cap +/-20; crypto floor 0; hold ~1 day (decay/exit at session close). Weight: **6-8%**. Sleeve: US equities/ETFs primary; crypto only after per-instrument trend-vs-revert test. Diversification: same statistic as Bollinger/z-score reversion but used as an intraday **trend** breakout — opposite sign — a genuinely distinct rule. Carries a reusable meta-insight: measure trend-vs-revert per instrument/timeframe and set the sign accordingly.

**Buy-strength: close-in-upper-range, hold N** — Williams "Long-Term Secrets", L5701-5748 (Truth 1). Params: X% (upper 65%), hold `N in {5,10,15,20}` (~10). Fit: 5M/60M/daily (timeframe-agnostic; held not per-bar -> 5M cost-OK). Mapping: `f0 = (close - mid)/(0.5*range)` in [-1,1] (undefined range -> 0); `f = scalar*f0` (avg|f|~10); cap +/-20; hold via EWMA/decay ~N bars; crypto floor 0. Weight: **8-10% (best momentum keeper)**. Sleeve: all. Diversification: naturally bounded, continuous, bar-internal-position momentum — distinct from EWMAC/TSMOM (price-change based); robust cross-market. *(Truth-2, buy new X-day highs, is Donchian/52-wk — already in catalog, do not add.)*

**Pullback reversal to 25ema** — Volman price-action, L1054-1094, 1256+. Params: EMA25 slope>0, 50-60% retrace, harmony filter. Fit: 5M/60M/daily all viable. Mapping: in EWMAC-uptrend, `f = +trend_sign * clip(retrace_frac in [0.4,0.6]) * exp(-|price-EMA25|/(c*ATR))` with harmony filter (avg pullback bar-range <= avg dominant-swing bar-range); standardise -> scalar to avg|f|~10; cap +/-20; held continuously (dip depth). Weight: **~7% (strongest price-action keeper)**. Sleeve: all (crypto buy-the-dip). Diversification: explicit dip-buy entry with EMA25 tag + Fib + harmony; lowest turnover / best cost profile of the price-action set; distinct from EWMAC crossover.

**Powerbar (wide-range trend bar) breakout** — Volman, L2600, L2856. Params: `range/ATR14 > k~1.5`, close_loc=(close-low)/(high-low). Fit: 60M primary; 5M weak; daily OK. Mapping: `signal = dir*(range/ATR14 - k)*(2*close_loc-1)`, dir=sign(close-open); gate to EWMAC sign; standardise by rolling std; scalar avg|f|~10; cap +/-20; emit pulse, decay ~6 bars. Weight: **~5%**. Sleeve: all (crypto long powerbars only). Diversification: single-bar range-expansion + close-location; not a channel/MA cross.

**Pattern-break combi (powerbar + inside bar)** — Volman, L4584-4628. Mapping: `signal = dir * (range_pb/ATR) * (1 - range_inside/range_pb)`, require EWMAC alignment; standardise; scalar; cap +/-20; decay ~6 bars. Fit: 60M primary; 5M borderline. Weight: **~4%**. Sleeve: all. Diversification: 2-bar continuation conjunction — higher-conviction, lower-frequency than powerbar/inside alone, better cost survivability. *(Subsumes the standalone inside-bar variant.)*

**Pattern-break pullback (breakout retest continuation)** — Volman, L4089+ / Fig 5.6. Mapping: on Donchian(M) break, arm; if within K~6 bars price retraces to within 0.25*ATR of the broken level then a new bar takes out the local swing extreme, emit `signal = dir*break_strength(range/ATR)`; standardise; scalar; cap +/-20; decay ~5 bars. Fit: 60M primary; 5M weak. Weight: **~3%**. Sleeve: all. Diversification: retest gate cuts false-break whipsaw vs raw breakout. *(Fold "ceiling test" into this — same mechanic.)*

**Greatest Swing Value (GSV) breakout** — Williams, L2714-2829. Params: buy_swing = High-Open on down-close bars, sell_swing = Open-Low on up-close bars; 4-bar avg; `buyStop = open + m*avgBuySwing`, m~1.0-1.2. Fit: daily native; 60M feasible; 5M cost-fragile. Mapping: `f0 = (price-open)/(m*avgBuySwing)` (long side), symmetric short; scalar avg|f|~10; cap +/-20; crypto floor 0. Weight: **~5-6%**. Sleeve: all. Diversification: adaptive breakout threshold from *directional* failure-swing vol — distinct from ATR/Donchian.

**Opening-Gap momentum (break beyond prior day range)** — Chan Ch.7, L156-157 (gapFutures_FSTX.m). Params: 90d C2C std, entryZ=0.1. Fit: 60M-native (open->close hold), daily-cadence signal. Mapping: `gapUp = open - prevHigh*(1+0.1*stdC2C)`; if >0 `f = clip(k*gapUp/(0.1*stdC2C*price),0,+20)` long, hold to close; crypto uses a self-defined synthetic session window. **SIGN CAUTION:** Chan's own code (`ret=pos*(op-cl)/op`, verified ~L6700) literally profits from a *fade* — test BOTH signs; use continuation as primary. Weight: **0.5x intraday sleeve** (cap combined gap exposure vs Buy-on-Gap). Sleeve: equities/ETFs + synthetic-session crypto. Diversification: triggers on the *overnight gap punching the prior session's* high/low (vs ORB's first-bar same-day range).

**Consecutive-Closes Momentum Stop-and-Reverse** — Carter Ch.14-15, L30199-30450. Params: arms at `|run|>=3` consecutive same-direction closes. Fit: 60M primary; daily OK; 5M only if costs trivial (high-turnover SAR). Mapping: `f = clip(k*run, -20, +20)`, sign flips on opposite 3-run; crypto floor 0. Weight: **low**. Sleeve: all. Diversification: run-length momentum (vs averaged-return EWMAC/TSMOM); parameter-light.

**ATR-Room Intraday Breakout (Gold Rush)** — Carter Ch.20, L37429-37560. Gate: short-frame ADX>20 AND `ATR_consumed = |price-day_open|/daily_ATR < 0.6`. Mapping: `f = sign(breakout)*20*max(0,(0.6-ATR_consumed)/0.6)`; cap +/-20; crypto long only. Also deployable as a multiplicative "range-budget-remaining" scalar on existing ORB/Donchian. Fit: 5M/60M. Weight: **moderate**. Sleeve: all. Diversification: the "<60% daily-ATR consumed" filter is the value-add — suppresses late-day chases, improves 5M cost-efficiency.

### 2B. Volatility

**Yang-Zhang OHLC realized-vol engine** — Sinclair Vol Trading, L13860-14260 (k, RS, GK, Parkinson formulas; Fig.142 efficiency up to 14x C2C). **Engine input, not a forecast.** `sigma_YZ^2 = sigma_ON^2 + k*sigma_OC^2 + (1-k)*sigma_RS^2`, `k = 0.34/(1.34+(N+1)/(N-1))`, N=20-60. Feed `sigma_YZ` as THE denominator in every vol-target and vol-scaling rule (replaces close-to-close) — sharpens *all* forecasts cheaply. Use RS+OC-only variant for 24/7 crypto (no overnight term). Fit: 5M/60M/daily (best in small-sample). Weight: **engine input (0 forecast weight — highest-leverage add)**. Sleeve: both. Diversification: closes the "no OHLC range estimator" gap.

**Leverage-effect vol-change directional forecast** — Sinclair, L4528-4535 ("equities more volatile when they decline," up to ~70% R2; short-dated 50-60%). Mapping: `dRV = first-diff of EWMA(RV_YZ)`; `d = dRV/std(dRV)`; `f = -20*clip(beta*d,-1,1)` (falling RV -> long; rising RV -> defensive/inverse-ETF); avg|f|~10. Fit: 60M/daily (5M noisy). Weight: **8-10% (cleanest new directional vol rule)**. Sleeve: **US equities/ETFs only** (exclude crypto — leverage effect weak/positive there). Diversification: forecasts *direction* from the sign of vol change (vs vol-managed sizing, which scales magnitude).

**RV term-structure slope** — Sinclair, L4528-4543, L10094-10095, L10475 (term structure upward-sloping on average, inverts in turbulence; RV mean-reverts ~8mo). Mapping: `slope = (RV_short - RV_long)/RV_long` (YZ, short 5-10 / long 40-60 bars); `s = slope/std(slope)`; `f = -20*clip(g*s)` with **asymmetric caps** (inverted slope steeper); preferred as a 0.3-1.0 multiplier on the trend sleeve. Fit: 60M/daily; 5M with long windows (trades slowly -> cost-OK). Weight: **5-8% standalone or gate**. Sleeve: equities directional; crypto flat-only-defensive when inverted. Diversification: explicit, parameter-light regime signal distinct from HMM gate.

**Overnight-variance-share jump/regime filter** — Sinclair, L14050 ("~1/6 of equity vol occurs outside the trading day; twice for ADRs"). Mapping: `share = sigma_overnight^2/sigma_YZ^2`; `z=(share-1/6)/std`; high z -> multiplier DOWN on intraday-continuation/trend rules, UP on gap-fade/overnight-reversal rules. Fit: **daily/session-boundary only** (N/A within-session, N/A crypto). Weight: **low gate, equity-only**. Diversification: variance-decomposition regime filter (vs overnight-intraday *return* signal).

**Quadrature Bandpass Filter-Bank Cycle Reversion** — Katz Ch.10, Tests 1-3. Params: log-spaced Morlet bank, periods 3-30; SNR gate `peakpower >= 1.5*peaknoise`. Mapping: power=inphase^2+inquad^2; pick peak-power period; `f = clip(scalar * -sin(phase+disp) * min(SNR/1.5,cap), -20,+20)` (fade predicted top / buy predicted bottom). Fit: 60M/daily on index-like series; **NOT 5M**. Weight: **~2% exploratory, index-ETF sleeve**. Diversification: cycle/rhythm family entirely absent from catalog; the SNR>=1.5 "is-there-a-cycle" test is independently reusable to auto-tune other rules' lookbacks.

### 2C. Mean-Reversion

**Safer Fast Mean Reversion (trend-gated + vol-attenuated)** — Carver Adv. Futures, L20138-20320. Core: `eq_t = EWMA(daily close, span=5)`; `MR_raw = eq_t - p_t`; `f = MR_raw/(p_t * sigma%_ann/16)`. **Trend gate:** if `sign(EWMAC(16,64)) != sign(f)` then `f=0`. **Vol attenuation:** `V_t = sigma_i,t / 10yr-avg-sigma_i`; `Q = empirical quantile(V_t) in [0,1]`; `M = 2 - 1.5*Q`; `f *= M`. Scalar ~20; cap +/-20; **no buffering**; bracketing limit orders; crypto floor 0 (gate already zeroes shorts in uptrend -> takes only long dips). Fit: 60M primary; 5M only on most-liquid majors/large ETFs with limit execution. Weight: **10-15% (highest-priority new add; best terminal-return fit)**. Sleeve: crypto majors (BTC/ETH/SOL long-dips) + liquid large-cap ETFs. Diversification: exactly the "fast-MR-in-trend" the brief flagged; native long-only clip ideal for crypto spot; distinct from separate HMM-gate and vol-managed-overlay entries (Sharpe 0.43-1.00, tamed skew).

**Floor-Trader Pivot R3/S3 Fade** — Carter Ch.8, L21705-21760, rule L21739/22463. Params: `P=(H+L+C)/3`, R1..R3/S1..S3 from prior H/L/C. Mapping: after penetration + >=1/4 retrace toward next level, `raw = (violated_pivot - price)/daily_ATR`; `f = C*raw` (avg|f|~10); **hard override:** touch R3 -> f=-20, touch S3 -> f=+20; decay to 0 toward next pivot; zero after 15:30 ET, flatten by close (equities); crypto keep buy side. Fit: 5M/60M. Weight: **low-moderate (0.5-0.75x)**. Sleeve: equities/ETFs (RTH pivots); crypto majors (00:00-UTC pivots). Diversification: floor-trader pivots absent from catalog; wide levels survive 5M costs.

**HOLP / LOHP Trend-Reversal** — Carter Ch.19, L35234-35320. Gate: ~20-period new high (LOHP/top) or new low (HOLP/bottom). Trigger: close through the opposite extreme of the single extreme bar. Mapping: emit bounded counter-trend pulse `f = +/-15..20` on trigger, decay toward 0 mimicking a 2-bar trailing stop; cap +/-20; crypto keep HOLP (long) only. Fit: 60M/daily; 5M noisier. Weight: **low-moderate**. Sleeve: all. Diversification: confirmation-based (close-through of an extreme bar), not a naked "looks cheap" fade — distinct from Bollinger/RSI-2.

**Internal Bar Strength (IBS) reversion** — trading_etfs, L9268-9288 (top/bottom-third-of-range confirmation). Mapping: `IBS = (Close-Low)/(High-Low)`; `f = 20*(1 - 2*IBS)` (self-normalising, E|f|~10; no extra scalar); crypto floor negative at 0. Fit: 60M/daily (5M turnover up -> weight down). Weight: **~7% (daily/60M)**. Sleeve: broad equity ETFs; crypto long leg. Diversification: HLC-only, cheap; distinct construction from Bollinger/VWAP/RSI-2/overnight.

**Smash-day reversal** — Williams, L2384-2467. BUY: bar closes below prior bar's Low; arm long at that bar's HIGH; fire when next bar trades above it. Mapping: `f0 = clip((prior_Low - smash_close)/smash_range, 0, cap)` (deeper naked close = stronger); scalar avg|f|~10; cap +/-20; hold a few bars, decay; crypto long only. Fit: 5M/60M/daily. Weight: **~4%**. Sleeve: all. Diversification: failed-breakout reversal off a single naked-close bar with next-bar confirmation.

**Hidden smash-day reversal** — Williams, L2415-2447. BUY: UP-close bar with close in LOWER 25% of range AND below its open (hidden buyer-exhaustion); trigger long above its HIGH. Mapping: `clp=(close-Low)/range`; `f0 = clip((0.25-clp)/0.25, 0, 1)`; scalar; cap +/-20; crypto long only. Fit: 5M/60M/daily. Weight: **~3%** (fires rarely). Diversification: close-location-in-range exhaustion; complements naked smash-day.

**Specialists' Trap (false congestion-breakout reversal)** — Williams, L2484-2529. Detect 5-10 bar congestion box after a trend; naked close beyond box, then within 1-3 bars price reclaims the break-bar's opposite true-extreme. Mapping: fire on snapback; magnitude ∝ `box_height/ATR` and inverse of bars-to-reversal; scalar avg|f|~10; cap +/-20; crypto buy-trap only. Fit: 5M/60M/daily. Weight: **~3%** (detection fragility, low frequency). Diversification: structured failed-range-breakout with confirmation window; not in catalog.

**Outside-day down-close + lower-open reversal** — Williams, L2277-2324 (85-90% tested accuracy w/ DoW filter). Setup: outside bar closing down; next bar opens below the outside bar's close -> buy that open. Mapping: `f0 ∝ outside_bar_range/ATR` (positive/long); scalar; cap +/-20; short hold. Fit: daily native; 60M rare; not 5M. Weight: **~3%** (very low trigger frequency — limited 1-month impact). Diversification: two-bar reversal with open-gap confirmation.

**GSV contra-trend band** — Williams, L2789-2802. Same 4-bar avgSwings, m~1.8: `f0 = -(price-open)/(m*avgSwing)`; clip |f0| at 1.25 (the 2.25*avgSwing protective stop) before scaling; cap +/-20; crypto lower-band buy only. Fit: 5M/60M native. Weight: **~3-4%; regime-gate against the GSV breakout (same trigger, opposite sign — do not run both un-gated on one asset)**. Diversification: band width set by directional failure swings (not Bollinger of close).

**False high / false low reversal (2-bar outside)** — Volman, L878-912. If `high_t>high_{t-1}` then within J~3 bars price breaks below the pre-poke bar's low -> short (mirror for long); magnitude boosted at marked S/R or round levels; scalar avg|f|~10; cap +/-20; decay ~4 bars. Fit: 60M primary; **NOT 5M** (below cost). Weight: **~2-3%**. Sleeve: equities both sides; crypto false-low bounces only. Diversification: level-keyed 2-bar trap; distinct from z-score/overnight reversals.

**MACD Price/Oscillator Divergence** — Katz Ch.7, Tests 19-21 ("dramatically different from all others"). Params: MACD EMA 12/26 signal 9; lookback len3=20. Mapping (discrete pattern -> continuous): `f = clip(scalar*(MACD_slope_z - price_slope_z)*turn_confirmation, -20,+20)`, where `turn_confirmation=+1` once MACD slope actually flips up (else 0, avoids catching knives). **Keep oscillator = MACD** (Katz found RSI/Stochastic divergence FAILED). Fit: daily/60M; 5M marginal. Weight: **~3-4% exploratory** (12.5% IS / 19.5% OOS, both sides). Sleeve: equities both sides (inverse ETFs); crypto bullish-divergence longs only. Diversification: divergence family entirely absent from catalog.

### 2D. Sectoral / Relative-Strength

**Intraday XS relative-strength opening-drive rank (gap-excluded)** — trading_etfs Ch.11 (subtract first printout from second; explicit gap-exclusion). At ~09:35 ET record %chg from prior close; at ~10:00 ET record again; `drive_i = pct(10:00) - pct(09:35)`; cross-sectional z-score; `f_i = clip(scalar*z(drive_i), -20,+20)` (avg|f|~10); sign-gate by broad-market (SPY) direction; compute once in first 30 min, HOLD session. Fit: 5M/60M. Weight: **~8% (moderate)**. Sleeve: US sector/industry ETFs (equities session only; no crypto). Diversification: strips the opening gap and ranks cross-sectionally on post-open drive — distinct from first-bar market-intraday-momentum and generic XS momentum. Low turnover (once/day) -> 5M cost-survivable.

**Realized-correlation / dispersion regime gate** — Sinclair Ch.6.3, L8303 (vol-ratio beta; index vol capped by weighted-avg constituent vol). `rho ~= (sigma_index^2 - sum w_i^2 sigma_i^2)/(sum_{i!=j} w_i w_j sigma_i sigma_j)` (or ratio `sigma_index/sum w_i sigma_i`); to percentile; **multiplier m in [0.3,1.0]** on XS-momentum/relative-strength: high rho (risk-off) -> low m + lean broad index; low rho (healthy dispersion) -> boost dispersion bets. Fit: daily/60M; heavy at 5M. Weight: **gate only (0 direct)**. Sleeve: equity/ETF cross-section. Diversification: catalog has a breadth gate but no realized-correlation/dispersion gate.

**Fitschen Bar-Scoring Composite Forecast Engine** — Fitschen Ch.8, L12667-12905 (Tables 8.1-8.3). For each criterion c (3/14/40-bar RSI, #stdevs of close vs 20-bar mean, 8-type OHLC bar class, volume, acceleration) bin historical values into >=20 equal-count bins vs realized N-bar-forward return using an **EXPANDING/OUT-OF-SAMPLE** window; live reading -> bin-mean fwd return `r_c`; `composite = mean_c(r_c)` (= expected fwd return, already a forecast); cross-sectional z-score; scalar avg|f|~10; cap +/-20; crypto floor 0. Same horizon N across criteria (N=1-3 for 5M/60M, 20-40 swing). Fit: 5M/60M/daily. Weight: **~8-10%** (exclude criteria already standalone catalog rules to avoid double-counting). Sleeve: both (needs large cross-section). Diversification: general empirical bin->forward-return combiner mapping natively to Carver. **Mandatory: expanding OOS binning — never in-sample.**

### 2E. Seasonality

**Day-of-Year Seasonal Momentum** — Katz Ch.8 (basic momentum model). For each calendar date `seasonal(t) = mean over prior years of [dailychange/ATR(50)]` on the same date; smooth with a **centered triangular MA** (no lag — inputs >=1yr old); `f = clip(scalar*seasonal(t), -20,+20)`. Live: all-past-years; backtest: leave-one-out jackknife (no lookahead). Fit: **daily-only** (no 5M edge). Weight: **~2-3%, equities/ETF, long history only**. Diversification: adaptive same-calendar-date momentum (predictive) vs catalog's responsive turn-of-month/day-of-week/time-of-day. Caveat: only ~21 daily signals in a one-month window.

### 2F. Statistical / ML

**ARIMA+GARCH rolling directional forecast** — adv_algo Ch.26 (windowLength=500, ARMA(p,q) p,q in {0..5} d=0 min-AIC, sGARCH(1,1) sged + hybrid solver, n.ahead=1). `s = mu_hat/sigma_cond`; `f = clip(scalar*s, -20,+20)` (avg|f|~10); **LAG one bar** (book look-ahead fix); crypto floor 0. Fit: **60M/daily only** (per-bar refit -> 5M infeasible on cost+compute). Weight: **~3%** (marginal live edge; matches user S26 interest). Sleeve: liquid equity indices/ETFs daily; BTC/ETH 60M long-only. Diversification: a fitted conditional-mean forecast — a new family vs smoothed-trend/HMM.

### 2G. Engine, sizing & overlays (KEEP-NEW — not +/-20 forecasts)

- **Position inertia (10% no-trade buffer)** — Carver, engine-wide. Only trade when `|target - current| > 10%` of current position. ~5% buffer on the fastest 5M sleeves. *Kills cost-only churn from per-bar re-sizing — one of the most impactful intraday-tournament adds.*
- **Half-Kelly vol targeting (cap 50%)** — Carver. `annual vol target = expected annual Sharpe` (full-Kelly) -> use **half**, hard-cap 50%; `daily = annual/16`; `Position = (f/10)*(daily_cash_vol_target/instrument_ccy_vol)*weight*IDM`. The aggressiveness dial; leaning toward full-Kelly raises terminal-return variance (tournament-useful) but blow-up risk is real with negative-skew sleeves.
- **FDM cap 2.5 + combined-forecast cap +/-20** — Carver. `combined = cap(FDM * sum(w_i f_i), -20,+20)`, `FDM = min(estimate, 2.5)`; estimate FDM from correlation priors *without a backtest* (same-rule ~0.9, same-style ~0.5, cross-style ~0.25). Adopt verbatim — stops an over-diversified blend from pinning at +/-20 (going effectively binary).
- **Cost-based turnover speed limit** — Carver. Hard (rule x instrument x cadence) admission filter. `cost budget = 1/3 of expected pre-cost SR` (~0.13 SR aggressive / 0.08 conservative); `std_cost = roundtrip_cost/annualised_vol`; `speed_limit = budget/std_cost`; **exclude any variation whose expected turnover breaches it**. Day-trading (>500 rt/yr) needs std_cost <= ~0.00025 SR — rarely viable. *The single most important governor for a 5M/60M bot; pair with position inertia.*
- **No-rule rule (constant +10 -> vol-targeted long)** — Carver. Emit f=+10 for every instrument -> risk-parity, vol-targeted long-only baseline, ~zero rule-driven turnover. Weight **5-10%** as a base beta sleeve; let vol-managed/regime gates throttle it in drawdowns (pure directional beta — hurts in a down month).
- **Volatility trailing-stop exit overlay (X*sigma)** — Carver. `Stop = high_since_entry - X*daily_price_vol`; X per instrument from cost (Table 38: X=1->~4d/turnover64 ... X=10->26wk/2). Optional holding-period governor; **X>=4 on 60M, avoid small X on 5M**.
- **Round-number magnet overlay (00/50 levels)** — Volman, L1255-1354. Multiplier `m in [0.5,1.5]` on other setups: boost when a favourable round level sits ~1 target ahead; veto when an adverse level sits just ahead. Best as a multiplier; standalone fade thin (60M, higher-priced instruments only).
- **Frantic-market / range-expansion skip gate** — Volman, L7362-7500. Multiplier `m in [0,1]`: `m = 1 - clip(frac_large_bars over last M)`; veto (m=0) when `|price-EMA25| > c*ATR` (over-extension). Applies to intraday breakout/reversal forecasts.
- **Global 0.5-ATR forecast hysteresis** — Katz half-ATR entry stop, recast as one engine setting: require price to move `0.5*ATR(50)` in the signal direction before the combined forecast may flip/increase — cuts whipsaw turnover (important at 5M).
- **Leveraged/inverse ETF decay-aware overlay** — trading_etfs Ch.2, Table 2.2 (S&P +3.163% -> 2x long -0.68%, 2x inverse -21.68%). Hard holding-horizon cap (intraday/1-2 bars) + regime multiplier shrinking toward 0 as realized vol rises, on any signal routed to a leveraged/inverse ETF. Optional decay-carry short (equities, trend-gated OFF, low weight ~3%).
- **ADX-Rising Trend Gate (White 1993)** — Katz Ch.5 Test 12. `gate=1 if ADX(18)==max(ADX(18), last 6 bars)` else attenuate (0.3-0). Overlaps efficiency-ratio/Hurst/HMM gates — enable on **at most one** trend rule to avoid double-gating.

---

### KEEP-VARIANT (fold params into existing rules or run at low weight)

| Variant | Source (verified) | One-line spec / what to adopt | Fit | Weight | Sleeve |
|---|---|---|---|---|---|
| Carver Fast MR (pure) | Carver L19481-19560 | span-5 EWMA-equilibrium, /16 daily-vol, scalar 9.3, no buffer — **run only as the engine that Safer-MR gates** (turnover ~140, vicious neg skew) | 60M limit-order only | ~0% standalone | BTC/ETH + few mega-ETFs |
| Cross-Instrument RV Spread | Carver L20700-20890 | min-var `R = rho*(sigma_b/sigma_a)`, `pDelta=R*pa-pb`, feed to any forecast, size at tau=10% | daily/60M | ~5% | equity/ETF pairs (needs short leg) |
| Carry (Carver/KMPV) | Carver Sys. Trading | `f = 30*net_return/(pct_vol*price*16)`; equities dividend-yield - r_f as static params; recompute weekly | daily | 10-15% | equities/ETFs only (no crypto) |
| Close-to-Open gap momentum | Carver | `f = 30*(Open-Close_prev)/std_daily_ret`; Carver never tested it; conflicts w/ overnight-reversal | daily | ~5% experimental | equities only |
| Half-life-calibrated z-score MR | Chan Ch.2 Ex.2.4-2.5, L44-49 | `lookback = round(-log2/lambda)` from OU regression; `f = -z` continuous (replace binary Bollinger); gate by Hurst<0.5 | any | **1.0x MR sleeve** | all (gated names) |
| Buy-on-Gap XS MR (Chan) | Chan Ch.4 L92-96 | anchor prior-day **LOW**, /90d C2C std, **Rule-2 MA20 gate** skips bad-news dumps; open->close | daily signal | 0.5x | equity + crypto long side |
| Leveraged/Inverse ETF late-day rebalancing momentum | Chan Ch.7 L163-164 | final ~15-min bar `ret=(p_T-15 - prevClose)/prevClose`; buy leveraged/inverse ETF into MOC | **5M/15M** | **0.75x (strong)** | US leveraged/inverse ETFs |
| Alexander filter (% zigzag) | Chan Ch.6 L6065-6067 | 1-param x% retracement stop-and-reverse -> graded distance-past-flip | 60M/daily | 0.25x | equities + crypto long/flat |
| ETF-vs-cointegrating-basket statarb | Chan Ch.4 L96-99 | ADF/Johansen basket vs ETF, `f=-z_spread` | 60M/interday | 0.25x | equity ETFs (short leg) |
| Cointegration CADF/Johansen pairs | adv_algo Ch.27+Ch.12 | static hedge beta, z-bands, `f=-scalar*z` | 60M/daily | ~5% | equities/inverse-ETF |
| Beta/vol-normalized sector pair | Sinclair L8298-8303 | `beta_i=sigma_i/sigma_mkt` (YZ), vol-normalized z fade | 60M/daily | low | equities only |
| ATR-Band breakout + retracement-limit entry | Katz Ch.5 Test 11 | `raw=(close-EMA22)/(3.7*ATR41)` Keltner-normalised; **anti-chase**: dampen when >1 ATR beyond band | 5M/60M/daily | ~3-5% | all |
| Slope-Turn Trend + Front-Weighted Triangular MA | Katz Ch.6 Test 21 (best OOS MA) | `f = scalar*slope(FWTMA20)/ATR50` (slope-turn, not crossover) | 60M/daily | ~3-4% | all |
| Williams Volatility Breakout | Williams L1550-1722 | `raw=(price-open)/(k*prior_bar_range)`; symmetric k~1.0 (drop per-weekday overfit) | 60M/daily | ~4-5% | all |
| OOPS! gap-reversal | Williams L2534-2660 | open outside prior range -> stop-entry at broken extreme, reversion; `f0=clip((prior_Low-open)/prior_range)` | daily/60M | ~3-4% | equities primary |
| Trade-for-failure (failed-breakout reclaim) | Williams L7362-7500 | counter-trend break then reclaim -> `f=trend_dir*reclaim_strength`; also vetoes counter-trend signals | 60M | ~2-3% | all |
| Intermarket lead-lag channel breakout | Williams L5626-5666 | trade follower off LEAD's N=14 Donchian break, exit on lead M=17 break; BTC->alt | daily/60M | ~4% | crypto (BTC->alt) + equities |
| TDM road-map | Williams L2101-2159, L3240-3343 | per-trading-day-of-month bias curve (buy TDM 18/22/1, sell TDM 12) as low-weight overlay | daily | ~3% overlay | all |
| Gap-Fill Fade | Carter Ch.6 L20696-20729 | fade open gap to prior close; buckets <4/>4 ES pts; **exclude Mon/expiry-Fri/month-start** | 5M | low-moderate | equity index ETFs |
| Range-Box Breakout (Currency Box) | Carter Ch.18 L33853-33914 | 2+2-test box + 25% re-entry confirm; **box-width measured-move target** | 60M/5M crypto | moderate | crypto majors + ETFs |
| Ping-Pong Adaptive Dual-SMA Channel | Carter Ch.16 L32116-32350 | 200/500-SMA channel; fade inside, flip to momentum on far-MA break | 5M | low | large-cap equities/ETFs |
| Pullback-in-Trend on Volume Spike (Gold Spike) | Carter Ch.20 L37600-37744 | daily-trend gate + >=1-ATR pullback + volume-climax (z>2) bar | 5M/60M | low-moderate | equities/ETFs + crypto |
| Keltner-ATR Pullback-to-Mean (RTM) | Carter L26128-26184 | mid=13-avg, width=1.5*ATR13, band-slope trend gate, `f=-k*(price-mid)/ATR13`, **squeeze-disable gate** | daily/60M (NOT 5M) | low-moderate | equities/ETFs + crypto |
| Inside-bar breakout | Volman L2858-2875 | `f = dir*(1 - range_inside/range_prior)`, EWMAC-gated | 60M only | ~2% | equities + crypto up-breaks |
| Vol-of-vol regime filter | Sinclair L3319-3947 | `VoV = std(RV)/mean(RV)`; `m_trend=1-clip(p)`, `m_meanrev=clip(p)` | 60M/daily | gate/low | both |
| Davey RSI-Gated Close Breakout | Davey Ch.3 L1034-1051 | 48-bar close-Donchian, RSI30>50 gate, anti-whipsaw spacing (RSI largely collinear) | 60M/daily | ~3-5% | all |
| Fitschen Trend-Pullback Entry | Fitschen Ch.6 L10171-10230 | 20-day trend gate + 1-bar down-close pullback -> **1.0-1.25x multiplier on EWMAC/TSMOM** | 5M/60M/daily | low (overlay) | all |
| Fitschen Congestion-Gated Gap Fade | Fitschen Ch.9 L14820-14862 | gap-down buy when 10-day range < 2*stdev20; `f=clip(-gap/ATR*scalar,0,+20)` | daily/60M | ~3-5% | equities/ETFs only |
| 10-day MA pullback buy | trading_etfs Ch.6 L4150-4179 | uptrend gate + `f=clip(20 - c*|close-SMA10|/ATR, 0, +20)`; scratch if fails to close >= MA10 | 60M/daily | ~3% | equities/ETFs + crypto |
| Volume-trend regime gate | trading_etfs L3331-3347 | 0..1 multiplier: 1 if vol>MA5>MA50 else taper to 0.3 (on breakout/trend rules) | 60M/daily | overlay | equities only |
| RF intraday classifier | adv_algo Ch.29 | 5-lag returns -> `f=clip(scalar*(2*p_up-1)*20)`, probability-graded | 60M (NOT 5M) | ~2% | crypto + long equity |

---

## 3. Duplicates & Rejected

| Name | Verdict | Why |
|---|---|---|
| Carver Value (5yr relative reversion) | REJECT | 5-year signal horizon, ~zero/neg monthly return — wrong horizon for a 1-month objective (Carver himself allocates 5%). |
| A&B early-loss-taker | REJECT | Binary long/short SAR, incompatible with continuous engine; useful piece (B*sigma trailing stop) captured by the vol trailing-stop overlay. |
| A&B early-profit-taker | REJECT | Binary; Carver warns profit targets hurt (cut trends short); MR already well-covered. |
| VIDYA volatility-adaptive EMA | REJECT | Katz's worst MA performer; at most a swappable smoother inside slope/EWMAC. |
| Half-ATR breakout-confirmation entry stop | REJECT | Execution, not a forecast — captured once as global 0.5-ATR hysteresis. |
| RV cone percentile timing | REJECT | Third expression of "fade vol / leverage effect" (dup of RV-fade + leverage-effect + vol-managed overlay). |
| RV mean-reversion carry (8-month clock) | REJECT | Un-actionable in a 1-month window; OHLCV proxy duplicates vol-managed + leverage-effect; no options leg to harvest VRP. |
| Roll-return carry via ETF proxy | REJECT | Requires futures term-structure data — outside OHLCV-spot/equity universe. |
| Half-Kelly leverage overlay (Chan) | REJECT | Sizing layer, emits no +/-20; informs the vol-target/weight step (use HALF-Kelly). |
| GARCH(1,1) conditional-vol sizing | REJECT | Sizing input, not a rule; duplicates vol-managed overlay (optionally fold into vol-target denominator). |
| Session-Open Overnight Breakout (GNG) | REJECT | Edge is the fixed 6/60-pt asymmetric stop/target the vol-sizer replaces; residual = trend + time-of-day (already in catalog). |
| Fitschen High-Vol Gap Continuation | REJECT | Continuation result is COMMODITIES-only; for stocks gaps are counter-trend (fade branch already covered). |
| XS momentum fast horizons (Carver) | DUPLICATE | Catalog has XS/residual momentum; H5/H10 net-negative after costs. Adopt only H20 scalar (108.5) + span into existing rule. |
| Skew Premium (Carver) | DUPLICATE | Catalog has realized skewness. Keep the 7-way deployment menu (absolute/demeaned/relative/XS/class-XS/aggregated/static) as a meta-template for fitting any statistic into +/-20. |
| EWMAC exact param (Carver) | DUPLICATE | Fold Table 49 per-pair scalars (10.6/7.5/5.3/3.75/2.65/1.87) + PRICE-point denominator into existing EWMAC. |
| Seasonal Crossover w/ Fast %K | DUPLICATE | Collapses onto Day-of-Year seasonal; salvage %K<25/>75 confirmation + 0.5-ATR hysteresis only. |
| Buildup / pre-breakout tension | DUPLICATE | = existing volatility-squeeze breakout (range-gate vs band-width reparam). |
| Ceiling test (broken-level retest) | DUPLICATE | Same mechanic as pattern-break pullback — fold in. |
| 25ema dominance filter | DUPLICATE | = EWMAC(1,25); reuse its sign as the shared directional gate for all price-action setups. |
| TTM Squeeze exact params | DUPLICATE | = existing squeeze rule; adopt BB(20,2) inside KC(20,1.5) + 12-period momentum direction + exit-on-fade; use squeeze-live as an MR-disable regime switch. |
| TTM Momentum + Trigger MTF | DUPLICATE | MACD zero-cross = EWMAC; fold in MTF-agreement multiplier, trigger-reversal early entry, 13-SMA close-through exit. |
| Fitschen Long-Only Dip-Buy | DUPLICATE | = Connors RSI-2 / Bollinger reversion + uptrend gate (reparam). |
| Fitschen RSI-as-Trend 53/47 band | DUPLICATE | = EWMAC/trend oscillator; extract only the ~40-bar profit-persistence as a trend-forecast decay parameter. |
| TDW open->close bias | DUPLICATE | Catalog has day-of-week; keep only as a per-weekday k/enable modulator on breakout rules. |

---

## 4. Prioritized shortlist to implement next into `strategies/engine/forecasts/`

Ranked by (diversification x terminal-return fit) / effort for a 5M/60M multi-asset book.

1. **Engine backbone bundle — cost-speed-limit + position-inertia + FDM-cap-2.5 + half-Kelly + 0.5-ATR hysteresis.** Prerequisite plumbing; makes every fast rule cost-survivable and the combine step bounded. Highest ROI, low effort.
2. **Safer Fast Mean Reversion (Carver, trend-gated + vol-attenuated).** Best standalone terminal-return fit; native long-only clip for crypto spot; reuses EWMAC(16,64) already built. Weight 10-15%.
3. **Yang-Zhang RV engine.** Drop-in denominator upgrade that sharpens *all* vol-scaled forecasts; unblocks the leverage-effect and term-structure rules. Engine input, not a weighted rule.
4. **Carver Continuous Breakout + Acceleration (paired).** Two decorrelated divergent trend rules that reuse the trend infra; Acceleration is near-free once EWMAC exists. Combined ~15-19%.
5. **Buy-strength close-in-upper-range (hold N) + Pullback-to-25ema.** The two lowest-turnover, cleanly-continuous, cross-market price-action keepers; both 5M-cost-friendly. Combined ~15-18%.
6. **Leveraged/Inverse-ETF late-day rebalancing momentum (Chan).** Monetises the leveraged/inverse ETFs already in the universe as both instrument and signal source; one round-trip/day -> 5M-survivable. 0.75x.
7. **Leverage-effect vol-change directional forecast (Sinclair).** The cleanest new *directional* volatility rule (equities/ETFs only); depends on #3. Weight 8-10%.
8. **Intraday XS opening-drive rank (gap-excluded) + Realized-correlation gate.** Adds an intraday sectoral relative-strength engine plus its natural risk-off throttle; compute-once/hold-session -> cost-cheap. Rank ~8%, gate as multiplier.

*Deferred (build after the above): Fitschen bar-scoring composite (powerful but OOS-binning-heavy), half-life z-score MR upgrade (fold into existing Bollinger), Floor-Trader-Pivot / HOLP-LOHP / IBS reversion cluster, Gold Rush ATR-room breakout, ARIMA+GARCH (S26). Equity-only shorting rules (cointegration/RV/carry) last, since crypto-spot is the primary sleeve.*