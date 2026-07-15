# SoAI 2026 — Systematic Multi-Strategy, Multi-Asset Trading Bot

Entry for the [SoAI 2026 AI Algorithmic Trading Competition](https://www.soc-ai.org/trading-competition/index.html).
The official entrypoint is `strategies/strategy.py` (`from strategies.strategy import Strategy`),
a Lumibot `Strategy` running a Carver-shaped systematic engine (`strategies/engine/`).

## Competition frame

The contest scores a single number — **Terminal Return**: final portfolio value
after full liquidation at the end of the trading window. Per the official template
README: **code freeze 25 Jul 2026**, live window **1–31 Aug 2026** (the public
competition page lists later dates — 9 Aug / 16 Aug–15 Sep — so confirm with the
organizers; this repo plans for the earlier freeze). No risk-adjusted metric, no
drawdown penalty; the prize pool is ranked. Eligible instruments: **crypto spot**
(CCXT, long/flat only) and **US equities & ETFs** (Massive). OHLCV bars only;
2 bps flat fee plus volume-aware slippage.

A terminal-return, ranked contest rewards the **opposite** of Carver's survival-
first prudence: maximum participation in the winning names, minimum dilution.
So this engine keeps Carver's *structure* (forecasts → combine → sizing →
portfolio → execution) but deliberately runs **fully invested (~0.97 gross,
no leverage), concentrated on the current momentum winners**, with convexity
coming from **eligible 3× leveraged bull ETFs** in the selection pool rather
than from book leverage.

## Approach

A daily (`1D`) engine trades a config-driven universe — crypto spot + US
equities/ETFs — as follows:

1. **Forecasts** (±20 frame, soft-capped): multi-speed EWMAC trend (anchor) plus
   safer-fast mean-reversion, cross-sectional momentum, a volatility breakout and
   a BTC→alt lead-lag rule, combined with forecast weights + FDM.
2. **Dynamic selection**: each rebalance, trade only the **top-N trending, liquid
   names per macro class** (`nmax_crypto=4`, `nmax_equity=8`) on a 90-day window —
   this concentration is the measured return driver.
3. **Sizing / portfolio**: handcrafted instrument weights by macro class, then a
   **full-deploy** renormalisation to the ~0.97 gross budget (spot ⇒ no leverage).
4. **Execution**: no-trade buffer + volume-aware order sizing + a gross guard and
   an **exit sweep** that liquidates any name dropped from selection (so book
   gross can never breach the no-leverage cap).

**Long/flat**: spot crypto cannot be shorted, so a bearish forecast parks capital
in cash; equities carry a breadth-gated tactical short only in a risk-off regime.

## Pipeline

```
data → volatility (EWMA σ%) → rules (forecasts ±20, soft-capped) →
forecast combine (weights + FDM) → dynamic selection (top-N per class) →
position sizing → portfolio (handcraft weights + full-deploy to 0.97 gross + long/flat) →
execution (no-trade buffer + volume-aware sizing + exit sweep + no-leverage gross guard)
```

**Active forecast rules** (`strategies/engine/forecasts/`):

| Family | Rule | Weight |
|---|---|---|
| Trend | Multi-speed EWMAC (anchor) | 0.50 |
| Reversion | Safer-fast mean-reversion | 0.20 |
| XS-momentum | Cross-sectional momentum (class-aware) | 0.12 |
| Volatility | Keltner volatility breakout | 0.10 |
| Lead-lag | BTC → alt lead-lag | 0.08 |

Other catalogued rules ship at weight 0 (research/robustness). Full sourcing and
evaluation: [`research/strategy_catalog.md`](research/strategy_catalog.md).

## Portfolio construction

- **Systematic universe** (`strategies/config/universe.csv`, ~118 names) — built
  by a REPRODUCIBLE rule, not hand-picked, via
  [`research/build_universe.py`](research/build_universe.py): an objective candidate
  pool (S&P-500 constituents + major liquid ETFs + a 3× leveraged-bull whitelist +
  the liquid crypto majors) is passed through objective screens — liquidity
  (ADDV ≥ $20M so orders fill under the volume cap), price ≥ $5, sufficient history,
  a tradeable-vol band that **bypasses the leveraged ETFs** so the convex drivers
  are never screened out — then convex-tilted (all ETF/leveraged/commodity + the
  top single-names by liquidity). Convexity comes from the eligible 3× bull ETFs
  (TQQQ/UPRO/SOXL/TNA/FAS/TECL/LABU/UDOW/FNGU/… in the equity pool). Reconstitute
  monthly (or once at go-live). The daily top-N selector then runs unchanged on it.
- **Handcrafted instrument weights**: hierarchical by macro class
  (crypto / equity / commodity), equal-risk within class.
- **Note on Carver risk knobs**: with `deploy_full=True` the vol-target (`τ`) and
  IDM cancel out in the gross renormalisation, so the book is always ~0.97 gross
  concentrated on the selected winners — a deliberate terminal-return posture, not
  a survival-first vol target. All knobs live in `strategies/engine/config.py`.

## Running locally

```bash
conda create -n soai python=3.11 -y && conda activate soai
pip install -r requirements.txt

# (re)build the systematic universe from the objective candidate pool + screens
python research/build_universe.py --write     # writes strategies/config/universe.csv

# daily multi-asset bars (crypto + equities + ETFs) for every universe ticker
python research/download_daily.py --years 3

# native Lumibot tearsheet — the report standard (daily, whole universe)
python backtest_daily.py            # writes logs/*_tearsheet.html + metrics json

# fast vectorized walk-forward twin (seconds) for A/B of selection/config changes
python research/backtest_dynamic.py
```

## Validation & honest caveats

- **Backtested performance (daily, ~25 months, native Lumibot tearsheet, systematic
  universe)**: **+170% total return / CAGR ~60% / Sharpe 2.03 / max drawdown −13% /
  ann. vol ~23%**, book gross ≤ 0.97 (no leverage) at all times.
- **⚠️ Survivorship caveat on that number.** The systematic universe is built from
  the *current* S&P-500 constituents applied to past data, so the backtest is
  survivorship-biased (it trades names known to have become index winners) — treat
  the headline as optimistic. The construction is **forward-clean for the live run**
  (it uses whatever is current at go-live). A more conservative, less-biased estimate
  of the edge is nearer the hand-curated universe's **~+141%**.
- **No book leverage.** An earlier position-accounting bug let dropped positions
  leak and silently lever the book; it is fixed (execution exit sweep), and all
  headline numbers here are the leak-free, no-leverage results.
- **Local backtest ≠ official result.** The official run is forward-live over the
  competition trading window (1–31 Aug 2026 per the template README) in the
  organizers' environment; the config is chosen for robustness, **not** fit to any
  known window (it is frozen before the live data exists, so over-fitting is the
  primary risk and is avoided by round defaults).
- **Long/flat**: in a falling month upside is capped by cash (no crypto short).
- **Slippage**: the official engine layers volume-aware slippage on top of the
  2 bps fee; execution pre-caps order size against recent volume. Treat local
  P&L as an optimistic upper bound.

## Reproducibility

- Pinned runtime deps in `requirements.txt` (the strategy imports only
  `lumibot`, `numpy`, `pandas`).
- `python -c "from strategies.strategy import Strategy"` imports with no network
  or API keys (heavy imports are deferred inside methods).
- No absolute paths, no committed secrets; the universe and all parameters are
  config files inside the repo.
