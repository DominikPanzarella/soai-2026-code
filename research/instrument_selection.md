# Systematic Instrument Selection for a One-Month Intraday (60M) Terminal-Return Book

## 1. The problem and why it matters

We run a systematic, vol-scaled, long/flat bot on a mixed universe of **crypto spot** and **US equities/ETFs**, sampled on **60-minute bars**, judged on **terminal return over a single month**. We have **OHLCV only** — no fundamentals, no order book, no true bid/ask.

The decision this document answers is *not* "what is the entry signal" but **"which subset of the universe should the bot be allowed to trade for the next month."** That decision dominates the outcome for four structural reasons:

- **Short horizon, no recovery time.** One month is ~500 hourly bars per asset. A single illiquid name that gaps, or one over-correlated cluster that all sells off together, can sink terminal return with no time to mean-revert back. Selection is the cheapest risk control we have.
- **Diversification is the only free lunch, and it is halved.** Long/flat spot cannot short, so we cannot harvest negative-correlation hedges. The *effective number of independent bets* (Carver's IDM, Baltas' diversification multiplier) is therefore driven almost entirely by (a) intra-crypto correlation and (b) the crypto-vs-equity boundary. Picking a basket that maximizes independent bets is the single highest-leverage choice.
- **Cost compounds against fast turnover.** At 60M cadence, turnover is high; a thin-spread small-cap or alt-coin quietly bleeds Sharpe. Carver's insight — **measure cost in Sharpe-ratio units** and impose a "speed limit" — is what makes cost comparable across a $2 alt-coin and SPY.
- **Estimation is noisy on one regime.** We only ever see one month of out-of-sample data. That forces us toward *few-parameter, robust, cross-sectionally-ranked* metrics rather than a finely-tuned optimizer.

The design principle, following Carver (AFTS / qoppac) and Baltas–Kosowski, is a **three-stage funnel**: **(1) gate** out anything untradeable (liquidity, minimum size, dead volatility), **(2) score/rank** survivors on cost-adjusted trend quality, **(3) greedily add** the least-correlated names to maximize independent bets until marginal diversification stalls or capacity binds. Every input below is computable from trailing OHLCV.

---

## 2. Computable per-asset metrics

Notation: `C_t, H_t, L_t, V_t` = close/high/low/volume of bar `t`; `r_t = ln(C_t/C_{t-1})` log return; window length `n` bars. Annualization factor `A = sqrt(bars_per_year)` — for 60M crypto `A = sqrt(24*365) ≈ 93.6`; for 60M equities use trading-hour bars, or compute vol on daily-resampled closes with `A = sqrt(252)`.

### 2.1 Liquidity gate — dollar volume + participation

**Average daily dollar volume (ADDV):**
```
ADDV = median_over_window( C_t * V_t )     # median is robust to wash-volume spikes
```
**Participation cap:** desired position notional must satisfy `position ≤ p_max * ADDV` (default `p_max = 1%`). Reject any asset where the *smallest* position meeting the risk target already breaches the cap.

Rationale: guarantees fills/exits over a one-month hold; Carver screens on liquidity "in risk units" (~$1.5M/day of risk, ~100 contracts/day). Compare on a **cross-sectional percentile** basis, not an absolute cutoff, because crypto vs equity nominal volumes are non-stationary and non-comparable.
*Sources:* Carver, "Static optimisation of the best set of instruments" (qoppac, 2021); QuantRocket, "Market Cap vs Dollar Volume".

### 2.2 Liquidity rank — Amihud illiquidity (ILLIQ)

```
ILLIQ = mean_over_days( |R_d| / (C_d * V_d) )     # price impact per dollar traded
```
On 60M bars: sum `|r_t| / (C_t*V_t)` intrabar per day, then average across days. Lower = more liquid. Use as a **rank within asset class** (crypto and equity ILLIQ are not on the same scale) after the ADDV hard gate.
*Source:* Amihud (2002), *J. Financial Markets*.

