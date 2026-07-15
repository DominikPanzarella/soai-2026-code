All attribution confirmed. Sources: batch 1 = Kakushadze & Serur, *151 Trading Strategies*; batch 2 = same + Simon & Campasano (VIX) + Chan (ETF twins/CADF); batch 3 = Kaufman, *Trading Systems and Methods*; batch 4 = Altucher + Chan, *Algorithmic Trading*; batch 5 = *The Trend Following Bible* + *Original Turtle Rules*; batch 6 = Katsanos, *Intermarket Trading Strategies*. Here is the catalog.

# Strategy Catalog v3 — Book-Sourced Additions

Companion to `strategy_catalog.md` and `strategy_catalog_books.md`. This file lists **only** the KEEP-verdict strategies (NEW families/dimensions or materially-better VARIANTS of existing catalog rules) that survived adversarial verification. Rejects/duplicates are omitted; where noted they should be folded into an existing sleeve as an exit/filter rather than added as a strategy.

**Conventions.** `forecast ∈ [-20,+20]` Carver scale; crypto is SPOT long/flat so its forecast is floored at 0 (short legs are equities/inverse-ETF only). `z()` = cross-sectional or rolling z-score; `clip(x,a,b)` bounds. Weights are given in each source's own convention (% of gross forecast, sleeve %, or an x-multiplier vs a 1x reference sleeve); a normalized suggestion is added. Eligibility notes are per-instrument.

