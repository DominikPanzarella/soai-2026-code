The file has 9 columns (there's a trailing `active` flag). I've cross-referenced every research candidate against the existing 80-row universe to strip duplicates and flag reactivations. Here is the plan.

---

# SoAI 2026 — Universe Expansion Plan

**Target file:** `strategies/config/universe.csv`
**Schema (actual, 9 cols):** `symbol,daily_ticker,asset_class,group,lumibot_type,long_only,cost_bps,role,active`
**Objective lens:** maximise **terminal return over one month** on 60M primary bars → weight breadth for cross-sectional/rotation strategies, but keep conviction sleeves (majors, mega-cap trend, liquid convexity) dominant. Thin/short-history names are candidates only, never core.

**De-dup note:** Research re-proposed several names **already in the file but inactive** — `DOT, UNI, AAVE, ATOM, NEAR, XLM` (crypto), `XBI, ARKK` (sector), `EEM, EFA` (intl), `SMH` (active), `JPM, CRM, COST, LLY, XOM` (single). Those are **reactivations** (flip `active` 0→1), not new rows. Genuinely new rows are listed below.

---

## 1. Crypto (CCXT spot, long/flat, no short)

Eligibility: all CCXT spot on Binance USDT pairs. `long_only=1` mandatory (hard constraint). `daily_ticker` uses the yfinance convention already in the file (`-USD`; note UNI is disambiguated as `UNI7083-USD`).

**New rows to append:**
```csv
TRX,TRX-USD,CRYPTO,crypto,crypto,1,12,core,1
BCH,BCH-USD,CRYPTO,crypto,crypto,1,12,core,1
ETC,ETC-USD,CRYPTO,crypto,crypto,1,15,convex,1
ALGO,ALGO-USD,CRYPTO,crypto,crypto,1,15,core,0
FIL,FIL-USD,CRYPTO,crypto,crypto,1,18,convex,0
HBAR,HBAR-USD,CRYPTO,crypto,crypto,1,18,convex,0
```
**Reactivate (already in file, set active=1):** `DOT, ATOM, XLM` → core; `UNI, AAVE, NEAR` → convex.

Ranking / rationale:
- **Tier 1 (activate now):** TRX, BCH — top-10 liquidity, 2017-vintage clean history, low-redundancy betas (payments/fork proxy). TRX diversifies away from smart-contract L1s; BCH feeds the existing BTC-BCH pairs/lead-lag rules.
- **Tier 2 (activate):** DOT, ATOM, XLM (reactivate) + ETC — deep books, 2016-2020 histories, good for EWMAC/TSMOM and XLM/ALGO range regimes for the z-score/MR sleeve.
- **Tier 3 (bench, active=0):** UNI, AAVE, NEAR (reactivate), ALGO, FIL, HBAR — DeFi/storage/enterprise convexity for XS-momentum dispersion, but higher idiosyncratic risk; turn on only if the alt basket needs breadth for rotation.
- **AVOID / caution:** none are thin, but FIL/HBAR (2020/2019, higher spreads → 18 bps) should stay bench; do not treat as trend anchors.

---

## 2. US Equity ETFs — broad, style, size (Massive)

`SPY, QQQ, IWM, DIA` already active. New completes the **size ladder** (SPY→MDY→IWM) and **style pair** (IWF/IWD) the catalog lacks in ETF form.

```csv
MDY,MDY,EQUITY,equity_broad,stock,1,4,core,1
IWF,IWF,EQUITY,equity_style,stock,1,3,core,1
IWD,IWD,EQUITY,equity_style,stock,1,3,core,1
```
All high ADV ($0.4–1.5B/day), no liquidity concern. IWF/IWD give the value-vs-growth relative-strength leg directly.

---

## 3. US Equity ETFs — sector & thematic (Massive)

Sectors `XLK…XLB` + `SMH` active. New thematic/commodity-equity carriers:

```csv
KWEB,KWEB,INTL_EQUITY,equity_thematic,stock,1,4,convex,1
GDX,GDX,METAL,equity_thematic,stock,1,3,convex,1
XME,XME,EQUITY,equity_thematic,stock,1,5,convex,0
TAN,TAN,EQUITY,equity_thematic,stock,1,8,convex,0
```
**Reactivate:** `XBI, ARKK` (already in file) → convex, active=1 (equal-weight biotech + high-beta growth amplitude for MR/breakout).

- GDX (ADV ~$1.5B) — levered gold beta, negative equity-beta in stress; strong diversifying trend carrier, keep active.
- KWEB (ADV ~$0.3–0.5B) — low-US-correlation, big trend/MR regimes; active.
- **AVOID as core / cap sizing:** **XME** (ADV ~$150–250M, equal-weight) — bench, strict per-bar volume cap. **TAN** (ADV ~$60–100M) — **LIQUIDITY FLAG, do not activate** unless the slippage model enforces per-bar caps; boom/bust vol is attractive but tape is too thin for tournament sizing.

---

## 4. US Equity ETFs — factor (Massive)

Entirely new family — building blocks for factor-momentum / factor-rotation without single-name risk.

```csv
MTUM,MTUM,EQUITY,equity_factor,stock,1,4,core,1
QUAL,QUAL,EQUITY,equity_factor,stock,1,4,core,1
USMV,USMV,EQUITY,equity_factor,stock,1,4,hedge,1
VLUE,VLUE,EQUITY,equity_factor,stock,1,6,core,0
SPHB,SPHB,EQUITY,equity_factor,stock,1,6,convex,0
```
- MTUM/QUAL/USMV (ADV ~$100–200M) — moderate-high liquidity, activate; USMV is the low-vol/BAB defensive leg vs SPHB.
- **AVOID as active / thin:** **VLUE** and **SPHB** (ADV ~$40–80M) — **LIQUIDITY FLAG**, bench (active=0), cap sizing. Value can be expressed via the more-liquid IWD; SPHB via TQQQ/beta names.

---

## 5. Commodity & Bond ETFs (Massive)

`GLD, SLV, USO` already active; `TLT` in file (inactive). Add the 3x duration convexity leg:

```csv
TMF,TMF,BOND,leveraged,stock,1,5,hedge,1
```
**Reactivate:** `TLT` → active=1 (core duration hedge + standalone trend asset; cash leg for TMF).

---

## 6. Volatility ETFs/ETNs (Massive) — NEW family

The catalog has a vol-managed *overlay* and a term-structure strategy but **no tradable vol instrument**. These supply the long-vol crash hedge and the short-vol carry harvester (carry family, ETF form).

```csv
VXX,VXX,VOL,volatility,stock,1,6,hedge,1
UVXY,UVXY,VOL,volatility,stock,1,7,hedge,1
SVXY,SVXY,VOL,volatility,stock,1,7,convex,0
UVIX,UVIX,VOL,volatility,stock,1,8,hedge,0
```
- **VXX** (top-3 vol product) — activate; cleanest 1x long-vol, feeds the term-structure/roll-yield signal.
- **UVXY** (ADV ~$0.5–1B, 1.5x) — activate as primary crash hedge, **regime/term-structure gated only** (negative carry).
- **SVXY** (-0.5x, ADV ~$100–150M) — short-vol carry harvester; bench until the carry sleeve is wired, gate OFF in high-vol states.
- **AVOID / tail-only:** **UVIX** (2x, steep decay) — bench, use sparingly as a strict regime-gated tail hedge. Never hold ungated.

> Note: vol ETFs are OHLCV-tradable and respect the constraints, but **every long-vol name must be held only when the regime/term-structure overlay signals** — otherwise decay silently bleeds terminal return.

---

## 7. Leveraged & inverse ETFs (Massive)

`TQQQ, UPRO, SOXL, TNA, FAS, TECL, LABU, UDOW, FNGU, CURE, DPST` (convex) and `SQQQ, SPXS, SOXS` (inverse) already active. Research adds only two genuinely new inverse hedges (SPXU broad, TZA small-cap early-warning):

```csv
SPXU,SPXU,INV_LEVERAGED,inverse,stock,1,5,hedge,1
TZA,TZA,INV_LEVERAGED,inverse,stock,1,5,hedge,0
```
- SPXU (ADV ~$150–250M) — smoother whole-book equity-beta hedge than SQQQ; activate.
- TZA (ADV ~$120M) — small-caps lead drawdowns; bench, activate only when the drawdown-control/HMM overlay wants an early-warning leg.

*(SOXS, SQQQ from research already present — no new row.)*

---

## 8. US single stocks (Massive equities)

Mega-cap trend anchors + high-beta momentum amplifiers. `AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, AVGO, AMD, NFLX` active; `JPM, CRM, COST, LLY, XOM` in file (inactive).

**New rows:**
```csv
PLTR,PLTR,EQUITY,equity_single,stock,1,4,convex,1
MU,MU,EQUITY,equity_single,stock,1,4,convex,1
MRVL,MRVL,EQUITY,equity_single,stock,1,4,convex,0
COIN,COIN,EQUITY,equity_single,stock,1,4,convex,1
MSTR,MSTR,EQUITY,equity_single,stock,1,5,convex,1
QCOM,QCOM,EQUITY,equity_single,stock,1,3,core,1
UBER,UBER,EQUITY,equity_single,stock,1,4,core,1
BAC,BAC,EQUITY,equity_single,stock,1,3,core,1
GE,GE,EQUITY,equity_single,stock,1,3,core,1
WMT,WMT,EQUITY,equity_single,stock,1,3,hedge,1
SMCI,SMCI,EQUITY,equity_single,stock,1,6,convex,0
```
**Reactivate:** `JPM, LLY, XOM, COST` → active=1 (sector diversifiers: financials/healthcare/energy/staples ballast).

- **Highest value-add:** COIN + MSTR — regulated-hours crypto beta and BTC lead-lag legs that **complement the spot-only CCXT book** (they can be flipped via inverse-of-nothing, but as long equities they add crypto convexity in equity hours). PLTR, MU — clean high-beta momentum.
- **Sector breadth (activate):** QCOM (semis), UBER (secular growth ex-tech), BAC (rate-sensitive, huge share volume), GE (industrials trend leader), WMT (defensive ballast).
- **AVOID as active / gap risk:** **SMCI** — extreme realized vol + gap/halt history; bench, size down hard even if activated. **MRVL** — fine liquidity but redundant with NVDA/AMD/AVGO/MU in the semis convexity sleeve; bench to avoid correlation clustering.

> Constraint note: all rows carry `long_only=1` to match existing file convention. Massive permits shorting single stocks/ETFs, so any equity row *can* be flipped to `long_only=0` if a short-capable strategy is enabled — but inverse/short exposure is currently expressed through the inverse-ETF sleeve (SQQQ/SPXS/SOXS/SPXU/TZA), keeping the schema uniform. Crypto rows must stay `long_only=1`.

---

## Recommended FINAL universe

Current file: 80 rows, ~52 active. Recommendation for the tournament: **~78 active instruments**, composed for cross-sectional breadth without diluting conviction.

| Macro class | Active target | Composition |
|---|---|---|
| Crypto spot | **16** | 10 current majors + TRX, BCH, ETC, DOT, ATOM, XLM |
| Equity broad/style/size | **7** | SPY, QQQ, IWM, DIA, MDY, IWF, IWD |
| Equity sector | **11** | current 11 (XLK…XLB, SMH) |
| Equity thematic | **4** | KWEB, GDX, XBI, ARKK |
| Equity factor | **3** | MTUM, QUAL, USMV |
| Single stocks | **20** | 10 current + COIN, MSTR, PLTR, MU, QCOM, UBER, BAC, GE, WMT + JPM, LLY, XOM (COST/WMT = defensive) |
| Metals/commodity | **3** | GLD, SLV, USO |
| Bonds | **2** | TLT, TMF |
| Volatility | **2** | VXX, UVXY (gated) |
| Leveraged (long) | **11** | current convex sleeve |
| Inverse (short beta) | **4** | SQQQ, SPXS, SOXS, SPXU |
| **Total active** | **~78** | |

**Balance rationale:** ~78 active gives enough names for XS-momentum / sector-&-factor rotation / relative-strength ranking to have statistical breadth, while the *role* tags keep sizing disciplined — `core` (deep-liquidity trend anchors) carry the book, `convex` (leveraged + high-beta) amplify confirmed trends for terminal return, `hedge` (vol, inverse, duration, staples) is gated on by the HMM/drawdown/term-structure overlays only.

### AVOID list (do NOT activate for the tournament)
| Ticker | Reason |
|---|---|
| **TAN** | ADV ~$60–100M — too thin for tournament sizing |
| **VLUE** | ADV ~$40–80M — thin; use IWD for value |
| **SPHB** | ADV ~$40–80M — thin; use beta ETFs/TQQQ |
| **XME** | ADV ~$150–250M equal-weight — cap-only, bench |
| **SMCI** | Gap/halt risk, extreme vol — bench, hard size-down if used |
| **UVIX** | 2x long-vol steep decay — tail-only, strict gating |
| **SVXY** | Short-vol — only with a wired, regime-gated carry sleeve |
| **FIL / HBAR** | 2020/2019 vintage, wider spreads (18 bps) — bench for dispersion only |
| **MRVL** | Liquid but correlation-redundant with NVDA/AMD/AVGO/MU |

No proposed instrument has disqualifying **short history** (all crypto ≥2019, all ETFs/stocks multi-year); the only flags are **thin liquidity** (above) and **structural decay** (leveraged/vol, managed by gating).

### Full append block (recommended active rows only)
```csv
TRX,TRX-USD,CRYPTO,crypto,crypto,1,12,core,1
BCH,BCH-USD,CRYPTO,crypto,crypto,1,12,core,1
ETC,ETC-USD,CRYPTO,crypto,crypto,1,15,convex,1
MDY,MDY,EQUITY,equity_broad,stock,1,4,core,1
IWF,IWF,EQUITY,equity_style,stock,1,3,core,1
IWD,IWD,EQUITY,equity_style,stock,1,3,core,1
KWEB,KWEB,INTL_EQUITY,equity_thematic,stock,1,4,convex,1
GDX,GDX,METAL,equity_thematic,stock,1,3,convex,1
MTUM,MTUM,EQUITY,equity_factor,stock,1,4,core,1
QUAL,QUAL,EQUITY,equity_factor,stock,1,4,core,1
USMV,USMV,EQUITY,equity_factor,stock,1,4,hedge,1
TMF,TMF,BOND,leveraged,stock,1,5,hedge,1
VXX,VXX,VOL,volatility,stock,1,6,hedge,1
UVXY,UVXY,VOL,volatility,stock,1,7,hedge,1
SPXU,SPXU,INV_LEVERAGED,inverse,stock,1,5,hedge,1
PLTR,PLTR,EQUITY,equity_single,stock,1,4,convex,1
MU,MU,EQUITY,equity_single,stock,1,4,convex,1
COIN,COIN,EQUITY,equity_single,stock,1,4,convex,1
MSTR,MSTR,EQUITY,equity_single,stock,1,5,convex,1
QCOM,QCOM,EQUITY,equity_single,stock,1,3,core,1
UBER,UBER,EQUITY,equity_single,stock,1,4,core,1
BAC,BAC,EQUITY,equity_single,stock,1,3,core,1
GE,GE,EQUITY,equity_single,stock,1,3,core,1
WMT,WMT,EQUITY,equity_single,stock,1,3,hedge,1
```
Plus **reactivations** (edit `active` 0→1 in place, no new rows): `DOT, ATOM, XLM, UNI, AAVE, NEAR` (crypto), `XBI, ARKK` (thematic), `TLT` (bond), `JPM, LLY, XOM, COST` (single).

**Bench rows** (append with `active=0`): `ALGO, FIL, HBAR` (crypto); `XME, TAN` (thematic); `VLUE, SPHB` (factor); `SVXY, UVIX` (vol); `TZA` (inverse); `MRVL, SMCI` (single).

Two new `group` values are introduced (`equity_style`, `equity_factor`, `equity_thematic`, `volatility`) and one new `asset_class` (`VOL`) — confirm the strategy loaders and per-group risk budgeting handle unseen group/asset_class strings before appending.