### 2.3 Tradeable-volatility band — realized vol vs target

Realized vol (choose one; OHLC range estimators are lower-variance):
```
sigma_cc  = std(r_t over n) * A                                  # close-to-close
sigma_park = sqrt( (1/(4 ln2)) * mean[(ln(H_t/L_t))^2] ) * A     # Parkinson
```
Position scalar = `sigma_target / sigma_i`. Because we are **long/flat spot and cannot lever**, volatility targeting is primarily a **selection filter**, not a sizing lever:
- Drop names whose `sigma_i` is *persistently far below* target (they cannot reach target risk without leverage we do not have).
- Down-weight names whose `sigma_i` is *far above* target (excessive turnover/cost, crash-prone).

Keep names whose native vol sits near the target band. The Sharpe benefit of vol scaling is concentrated in leverage-effect risk assets (equities); tail-risk reduction holds across all classes.
*Sources:* Harvey, Hoyle, Korgaonkar, Rattray, Sargaison, Van Hemert, "The Impact of Volatility Targeting" (JPM 2019); Moreira & Muir, "Volatility-Managed Portfolios" (JF 2017); Barroso & Santa-Clara, "Momentum Has Its Moments" (JFE 2015).

### 2.4 Trend-strength / predictability (signal-to-noise family)

These are close-only, unit-free, and directly comparable across crypto and equities. They are **highly correlated with each other** — treat the family as *one factor* and average 2–3, do not double-count.

**Kaufman Efficiency Ratio (cheapest, most robust on short samples):**
```
ER = |C_t - C_{t-n}| / sum_{i=t-n+1..t} |C_i - C_{i-1}|     # in [0,1]
```
ER→1 = clean directional trend; ER→0 = chop. Unsigned — pair with `sign(C_t - C_{t-n})` for direction. Default `n = 20–50` on 60M bars.
*Sources:* Kaufman KAMA (StockCharts ChartSchool; TradingView docs).

**Drift-to-vol t-statistic (signed, cost-aware threshold):**
```
SNR = (mean(r) / std(r)) * sqrt(n)     # t-stat of the mean return; sign = direction
```
`|SNR|` large ⇒ move far exceeds random-walk noise. Being a t-stat, it is comparable across assets and gives a principled threshold: require expected trend PnL > turnover cost.
*Source:* Carver, "Some more trading rules" (qoppac, 2017).

**Variance Ratio (signed, statistically testable):**
```
VR(q) = Var(q-bar overlapping returns) / (q * Var(1-bar returns))
```
`VR>1` = momentum/trending; `VR<1` = mean-reverting; RW ⇒ 1. Test with Lo–MacKinlay heteroskedasticity-robust `z*(q)`. Scan `q = 2,4,8,16` to match holding period to the horizon where each asset is most predictable.
*Source:* Lo & MacKinlay (1988), NBER w2168.

**ADX (independent confirmer — uses intrabar H/L that close-only metrics miss):** Wilder true-range / directional-movement construction; `ADX>25` trending, `<20` ranging; direction from `sign(+DI − −DI)`. Lagging and threshold-conventional — use as corroboration only. *Source:* Wilder (1978), *New Concepts in Technical Trading Systems*.

*(Hurst / R-S exponent is available but small-sample-biased; use only as a soft corroborator on long history, per Lo 1991.)*

### 2.5 Momentum (selection + direction)