Sources keyed as: **[K151]** Kakushadze & Serur, *151 Trading Strategies*; **[Kauf]** Kaufman, *Trading Systems and Methods*; **[Alt]** Altucher, *Trade Like a Hedge Fund* (technique #s); **[Chan]** Chan, *Algorithmic Trading*; **[TFB]** *The Trend Following Bible*; **[Turtle]** *Original Turtle Trading Rules*; **[Kats]** Katsanos, *Intermarket Trading Strategies*; **[S&C]** Simon & Campasano (VIX roll).

---

## 1. Trend (adaptive & channel)

### 1.1 KAMA — Kaufman Adaptive Moving Average `KEEP-VARIANT`
- **Source:** [Kauf], adaptive-MA chapter.
- **Formula:** `ER = |P_t−P_{t−n}| / Σ|P_i−P_{i−1}|`; `SC = [ER·(2/3−2/31)+2/31]²`; `KAMA_t = KAMA_{t−1}+SC·(P_t−KAMA_{t−1})`.
- **Fit:** 60M primary + daily. Pure trend → **no 5M/15M** (fast-crypto-trend rule). 
- **Mapping:** `forecast = clip((KAMA_t−KAMA_{t−1})/(price_vol·k), −20, +20)`, k so mean|F|≈10; kill micro-reversals with a ~0.1σ slope filter. Crypto long/flat on slope>0.
- **Weight:** ~1.0% (flagship adaptive-trend representative). **Sleeve:** trend.
- **Diversification:** catalog has efficiency-ratio only as an *overlay*; this is the standalone adaptive-trend engine. Single representative of the adaptive-MA cluster (VIDYA/FRAMA/r² all verified redundant to it).

### 1.2 MAMA/FAMA — MESA Adaptive MA crossover `KEEP-NEW`
- **Source:** [Kauf] (Ehlers Hilbert-transform method).
- **Formula:** Hilbert-transform homodyne discriminator → dominant cycle phase; MAMA adapts α between fast/slow bounds by phase rate; FAMA = slower follower.
- **Fit:** 60M primary; trend-following → off 5M/15M. Crypto long when MAMA>FAMA else flat.
- **Mapping:** `forecast = clip((MAMA_t−FAMA_t)/(price_vol·k), −20, +20)`.
- **Weight:** ~1.0%. **Sleeve:** trend.
- **Diversification:** cycle-phase driver (not ER/vol) makes it genuinely decorrelated from KAMA — keep both.

### 1.3 TRIX — triple-smoothed exponential oscillator `KEEP-VARIANT`
- **Source:** [Kauf] (Hutson).
- **Formula:** triple-EMA of price, then 1-bar % change of that line.
- **Fit:** 60M trend (crypto long/flat on TRIX>0); keep off 5M.
- **Mapping:** `forecast = clip(TRIX_t/scale, −20, +20)`.
- **Weight:** 0.5% (small — zero-cross overlaps EWMAC/adjusted-trend; smoothing overlaps TSI). **Sleeve:** momentum.
- **Diversification:** low; hold small and expect correlation with trend + TSI.

### 1.4 ATR Channel Breakout — asymmetric 7/3 `KEEP-VARIANT`
- **Source:** [TFB].
- **Formula:** band = `SMA_N ± k·ATR_N`, wide up-band `k_up≈7`, tight down-band `k_dn≈3`, `N≈80–150` on 60M.
- **Fit:** 60M-native after rescaling from the book's 350; trend → never 5M.
- **Mapping:** long `clip(20·(close−SMA_N)/(k_up·ATR_N),0,20)`; short (equities/inverse ETF) `clip(−20·(SMA_N−close)/(k_dn·ATR_N),−20,0)`; decay to 0 on SMA re-cross.
- **Weight:** ~4% of gross, **equity/ETF only**. **Sleeve:** trend.
- **Diversification:** the **asymmetric** band (ride longs wide, cut shorts fast) is the edge vs catalog continuous-breakout. For crypto spot the down-band is irrelevant so it collapses to continuous-breakout — value confined to the equity short side / 3x-long wide side.

### 1.5 Multi-timeframe pullback-continuation `KEEP-NEW` ⭐
- **Source:** [TFB].
- **Formula:** HTF trend gate (daily EWMAC/MACD>0); on 60M measure pullback depth z; arm an adaptive descending buy-stop = 1 tick above prior-2-bar high, lowered each bar until filled, cancelled if HTF sign flips.
- **Fit:** explicitly 60M signal + daily/weekly filter → **strongest fit to the 60M-primary mandate**; no tick/order-book data needed.
- **Mapping:** `forecast = HTF_sign · clip(20·pullback_depth_z)`, armed only on resumption confirmation. Crypto long-only w/ HTF-up gate; equities both sides. Cap entry risk ≤~1% equity.
- **Weight:** ~8% of gross (best mandate fit). **Sleeve:** trend / retracement-continuation.
- **Diversification:** genuinely new construction — a **with-trend re-entry on a counter-trend pullback**. Catalog reversion rules are counter-trend fades and catalog trend rules are breakouts/MA crosses; nothing occupies this cell.

---

## 2. Momentum

### 2.1 Risk-adjusted (Sharpe) cross-sectional momentum `KEEP-VARIANT`
- **Source:** [K151].
- **Formula:** `R_riskadj = mean(monthly ret over 12m)/σ_12m` (equities skip most-recent month; crypto no skip).
- **Fit:** formation on 60M-aggregated monthly bars, monthly rebalance; OHLCV-clean, not an intraday-decision signal.
- **Mapping:** `forecast_i = clip(20·(2·pct_rank_i − 1), −20, 20)`; crypto floor 0 → `[0,20]`.
- **Weight:** 3–5% (low; refinement of existing 12-1, keep *alongside* not instead). **Sleeve:** cross-sectional momentum.
- **Diversification:** de-emphasizes high-vol names vs the raw cumulative-return sort — mild decorrelation from catalog 12-1.

### 2.2 TSI — Blau True Strength Index `KEEP-NEW`
- **Source:** [Kauf] (Blau).
- **Formula:** `TSI = 100·EMA_r(EMA_s(ΔP)) / EMA_r(EMA_s(|ΔP|))`, typical (s,r)=(20,10) or (25,13).
- **Fit:** 60M + daily; crypto long on TSI>0 (or >signal) else flat; equities bipolar. Very smooth → low turnover, friendly to 3x-ETF costs.
- **Mapping:** `forecast = clip(TSI/5, −20, +20)`, or `(TSI − MA3(TSI))` scaled.
- **Weight:** 1.0%. **Sleeve:** momentum.
- **Diversification:** double-smoothed momentum construction absent from catalog (Connors cumRSI/Bollinger are different builds).

### 2.3 Smoothed 3-period ROC cross-sectional ranking `KEEP-VARIANT`
- **Source:** [TFB].
- **Formula:** composite = mean of 3 ROC lookbacks on the HTF (smooths single-spike noise); rank cross-sectionally.
- **Fit:** ranking on daily/HTF, entries on 60M — standard XS cadence.
- **Mapping:** `forecast = clip(20·z_XS(composite ROC))`, gated by an absolute regime filter (benchmark > 200-EMA). Crypto long strongest only; equities long strong / short weak via inverse ETFs.
- **Weight:** ~6% of gross. **Sleeve:** cross-sectional momentum / relative-strength.
- **Diversification:** multi-horizon variant of catalog single-lookback 12-1, consistent with Carver's multi-speed philosophy — better-specified, mildly decorrelated.

---

## 3. Mean-reversion (single-name / oscillator)

### 3.1 Double-Smoothed Stochastic (Blau) `KEEP-NEW`
- **Source:** [Kauf] (Blau).
- **Formula:** double-EMA of *both* numerator `(C − LowestLow)` and denominator `(HighestHigh − LowestLow)` of Lane's raw stochastic → DS.
- **Fit:** MR framing permits **5M/15M** as well as 60M. Crypto buy oversold / exit flat on overbought; equity shorts via inverse ETFs.
- **Mapping:** `forecast = clip((50 − DS)/50 · 20, −20, +20)` (fade extremes), or signal-line-cross variant.
- **Weight:** 1.0%. **Sleeve:** mean-reversion.
- **Diversification:** double-smoothing of both stochastic terms is distinct from cumRSI and Bollinger/z-score.

### 3.2 Fisher Transform (Ehlers) `KEEP-NEW`
- **Source:** [Kauf] (Ehlers).
- **Formula:** normalize price to `x∈(−1,1)` over n bars; `Fisher = 0.5·ln((1+x)/(1−x))`; trigger = prior Fisher.
- **Fit:** MR → **5M/15M** allowed + 60M. Sharp low-lag turns suit fast crypto reversals. Crypto long on trough-cross / exit flat on peak.
- **Mapping:** `forecast = clip(−Fisher_t · 20, −20, +20)` (fade; extremes precede reversals), gated by trigger.
- **Weight:** 1.0%. **Sleeve:** mean-reversion.
- **Diversification:** Gaussianizing transform is a construction not in catalog.

### 3.3 Inverse Fisher Transform of RSI (Ehlers) `KEEP-VARIANT`
- **Source:** [Kauf] (Ehlers).
- **Formula:** `IFT = (e^{2y}−1)/(e^{2y}+1)` with `y = 0.1·(RSI−50)`; IFT∈(−1,1).
- **Fit:** 60M and (MR use) 15M. Crypto long/flat on positive IFT; bipolar clustering cuts turnover (good for leveraged ETFs).
- **Mapping:** `forecast = clip(IFT · 20, −20, +20)`.
- **Weight:** 0.5% (small — same Fisher machinery as 3.2, input differs). **Sleeve:** mean-reversion.
- **Diversification:** low vs 3.2; keep small to avoid double-counting the transform.

### 3.4 Nofri Congestion-Phase (third-day reversal) `KEEP-NEW`
- **Source:** [Kauf] (Nofri).
- **Formula:** define congestion range (top = prior high with 2 lower closes; bottom = prior low with 2 higher closes); act only inside range.
- **Fit:** daily originally; MR framing allows 60M/15M. Crypto long leg only (buy after 2 down closes inside range, exit flat on 1-bar profit or range-exit).
- **Mapping:** `forecast = ±15 fixed` only when price is inside the congestion range, else 0; **suppressed** 10 bars after a large move (10-bar net > 2× avg) and 7 bars after a false breakout.
- **Weight:** 0.75%. **Sleeve:** mean-reversion (range/congestion).
- **Diversification:** the explicit congestion-regime gate + trend-suppression make it distinct from IBS/pivot-fade — a genuinely non-trend MR engine.

### 3.5 Ten-Percent Single-Name Panic Reversion `KEEP-NEW` ⭐ (crypto)
- **Source:** [Alt] Technique 13.
- **Formula:** hard trigger `1-bar return ≤ −10%`.
- **Fit:** daily primary; also rolling 60M (MR fast-TF OK). Excellent crypto fit (frequent −10% bars) — fires often inside a 1-month window.
- **Mapping:** `forecast = clip(20·(drop%/10%), 0, 20)`; exit (a) same-day close (fast capitulation) or (b) 20-day swing hold. Long/flat.
- **Weight:** 0.75. **Sleeve:** reversion.
- **Diversification:** pure price-drop trigger, no oscillator — distinct from cumRSI / z-score / safer-fast-MR.

### 3.6 200-Day-MA Deep-Discount Reversion `KEEP-NEW`
- **Source:** [Alt] Technique 11 (contrarian variant).
- **Formula:** `close ≤ 0.8·SMA200`.
- **Fit:** daily; fixed 20-day hold matches tournament horizon exactly. **Low frequency** — rare deep capitulation, may not fire on equities in a given month (more likely crypto majors).
- **Mapping:** `forecast = +20` on trigger, decay linearly to 0 over the 20-day hold. Long/flat.
- **Weight:** 0.25 (low; caveat it may not fire). **Sleeve:** reversion.
- **Diversification:** uses %-distance-from-200dma (opposite sign to Faber/trend), not band width.

### 3.7 Four-Consecutive-Down-Days Reversal `KEEP-VARIANT`
- **Source:** [Alt] Technique 17.
- **Formula:** 4th consecutive lower close.
- **Fit:** daily or 60M; equity + crypto. Many signals/month but small edge (~0.66% avg/trade).
- **Mapping:** `forecast = +20` on the 4th lower close (scale up for streaks >4), decay to 0 next bar (1-bar hold). Long-only (short mirror is weak).
- **Weight:** 0.5. **Sleeve:** reversion.
- **Diversification:** streak-count reversal, distinct from cumRSI (which sums RSI values).

### 3.8 Five-Minute Bollinger 3%-Break Capitulation `KEEP-VARIANT`
- **Source:** [Alt] Technique 16.
- **Formula:** 5M bars, MA10 ± 2σ; trigger when price prints ≥3% *below* the lower band (decisive break, not a touch).
- **Fit:** **5M — permitted** (MR carve-out). Ideal for 24/7 crypto intraday flushes; distinct TF from catalog daily Bollinger.
- **Mapping:** `forecast = clip(20·(break%/3%), 0, 20)`; exit on reversion to band/MA or ~2-bar time-stop. Long/flat.
- **Weight:** 0.5. **Sleeve:** reversion.
- **Diversification:** intraday expression of Bollinger with a stricter entry; the 5M timeframe itself is the differentiator. (Note: the daily/60M "%b break-through" and "1.5σ index-crash" siblings were rejected as plain Bollinger duplicates — use this intraday version instead.)

### 3.9 Market-Confirmed Gap-Down Fade `KEEP-VARIANT`
- **Source:** [Alt] Systems #4/#6.
- **Formula:** at open, `open ≤ prevClose·0.95` AND prior day down AND index ETF (QQQ/SPY, or BTC for crypto basket) `open ≤ prevClose_idx·0.995`.
- **Fit:** daily/open bars; fires on any panic day → multiple shots per month.
- **Mapping:** `forecast = clip(+20·min(gap%/5%,2)/2, 0, 20)`; decay to 0 on gap-fill (touch prior close) or EOD. Long/flat.
- **Weight:** 0.5. **Sleeve:** reversion.
- **Diversification:** the cross-sectional **index-gap confirmation** distinguishes it from OOPS / overnight-intraday.

---

## 4. Mean-reversion (cross-sectional / statistical-arbitrage)

### 4.1 Regression-residual (factor-neutral) mean-reversion `KEEP-NEW` ⭐
- **Source:** [K151].
- **Formula:** each rebalance regress return vector `R` on binary cluster loadings `Λ` (+ optional risk-factor cols `Ω`) with weights `z_i = 1/σ_i²`; residual `ε_i = R − Ω(ΩᵀZΩ)⁻¹ΩᵀZR`.
- **Fit:** 60M-primary. Needs a labelled universe (GICS ETFs; L1/DeFi/meme crypto groupings).
- **Mapping:** `forecast_i = clip(−k·ε_i·z_i, −20, +20)`, floor 0 for spot; buy bottom-quantile (most-negative) residuals.
- **Weight:** 1x (reference). **Sleeve:** cross-asset MR / stat-arb.
- **Diversification:** **new capability** — strips common BTC/market/sector beta to isolate idiosyncratic reversion. Catalog ST-XS / EOD-XS do *not* factor-neutralize. This is the fuller sibling of 4.2.

### 4.2 Cluster / sector-neutral short-term reversion `KEEP-VARIANT`
- **Source:** [K151] (merges the two batches' single-cluster demean variants).
- **Formula:** per cluster (L1s ETH/SOL/AVAX/ADA; memes; DeFi; or same-sector ETFs), `R_i = ln(P_t/P_{t−L})` over `L≈24–120` 60M bars; demean `R̃_i = R_i − mean(R_cluster)`.
- **Fit:** 60M-primary (also daily/weekly). Cluster demeaning needs the labelled universe.
- **Mapping:** `forecast_i = clip(−k·R̃_i/σ_i, −20, +20)`, floor 0 for spot (only cheap `R̃<0` names get +forecast); k so most-negative residual ≈ +20; flat cluster-wide when no cheap name. Symmetric short leg equities-only.
- **Weight:** 0.5x (4–6%). **Sleeve:** cross-sectional MR.
- **Diversification:** scopes the demean to a *correlated cluster* rather than the whole universe (vs catalog ST-XS). Lighter/faster version of 4.1 — run one, not both, unless capacity allows.

### 4.3 Volume-gated cross-sectional reversion `KEEP-VARIANT`
- **Source:** [K151] (merges batch-1 weekly + batch-2 60M variants).
- **Formula:** volume ratio `v_i = ln(V/V_prior)` over the formation window; keep only **upper-half-by-v_i** names (biggest expansion = strongest overreaction), then apply reversion on that subset.
- **Fit:** 60M-primary (or weekly). Volume from OHLCV (both crypto and equities).
- **Mapping:** `forecast_i = clip(−k·(R_i − R_mkt)/σ_i, −20, +20)` on gated names, else 0; long-only keeps the losers (`R_i ≪ R_mkt`). Short-winners leg equities-only. (OI leg from the book dropped — no OI in OHLCV.)
- **Weight:** 0.5x (3–4%). **Sleeve:** cross-sectional MR.
- **Diversification:** genuine **volume gate** on top of ST-XS — not present in catalog as a gate.

### 4.4 CADF-Cointegrated ETF Spread w/ Half-Life Time-Stop `KEEP-VARIANT`
- **Source:** [Chan] Examples 3.6/7.2/7.5 (GLD/GDX, half-life ~10d).
- **Formula:** OLS hedge `h` on train window, confirm CADF@95%; spread `s = P_A − h·P_B`; z on train mean/std; hard time-stop = OU half-life `ln(2)/θ`.
- **Fit:** daily; ETF pairs long/short. Crypto spot: trade the cheap leg unilaterally.
- **Mapping:** `forecast = clip(−13.3·z, −20, +20)`, enter `|z|≥1`, exit `|z|≤0.5`. Crypto: apply to cheap leg only, clip `[0,20]`.
- **Weight:** 0.5. **Sleeve:** relative-strength / stat-arb.
- **Diversification:** static CADF-validated hedge + statistically-derived time-stop, vs catalog Kalman-pairs' dynamic filter.

### 4.5 Cross-listed ETF-twin spread reversion `KEEP-VARIANT`
- **Source:** [Chan] (pairs framework).
- **Formula:** same-underlying twins only (SPY/IVV/VOO, QQQ/QQQM, GLD/IAU). `x = ln(P1/P2)`, rolling mean/σ on bar closes; `z = (x−mean)/σ`.
- **Fit:** 15M OK (bar-close z avoids the HFT bid/ask requirement). Equity/ETF sleeve.
- **Mapping:** `forecast_cheaper = clip(−k·z, −20, +20)`, entry `|z|>2`, exit toward 0; hold cheaper twin long, flat otherwise.
- **Weight:** 0.5. **Sleeve:** equity-ETF.
- **Diversification:** economically-identical twins → near-zero divergence risk vs Kalman pairs, but tiny per-trade edge. Safe, low-vol diversifier.

### 4.6 Unilateral Ratio-Pairs (trade only the volatile leg) `KEEP-VARIANT`
- **Source:** [Alt] Technique 2.
- **Formula:** `R = P_A/P_B`; `z = (R − MA20(R))/std20(dev)`; trade only volatile leg A.
- **Fit:** daily (60M viable). Long/flat on the volatile leg works for crypto (buy the leg on dips).
- **Mapping:** `forecast_A = clip(−13.3·z, −20, +20)` gated by `|same-day move of A| ≥ 2%`; clip `[0,20]` for crypto; exit `|z|<0.5`.
- **Weight:** 0.75. **Sleeve:** relative-strength.
- **Diversification:** static single-leg execution, no dynamic hedge — distinct from Kalman-pairs.

---

## 5. Volatility & carry (short-vol, vol-breakout)

### 5.1 VIX term-structure / VRP short-vol carry (SVXY) `KEEP-VARIANT` ⭐
- **Source:** [S&C] (roll thresholds) + [K151] (VRP). Combines the two SVXY signals (slope-based + level-based).
- **Formula:** roll proxy `D = (P_short − P_long)/T` from VIXY vs VIXM closes; `VRP = VIX_level − realized_vol(SPY, 21d)`.
- **Fit:** daily-only. Equity-ETF sleeve.
- **Mapping (slope):** `forecast_SVXY = clip(+k·(D−0.05), 0, 20)` — long inverse-vol when contango `D>0.10`, scale with D, exit 0 when `D<0.05`, hard 0 in backwardation. **Mapping (level):** `forecast_SVXY = clip(+k·VRP, 0, 20)` when `VRP>0` AND contango. **Mandatory vol-spike drawdown stop** on both.
- **Weight:** 0.5 each (or blend to one SVXY sleeve ≤0.5). **Sleeve:** equity-ETF (carry/vol).
- **Diversification:** concrete SVXY long/flat implementation of catalog "term-structure vol" — fills the carry/vol harvesting gap. High terminal-return potential in a calm month; tail-risky, so hard stop is non-negotiable.

### 5.2 Volatility System (Bookstaber ATR jump) `KEEP-NEW`
- **Source:** [Kauf] (Bookstaber).
- **Formula:** compare `(C_t − C_{t−1})` to `k·ATR_{t−1}`, `k≈3`.
- **Fit:** 60M/daily (vol breakout, **not** MR → no 5M/15M). `k≈3` keeps signals rare (good for leveraged ETFs). Crypto long on upside jump, exit flat on downside jump.
- **Mapping:** `forecast = +20` if `(C_t−C_{t−1}) > k·ATR_{t−1}`; `−20` (or flat crypto) if `< −k·ATR_{t−1}`; hold otherwise.
- **Weight:** 1.0%. **Sleeve:** volatility.
- **Diversification:** close-change-vs-prior-ATR jump is distinct from channel breakouts (Donchian/Keltner/ORB/squeeze).

### 5.3 Outside-Month Volatility Reversion `KEEP-NEW`
- **Source:** [Alt] Technique 12 ("Outside Month").
- **Formula:** prior month HIGH > high two months ago AND prior month LOW < low two months ago (an outside month).
- **Fit:** monthly bars; coarse — effectively a whole-month regime tilt (prior month qualified → long all month, else no trade).
- **Mapping:** `forecast = +15/+20` on the index from first to last trading day of the current month if prior month was outside. Long/flat.
- **Weight:** 0.25 (slow regime overlay, not standalone alpha). **Sleeve:** volatility.
- **Diversification:** vol-expansion-to-reversion monthly pattern not in catalog.

---

## 6. Carry

### 6.1 Bond-ETF carry / roll-down rotation `KEEP-NEW`
- **Source:** [K151] (carry family; OHLCV proxy).
- **Formula:** slope proxy `S = trailing risk-adj return(TLT/IEF) − trailing risk-adj return(SHY)` over ~60–120d (no yield feed).
- **Fit:** daily-only. Equity-ETF sleeve.
- **Mapping:** `forecast_top-tier = clip(+k·S, −20, +20)` — long the top-carry duration ETF when `S>0`, rotate to SHY/flat when the slope proxy inverts.
- **Weight:** 0.5 (carry is proxied not exact → cap weight). **Sleeve:** equity-ETF.
- **Diversification:** **no carry sleeve exists in catalog** — new family. Fixed-income return stream, low correlation to crypto/equity trend.

---

## 7. Value

### 7.1 Long-horizon (5yr) value / reversal `KEEP-NEW`
- **Source:** [K151].
- **Formula:** `v_i = P(t−5y)/P(t)`; long long-term losers (high v).
- **Fit:** 5yr lookback, monthly rebalance — effectively a static long basket over the 1-month window; weak within-window responsiveness. Crypto restricted to BTC/ETH (only majors have 5y history); equities/ETFs with ≥5y.
- **Mapping:** `forecast_i = clip(20·z(v_i), 0, 20)` long-only.
- **Weight:** 2–3% (low; slow diversifier — **horizon-mismatch caveat**: barely moves over one month). **Sleeve:** value.
- **Diversification:** **fills a family gap** (no explicit value strategy in catalog), but treat as a slow diversifier only given the 1-month objective.

---

## 8. Sectoral / relative-strength / intermarket

### 8.1 R-squared "selectivity" double-sort rotation `KEEP-NEW`
- **Source:** [K151].
- **Formula:** selectivity `= 1 − R²` from regression vs SPY/BTC factor; double-sort on `α` and selectivity (coarsen the book's 5×5 to 2×2/3×3 for a dozens-sized ETF universe).
- **Fit:** 1yr daily/weekly regression, monthly rebalance; OHLCV-clean, not intraday.
- **Mapping:** `forecast_i = clip(20·z(0.5·z(α_i) + 0.5·z(1−R²_i)), 0, 20)` — long the low-R²/high-α basket (thematic/leveraged/vol ETFs are naturally low-R²). Long-only.
- **Weight:** 3–4%. **Sleeve:** sectoral/relative-strength.
- **Diversification:** **new selection dimension** (selectivity) not in catalog. (The plain Jensen-α rotation sibling was rejected as collinear with catalog residual-momentum — the R² dimension is what earns this a slot.)

### 8.2 Relative Rotation Graph (RS-Ratio / RS-Momentum) rotation `KEEP-VARIANT`
- **Source:** [Kats].
- **Formula:** per name vs benchmark, JdK RS-Ratio (normalized smoothed RS ≈100) and RS-Momentum (normalized ROC of RS-Ratio ≈100).
- **Fit:** daily/weekly native, usable as a 60M rotation overlay.
- **Mapping:** `raw = (RS-Ratio−100) + (RS-Momentum−100)`; cross-sectionally demean; `forecast = clip(raw/xs_sd·scalar, −20, +20)`. Long Leading + Improving quadrants; size top-N by RS-Ratio. Universe: 11 SPDR sectors + leveraged/international ETFs vs SPY; crypto basket vs BTC/total-cap (long/flat).
- **Weight:** ~10% of rotation sleeve. **Sleeve:** XS relative-strength rotation.
- **Diversification:** the **RS-Momentum early signal** makes it more precise than catalog plain sector-rotation.

### 8.3 Intermarket Regression Divergence (catch-up) `KEEP-NEW` ⭐
- **Source:** [Kats].
- **Formula:** `divergence = Y_pred − Y_actual`, `Y_pred = r·(σ_Y/σ_X)·X` on a rolling %-return window (~150–300 60M bars).
- **Fit:** **strong 60M** — author demonstrates 60M ES/DAX catch-up.
- **Mapping:** `forecast = clip((divergence/rolling_sd(divergence))·scalar, −20, +20)`, scalar so mean|F|≈10. Positive extreme (lagged leader up) → +F long SEC1; negative → −F (equities/inverse) or floor 0 for crypto. Pairs: BTC→ETH/SOL, SPY→XLK/XLF, GLD→GDX/SLV.
- **Weight:** 10% of intermarket sleeve. **Sleeve:** intermarket relative-strength (MR of spread).
- **Diversification:** MR of the return-regression spread between markets — new intermarket family (catalog BTC lead-lag is a momentum spillover, opposite sign to this).

### 8.4 Intermarket Disparity Index `KEEP-VARIANT`
- **Source:** [Kats].
- **Formula:** `DSx = (SECx − MA)/MA·100` (MA~30); `ID = c·DS2 − DS1`, `c = sign(corr)`.
- **Fit:** daily-native; adequate on 60M with a scaled MA window.
- **Mapping:** `forecast = clip((ID/rolling_sd(ID))·scalar, −20, +20)`, turn-confirmed extremes.
- **Weight:** 6–8% of intermarket sleeve. **Sleeve:** intermarket relative-strength (MR of spread).
- **Diversification:** the `c=−1` branch enables **negatively-correlated pairs** (equity-ETF vs UUP/inverse; crypto vs DXY-proxy) not covered elsewhere in catalog.

### 8.5 Intraday intermarket lead-lag catch-up (30–75 min) `KEEP-VARIANT` ⭐
- **Source:** [Kats].
- **Formula:** on 60M, `gap = β·leader_return − follower_return_so_far`, `β = r·(σ_follower/σ_leader)` from rolling intraday history; lead/horizon from a rolling lead-lag table.
- **Fit:** **excellent — purpose-built for 60M/intraday primary.**
- **Mapping:** `forecast = clip((gap/rolling_sd(gap))·scalar, −20, +20)` in the leader's direction, held 1–2 bars. Follower long/flat for crypto (floor 0). Pairs: BTC→ETH/alts, SPY→sector ETFs, QQQ/DIA↔SPY.
- **Weight:** 8–10% of intermarket sleeve. **Sleeve:** intraday intermarket momentum-spillover.
- **Diversification:** materially more precise than catalog BTC lead-lag (regression-sized gate + horizon selection); direction is **momentum spillover**, opposite to the reversion of 8.3 — the two hedge each other.

---

## 9. Factor / lottery

### 9.1 Crash-Component Beta Dispersion Buy `KEEP-NEW`
- **Source:** [Alt] Technique 8 sub-systems.
- **Formula:** rolling beta of constituents (from OHLCV returns); gate on an index crash (`index close ≤ MA10 − 1.5σ`, or 1.0σ aggressive).
- **Fit:** daily; long/flat. Needs a constituent universe + rolling beta.
- **Mapping:** on the crash gate, `forecast = +20` on the top beta-decile constituents (crypto: high-beta alts when BTC crashes), size by beta rank; 0 otherwise; exit first up close or 20d.
- **Weight:** 0.4. **Sleeve:** factor/lottery.
- **Diversification:** **opposite sign to catalog BAB/low-vol** (which shorts high-beta) — a conditional high-beta tilt gated on a crash. Distinct, and fires only in stress windows.

---

## 10. Seasonality / event

### 10.1 Pre-FOMC / announcement-day equity drift `KEEP-NEW` ⭐
- **Source:** [K151] (calendar/event).
- **Formula:** known 8 FOMC dates/yr (optionally + CPI/NFP); pure calendar.
- **Fit:** event-driven; equity-ETF sleeve. Fires ~1–2× in a 1-month window.
- **Mapping:** `forecast = +20` on SPY/QQQ (or TQQQ for terminal-return) across the T-24h→release pre-announcement window, else 0. Optional gate: fire only if price > 200d MA.
- **Weight:** 0.5. **Sleeve:** equity-ETF (seasonality).
- **Diversification:** **no catalog seasonality entry covers scheduled macro-event drift** (catalog is intraday/time-of-day/day-of-week/turn-of-month only).

### 10.2 Option-Expiration-Week Trend Continuation `KEEP-NEW`
- **Source:** [Alt] Technique 14 (OED System #1).
- **Formula:** on the Friday one week before OpEx Friday: S&P500 makes an 80-day closing high AND VIX closes within 20% of its 4-month low.
- **Fit:** daily; **equity/ETF only** (needs VIX + monthly OpEx; VIX usable as a 2nd OHLCV index). Fires ~once/month. Crypto substitute untested — do not deploy on crypto.
- **Mapping:** `forecast = +15` on trigger; exit at OpEx-day close one week later.
- **Weight:** 0.25. **Sleeve:** equity-ETF (seasonality).
- **Diversification:** calendar + low-vol trend-continuation, distinct from generic day-of-week/time-of-day.

### 10.3 Wednesday Wide-Range Midweek Reversal `KEEP-VARIANT`
- **Source:** [Alt] Technique 18.
- **Formula:** at Wednesday open, `Tuesday LOW ≤ Monday HIGH·0.95` AND `Tuesday low < Monday low`.
- **Fit:** daily; **equity/ETF only** (crypto day-of-week weak). Low frequency.
- **Mapping:** `forecast = +15` on trigger; exit after 2 consecutive up closes. Long/flat.
- **Weight:** 0.25. **Sleeve:** reversion (seasonality).
- **Diversification:** vol-expansion reversal gated to midweek — distinct from generic day-of-week via the wide-range + Mon/Tue structure filter.

---

## 11. Overlays (not standalone ±20 forecasts)

### 11.1 Inverse-volatility strategy-sleeve allocation (risk-parity) `KEEP-VARIANT`
- **Source:** [K151].
- **Formula:** `w_A ∝ 1/σ_A²` where `σ_A` = each *sleeve's* own realized return vol; normalize `Σw=1`; per-sleeve cap.
- **Role:** book-level overlay **one tier above** the catalog per-instrument vol-managed overlay (does not duplicate it) — scales each sleeve's aggregate contribution into the combined book.
- **Apply:** across all strategy sleeves; recompute on a rolling (e.g. monthly) window.
- **Structural (not a % sleeve).**

### 11.2 Ornstein-Uhlenbeck half-life holding overlay `KEEP-NEW`
- **Source:** [Chan] Example 7.5.
- **Formula:** estimate `θ` by OLS of `d(z)` on lagged demeaned level; set holding/time-stop `= ln(2)/θ` and profit target `= μ`.
- **Role:** exit/holding overlay replacing arbitrary N-day exits. **Apply to** reversion forecasts 3.5, 3.8, 4.x and existing catalog reversion strategies. Adds no new position sign. Any timeframe.

### 11.3 Donchian time-exit overlay (T-bar, no stop) `KEEP-NEW`
- **Source:** [TFB].
- **Formula:** on any breakout entry, linearly decay forecast to 0 over T bars (or hard-flatten at bar+T), independent of price; rescale T to horizon (a few trading days of 60M for a 1-month contest).
- **Role:** new exit mechanism (all catalog exits are price/stop/trail). Bounded, known holding period — attractive for a fixed 1-month window. Pair with catalog breakout/Donchian entries.

### 11.4 ATR(39) chandelier trailing-stop overlay `KEEP-VARIANT`
- **Source:** [TFB].
- **Formula:** once a position is in profit, trail a ratchet-only stop from the highest close since entry by `m·ATR_39`; breach → force forecast/position to 0.
- **Role:** per-position trailing exit, distinct from catalog portfolio-level drawdown-control. Locks in the rare large winners that drive terminal return. Optional on trend/breakout sleeves. Crypto: market-sell to flat.

> **Also fold in (do not add as strategies):** the Bollinger "first-green-close / 20d" exit (Alt T8) into the existing Bollinger sleeve; the −1% turn-of-month panic filter (Alt T12) onto the turn-of-month sleeve; the `corr<0.5` anti-crowding filter (Kats) as a rotation-sleeve overlay. Shelved for a later window: **Energy-ETF summer-demand seasonal long** (Chan; Feb–Apr calendar, does not overlap the current July tournament horizon).

---

## Top-6 shortlist to implement next

Ranked for the mandate (60M-primary, terminal return over one month, genuine diversification, reliably fires inside a 1-month window):

1. **Multi-timeframe pullback-continuation (1.5)** — best 60M-native fit of anything verified; a genuinely new with-trend-re-entry cell; ~8% gross. Highest priority.
2. **Regression-residual factor-neutral MR (4.1)** — new stat-arb capability (BTC/sector-beta stripped), 60M, fires frequently across the crypto/ETF universe; 1x reference sleeve.
3. **Intraday intermarket lead-lag catch-up (8.5)** — purpose-built for 60M, BTC→alts momentum spillover, high shot-count in a month; hedges #4.
4. **Intermarket Regression Divergence (8.3)** — demonstrated on 60M, new intermarket-MR family, decorrelated from all catalog trend/momentum (opposite sign to #3).
5. **VIX term-structure / VRP short-vol carry (5.1)** — fills the carry/vol-harvest gap with a concrete SVXY long/flat rule; strong terminal-return contribution in a calm month (hard vol-spike stop mandatory).
6. **MAMA/FAMA adaptive trend (1.2)** — decorrelated (cycle-phase) adaptive-trend engine, 60M, low turnover suits leveraged ETFs; complements existing EWMAC without collinearity.

**Runners-up** (deploy next tier): Ten-Percent Single-Name Panic Reversion (3.5) — excellent crypto fit, fires often; Fisher Transform (3.2) — clean fast-crypto MR usable at 5M/15M; Pre-FOMC drift (10.1) — reliable equity event edge. **Adopt the OU half-life overlay (11.2) immediately alongside** the reversion additions, and the inverse-vol sleeve allocation (11.1) as the book-level risk-parity layer.