**Time-series momentum (long/flat on/off gate):**
```
TSMOM_i = prod(1 + r_s) - 1  over s in [t-L, t-1];  signal = sign(TSMOM_i)
```
Include an asset only when its own trailing return is positive (natural for spot long/flat); size inversely to `sigma_i`. Default `L ≈ 20–60 trailing days` (scaled down from MOP's 12 months for the one-month horizon — with correspondingly weaker statistical power).
*Source:* Moskowitz, Ooi, Pedersen, "Time Series Momentum" (JFE 2012).

**Cross-sectional relative strength (rank the universe):**
```
R_i = prod(1 + r_s) - 1  over s in [t-J, t-2]     # skip most-recent bar (reversal)
```
Long the top-quantile winners. Needs a reasonably wide cross-section to sort meaningfully. *Source:* Jegadeesh & Titman (1993), *J. Finance*.

**52-week-high nearness (does not reverse long-run — attractive for 1-month):**
```
Nearness_i = C_t / max(High over trailing window)     # in (0,1]
```
*Source:* George & Hwang (2004), *J. Finance*.

### 2.6 Beta / defensive tilt

```
beta_i = rho_{i,m} * (sigma_i / sigma_m)              # m = universe proxy index
beta_shrunk = 0.6 * beta_i + 0.4                       # shrink toward 1
```
Build the market proxy `m` **within each asset class separately** (an equal- or dollar-volume-weighted index of that class); mixing crypto+equity into one proxy is a fragile modeling choice. Tilt inclusion/weight toward **low-beta** names so the basket is not dominated by the highest-beta crypto in a drawdown. Long/flat captures only the low-beta tilt, not the full BAB premium.
*Source:* Frazzini & Pedersen, "Betting Against Beta" (JFE 2014).

### 2.7 Cost in Sharpe-ratio units (Carver speed limit)

```
C_pct     = half_spread + commission + slippage       # fraction of notional
sigma_ann = A * std(r)                                 # annualized vol (2.3)
cost_SR   = C_pct / sigma_ann                          # risk-adjusted cost per trade
annual_drag = turnover_per_year * cost_SR
```
From OHLCV, estimate `half_spread` with the **Corwin–Schultz** high-low estimator (or Abdi–Ranaldo), and `slippage` as a fraction of ATR. **Speed-limit rule:** reject any instrument whose `annual_drag > cost_budget` (default `cost_budget = 0.10 SR/yr` against an assumed ~0.5 gross SR — i.e. ≤ one-third of gross). Because cost is normalized by vol, high-vol crypto tolerates larger absolute spreads than a low-vol ETF.
*Sources:* Carver, *Advanced Futures Trading Strategies*; Carver, "Static optimisation…" (qoppac, 2021).

### 2.8 Correlation / diversification (the objective)

Correlation matrix `H` of subsystem returns from trailing OHLCV. **Effective number of independent bets:**
```
IDM   = 1 / sqrt(w' H w) ;  N_eff = IDM^2
```
For equal-weight `N` assets with average pairwise correlation `rho_bar`:
```
N_eff = N / (1 + (N-1) * rho_bar)
```
**Baltas–Kosowski dynamic multiplier** (regime overlay): `DM_t = sqrt(N) / sqrt(1 + (N-1)*rho_bar_t)`; when trailing average correlation spikes (crypto sell-offs where everything → 1), de-risk the whole book. Cap the credit taken for low correlation and use shrinkage — correlations are unstable and jump toward 1 in crises, and a one-month window is noisy.
*Sources:* Carver, "Correlations, Weights, Multipliers" & "Portfolio construction through handcrafting" (qoppac); Baltas & Kosowski, "Demystifying Time-Series Momentum" (SSRN 2140091); Baltas, "Trend-Following, Risk-Parity and the Influence of Correlations" (SSRN 2673124).

---

## 3. Concrete composite score + monthly rebalance procedure

The procedure is a **gate → rank → greedy diversification pick**, run **per asset class** then merged, on each monthly rebalance using the trailing window.

### 3.1 Stage 1 — hard gates (drop, don't score)

For each candidate `i`, drop if **any** fails:

| Gate | Rule | Default |
|---|---|---|
| Liquidity floor | `ADDV_i ≥ ADDV_min` (percentile within class) | ≥ 40th pctile of class |
| Participation | smallest risk-target position `≤ p_max * ADDV_i` | `p_max = 1%` |
| Volatility band | `vol_lo ≤ sigma_i ≤ vol_hi` (drop dead-vol names) | `[0.5, 3.0] × sigma_target` |
| Cost speed limit | `turnover_yr * cost_SR_i ≤ cost_budget` | `cost_budget = 0.10 SR/yr` |
| History | ≥ `n_min` bars available | `n_min = 500` (60M) |

### 3.2 Stage 2 — composite rank score (survivors only)

Compute each component per survivor, **z-score cross-sectionally within asset class**, winsorize at ±3, then combine. All components oriented so higher = better.

```
z_trend  = zscore( 0.5*ER_i + 0.5*rank(|SNR_i|) )    # trend-strength family (one factor)
z_mom    = zscore( sign(TSMOM_i) * R_i )             # signed momentum; long/flat sets neg→ineligible
z_liq    = zscore( -ILLIQ_i )                        # lower illiquidity better
z_cost   = zscore( -cost_SR_i )                      # cheaper better
z_beta   = zscore( -beta_shrunk_i )                  # low-beta tilt (defensive)
z_vol    = zscore( -|ln(sigma_i / sigma_target)| )   # closeness to tradeable band

Score_i =  0.35*z_trend
         + 0.25*z_mom
         + 0.15*z_liq
         + 0.10*z_cost
         + 0.10*z_beta
         + 0.05*z_vol
```
**Eligibility:** in the long/flat mandate, force `TSMOM_i > 0` (positive trailing return) as an additional gate — a name with a negative trend has no long-only expression and is set ineligible regardless of Score.

Weights are deliberately blunt (few parameters). Trend/predictability and momentum dominate because they are the only *return-predictive* components; liquidity/cost/beta/vol are quality tilts. This ordering matches Gu–Kelly–Xiu's finding that the dominant OHLCV predictors reduce to **momentum, liquidity, and volatility**.
*Source:* Gu, Kelly, Xiu, "Empirical Asset Pricing via Machine Learning" (RFS 2020).

### 3.3 Stage 3 — greedy correlation-diversification pick (per class, then merge)

Within each class, order survivors by `Score_i` descending, then build the basket to **maximize independent bets**:

```
selected = [ argmax_i Score_i ]                      # seed with best name
repeat:
    for each candidate c not selected:
        cand_set = selected + [c]
        w        = risk-parity weights (inverse-vol) over cand_set
        portSR   = IDM(cand_set, w) * mean(Score_normalized over cand_set)
        # IDM = 1/sqrt(w' H w) from trailing return correlation matrix H
    add the c that maximizes portSR
until  portSR < 0.90 * running_max(portSR)           # marginal diversification exhausted
   or  len(selected) == N_max_class
   or  next add's marginal N_eff gain < eps
```

Then **merge across classes** and re-check the portfolio-level `IDM` over the combined set: because crypto is nearly one giant cluster, most of the independent-bet gain comes from the crypto-vs-equity split — enforce a **per-cluster cap** (handcrafting: at most `k` representatives per correlation cluster) so a mean-variance step cannot pile into one cluster.

**Default parameters (one-month tournament, limited capital):**

| Parameter | Default | Note |
|---|---|---|
| Rebalance cadence | monthly (at each tournament reset) | recompute all metrics on fresh trailing window |
| Trailing window | 60 trading days (daily) / ~500–1000 60M bars | trend/vol/corr estimation |
| `N_max` crypto | 4–6 | crypto ≈ one cluster; low marginal `N_eff` |
| `N_max` equity/ETF | 6–10 | more independent sectors |
| `sigma_target` | 15–25% annualized | tune to capital & risk budget |
| Per-cluster cap `k` | 1–2 | handcrafting robustness |
| Correlation shrinkage | shrink `H` toward class-average `rho_bar` | short-window noise |
| Diversification overlay | scale gross exposure by `DM_t`; de-risk when `rho_bar_t` spikes | Baltas–Kosowski |

### 3.4 Mapping to our engine

- **Crypto sleeve (spot, long/flat):** ADV/ILLIQ from `close*volume` on the venue's 60M bars; fractional sizing means the min-contract granularity issue mostly disappears, but exchange **minimum-notional** and wash-volume still bind — use `median` dollar volume and a percentile floor. Correlation matrix is dense/high — expect `N_eff` per crypto basket near 1–2 regardless of count.
- **Equity/ETF sleeve:** ADV in shares → dollars; watch overnight gaps not captured intraday. Beta proxy = dollar-volume-weighted index of the equity survivors only.
- **Merge & overlay:** compute combined-book `IDM` and the Baltas `DM_t`; feed `DM_t` to the existing vol-target sizing layer as a global multiplier.
- **Output:** the active universe (tickers + per-asset target vol scalar + class tag) written for the trading loop to consume.

---

## 4. Overfitting and robustness cautions

- **One regime of data.** A single month is essentially one draw. Every academic magnitude cited (MOP ~12-month persistence, Jegadeesh–Titman ~1.3%/mo, George–Hwang ~0.45%/mo, Baltas capacity figures) is from long institutional samples in futures/equities and **will not transfer** in size to hourly crypto+equity. Treat them as *directional priors*, not calibrations.
- **Prefer few parameters.** ER and the drift/vol t-stat are the most robust on short samples; Variance Ratio and Hurst need many bars for reliable inference and are marginal on one month. Combine 2–3 metrics; never trust a single one. Do not tune the composite weights on the tournament data itself.
- **Correlation instability is the biggest risk.** `H` spikes toward 1 in crypto drawdowns exactly when diversification is needed. Shrink `H`, cap the low-correlation credit, and keep the `DM_t` de-risk overlay. The greedy pick is *not* globally optimal and is sensitive to correlation error — the per-cluster cap and the 90%-of-running-max stopping rule are deliberate robustness brakes.
- **Long/flat halves realized diversification.** You cannot capture negative-correlation shorts; realized `N_eff` will be below the long/short ideal. Don't over-count intra-crypto names as independent bets.
- **Survivorship / point-in-time.** Build the candidate list from assets **listed and liquid at the rebalance date**, not today's survivors. Newly-listed crypto with short history should fail the `n_min` gate rather than be force-included; a young coin's trailing "all-time high" and beta are regime-specific and unstable.
- **OHLCV cost is estimated, not observed.** Corwin–Schultz/Abdi–Ranaldo *understate* spread for thin names and miss crypto maker/taker + funding. Keep the cost budget conservative and re-derive turnover from the actual trading rule, not a constant.
- **ILLIQ ≠ liquidity and volume ≠ liquidity.** Wash/inflated crypto volume inflates ADV; pair the ADV floor with Amihud and always rank on cross-sectional percentiles within class.

---

## 5. Implementation sketch — `research/select_universe.py`

```python
"""
select_universe.py — systematic monthly instrument selection from trailing OHLCV.
Gate -> composite rank -> greedy correlation-diversification pick, per asset class.
Writes the active universe for the trading loop. OHLCV-only; no fundamentals.
"""
from __future__ import annotations
import numpy as np, pandas as pd, json
from pathlib import Path

# ---------- config (few, blunt parameters — do NOT tune on tournament data) ----------
CFG = dict(
    window_bars=1000, bars_per_year=24*365,      # 60M crypto; use 252-day for equities
    addv_pctile=0.40, p_max=0.01,
    vol_lo=0.5, vol_hi=3.0, sigma_target=0.20,
    cost_budget=0.10, gross_SR=0.50, turnover_yr=50.0,
    n_min=500,
    weights=dict(trend=0.35, mom=0.25, liq=0.15, cost=0.10, beta=0.10, vol=0.05),
    nmax=dict(crypto=5, equity=8), cluster_cap=2, stop_frac=0.90,
    corr_shrink=0.30,
)

# ---------- per-asset metrics (each from OHLCV; see section 2) ----------
def log_ret(c): return np.log(c).diff().dropna()

def realized_vol(c, ann):  return log_ret(c).std() * np.sqrt(ann)

def efficiency_ratio(c, n=40):
    d = c.diff().abs().rolling(n).sum()
    return (c.diff(n).abs() / d).iloc[-1]

def drift_vol_tstat(c):
    r = log_ret(c); return (r.mean()/r.std())*np.sqrt(len(r))     # signed SNR

def tsmom(c, L):  return c.iloc[-1]/c.iloc[-L] - 1.0

def xsect_mom(c, J, skip=1):  return c.iloc[-1-skip]/c.iloc[-J] - 1.0

def amihud(c, v):
    r = log_ret(c); dv = (c*v).reindex(r.index)
    return (r.abs()/dv).replace([np.inf,-np.inf], np.nan).mean()

def addv(c, v):  return (c*v).median()

def corwin_schultz_spread(h, l):   # high-low effective spread estimator -> half-spread
    b = (np.log(h/l)**2).rolling(2).sum()
    g = np.log(h.rolling(2).max()/l.rolling(2).min())**2
    a = ((np.sqrt(2*b)-np.sqrt(b))/(3-2*np.sqrt(2))) - np.sqrt(g/(3-2*np.sqrt(2)))
    s = 2*(np.exp(a)-1)/(1+np.exp(a))
    return np.clip(s, 0, None).mean()/2

def cost_SR(h, l, c, ann):
    half = corwin_schultz_spread(h, l)
    slip = 0.10 * (log_ret(c).abs().mean())          # slippage ~ fraction of ATR-ish
    return (half + slip + 0.0005) / max(realized_vol(c, ann), 1e-9)

def beta_shrunk(c, cm):
    r, rm = log_ret(c), log_ret(cm)
    ix = r.index.intersection(rm.index); r, rm = r[ix], rm[ix]
    b = np.corrcoef(r, rm)[0,1]*(r.std()/rm.std())
    return 0.6*b + 0.4

# ---------- pipeline ----------
def zscore(s):  return (s - s.mean())/(s.std() + 1e-9)

def gate(df, class_proxy, cfg):
    ann = cfg["bars_per_year"]
    rows = []
    floor = df.groupby(level=0).apply(lambda g: addv(g.close, g.volume)).quantile(cfg["addv_pctile"])
    for sym, g in df.groupby(level=0):
        c, h, l, v = g.close, g.high, g.low, g.volume
        if len(c) < cfg["n_min"]: continue
        adv, sig = addv(c, v), realized_vol(c, ann)
        cs = cost_SR(h, l, c, ann)
        if adv < floor: continue
        if not (cfg["vol_lo"]*cfg["sigma_target"] <= sig <= cfg["vol_hi"]*cfg["sigma_target"]): continue
        if cfg["turnover_yr"]*cs > cfg["cost_budget"]: continue
        tm = tsmom(c, min(len(c)-1, 60))
        if tm <= 0: continue                          # long/flat: positive trend only
        rows.append(dict(sym=sym, sigma=sig, illiq=amihud(c,v), cost=cs,
                         er=efficiency_ratio(c), snr=drift_vol_tstat(c),
                         mom=xsect_mom(c, min(len(c)-1,120)), tsmom=tm,
                         beta=beta_shrunk(c, class_proxy)))
    return pd.DataFrame(rows).set_index("sym")

def score(g, cfg):
    w = cfg["weights"]
    z_trend = zscore(0.5*zscore(g.er) + 0.5*zscore(g.snr.abs()))
    g["Score"] = ( w["trend"]*z_trend + w["mom"]*zscore(np.sign(g.tsmom)*g.mom)
                 + w["liq"]*zscore(-g.illiq) + w["cost"]*zscore(-g.cost)
                 + w["beta"]*zscore(-g.beta)
                 + w["vol"]*zscore(-(np.log(g.sigma/cfg["sigma_target"]).abs())) )
    return g.sort_values("Score", ascending=False)

def idm(corr, w):  return 1.0/np.sqrt(max(w @ corr @ w, 1e-9))

def greedy_pick(ranked, rets, cfg, nmax):
    C = rets[ranked.index].corr()
    C = (1-cfg["corr_shrink"])*C + cfg["corr_shrink"]*np.mean(C.values[np.triu_indices_from(C,1)])
    sel, best, run_max = [ranked.index[0]], -np.inf, -np.inf
    while len(sel) < nmax:
        cand, cand_score = None, -np.inf
        for s in ranked.index:
            if s in sel: continue
            cs = sel + [s]
            w = 1.0/ranked.loc[cs,"sigma"]; w = (w/w.sum()).values
            ps = idm(C.loc[cs,cs].values, w) * ranked.loc[cs,"Score"].clip(lower=0).mean()
            if ps > cand_score: cand, cand_score = s, ps
        if cand is None: break
        run_max = max(run_max, cand_score)
        if cand_score < cfg["stop_frac"]*run_max: break
        sel.append(cand)
    return sel

def select_universe(ohlcv_by_class: dict[str, pd.DataFrame],
                    proxies: dict[str, pd.Series], out="active_universe.json"):
    cfg, active = CFG, []
    for cls, df in ohlcv_by_class.items():
        g = score(gate(df, proxies[cls], cfg), cfg)
        if g.empty: continue
        rets = df.reset_index().pivot(index="ts", columns="sym", values="close").pct_change()
        picks = greedy_pick(g, rets, cfg, cfg["nmax"][cls])
        for s in picks:
            active.append(dict(symbol=s, asset_class=cls,
                               vol_scalar=float(cfg["sigma_target"]/g.loc[s,"sigma"]),
                               score=float(g.loc[s,"Score"])))
    Path(out).write_text(json.dumps({"universe": active}, indent=2))
    return active

# Run monthly at each rebalance:
#   ohlcv_by_class = {"crypto": df_crypto_60m, "equity": df_equity_60m}
#   proxies        = {"crypto": crypto_index_close, "equity": equity_index_close}
#   select_universe(ohlcv_by_class, proxies)
```

**Notes on the sketch:** `df` is a MultiIndex `(sym, ts)` OHLCV frame per class; `proxies[cls]` is a dollar-volume-weighted index close built from that class only (§2.6). The greedy loop applies the diversification stop; add a `cluster_cap` check inside `greedy_pick` (reject a candidate if it is the `>k`-th member of an existing high-correlation cluster) for the handcrafting robustness brake (§3.3). Layer the Baltas `DM_t` overlay in the trading loop, not here — this file only writes *which* assets and their vol scalars.

---

### Key sources

- Robert Carver — *Advanced Futures Trading Strategies*; *Systematic Trading*; qoppac posts: "Static optimisation of the best set of instruments" (2021), "Correlations, Weights, Multipliers" (2016), "Portfolio construction through handcrafting" (2018), "Some more trading rules" (2017).
- Baltas & Kosowski — "Demystifying Time-Series Momentum Strategies" (SSRN 2140091); Baltas — "Trend-Following, Risk-Parity and the Influence of Correlations" (SSRN 2673124).
- Moskowitz, Ooi, Pedersen — "Time Series Momentum" (JFE 2012); Jegadeesh & Titman (1993); George & Hwang (2004).
- Frazzini & Pedersen — "Betting Against Beta" (JFE 2014); Ang, Hodrick, Xing, Zhang — idiosyncratic-vol (JFE 2009).
- Harvey et al. — "The Impact of Volatility Targeting" (JPM 2019); Moreira & Muir — "Volatility-Managed Portfolios" (JF 2017); Barroso & Santa-Clara — "Momentum Has Its Moments" (JFE 2015).
- Amihud (2002); Lo & MacKinlay (1988); Lo (1991) modified R/S; Kaufman ER; Wilder ADX (1978); Gu, Kelly, Xiu — "Empirical Asset Pricing via Machine Learning" (RFS 2020).