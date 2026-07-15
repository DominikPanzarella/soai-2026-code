"""
═══════════════════════════════════════════════════════════════════════════════
  BUILD_UNIVERSE — systematic, rule-based construction of the tradeable universe
═══════════════════════════════════════════════════════════════════════════════

Replaces the hand-curated ``strategies/config/universe.csv`` with a REPRODUCIBLE
pipeline (SoAI-2026 spec: universe is open — "if it has data, you can trade it" —
but volume-aware slippage punishes illiquidity, so a liquidity screen is the core
gate). Three layers:

  STEP 0  candidate pool  — objective, rule-based (NOT hand-picked):
            S&P-500 constituents (GitHub CSV) ∪ a fixed set of the major liquid
            US ETFs (all categories) ∪ a leveraged-ETF whitelist (the convexity
            drivers) ∪ top liquid crypto spot pairs.
  STEP 1  fetch daily OHLCV via yfinance (cached to scratch for fast iteration).
  STEP 2  objective screens: history ≥ H, price ≥ $5, median dollar-volume
            (ADDV) ≥ $L so orders fill under the volume cap, vol floor to drop
            dead names — with the leveraged whitelist BYPASSING the vol upper
            bound so the 3x convex drivers are never screened out.
  STEP 3  emit the eligible universe (→ optionally write universe.csv).

The daily top-N selector (strategies/engine/selection.py) then runs UNCHANGED on
whatever this produces. Cadence: rebuild monthly (or once at go-live).

    python research/build_universe.py            # screen + report
    python research/build_universe.py --write     # also write universe.csv
"""
from __future__ import annotations
import sys, io, csv, json, urllib.request, argparse
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "univ_cache.parquet"
VCACHE = Path(str(CACHE).replace(".parquet", "_vol.parquet"))

# ── objective ETF pool (major liquid ETFs, by category coverage — not by return) ──
ETF_POOL = {
    "broad":     ["SPY","QQQ","DIA","IWM","VTI","VOO"],
    "sector":    ["XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLB","XLRE","XLC"],
    "thematic":  ["SMH","SOXX","ARKK","IBB","XBI","KWEB","KRE","ITB","JETS","TAN"],
    "factor":    ["MTUM","QUAL","USMV","VLUE"],
    "style":     ["IWF","IWD"],
    "reit":      ["VNQ","IYR"],
    "intl":      ["EEM","EFA","VWO","FXI","EWZ","INDA","EWJ"],
    "commodity": ["GLD","SLV","USO","DBC","DBA","GDX","SLX","UNG"],
    "bond":      ["TLT","IEF","SHY","LQD","HYG","TIP","AGG","EMB"],
    "vol":       ["VXX","UVXY","SVXY"],
}
LEVERAGED = ["TQQQ","UPRO","SOXL","TNA","FAS","TECL","LABU","UDOW","FNGU","CURE",
             "DPST","SPXL","QLD","SSO","FNGO","NAIL"]           # convex drivers (whitelist)
INVERSE   = ["SQQQ","SPXS","SOXS","SDOW"]
CRYPTO    = ["BTC","ETH","SOL","BNB","XRP","ADA","AVAX","LINK","LTC","DOGE","DOT",
             "UNI","AAVE","ATOM","NEAR","XLM","TRX","BCH","MATIC","APT"]

# ── objective screen thresholds (few, round, economically motivated) ──
HIST_MIN   = 300        # trading days of history (features warm; < FNGU's ~363)
PRICE_MIN  = 5.0        # avoid penny stocks
ADDV_MIN   = 20e6       # $20M median daily dollar volume → orders fill under volume cap
VOL_MIN    = 0.12       # annualized; drop near-dead names
VOL_MAX    = 5.0        # very wide upper (leveraged bypass anyway) — do NOT cap upside


def sp500() -> list[str]:
    for u in ("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv",
              "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            txt = urllib.request.urlopen(req, timeout=30).read().decode()
            rows = list(csv.DictReader(io.StringIO(txt)))
            return [(r.get("Symbol") or r.get("symbol")).replace(".", "-") for r in rows]
        except Exception as e:  # noqa: BLE001
            print(f"[sp500] {u[-30:]} failed: {e!r}")
    return []


def candidate_pool() -> dict[str, str]:
    """symbol → macro group tag. Objective union; de-duplicated (whitelist wins)."""
    pool: dict[str, str] = {}
    for s in sp500():
        pool.setdefault(s, "equity")
    for grp, syms in ETF_POOL.items():
        for s in syms:
            pool[s] = grp
    for s in LEVERAGED:
        pool[s] = "leveraged"
    for s in INVERSE:
        pool[s] = "inverse"
    for s in CRYPTO:
        pool[f"{s}-USD"] = "crypto"
    return pool


def fetch(pool: list[str], years: float = 2.5) -> tuple[pd.DataFrame, pd.DataFrame]:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE.exists() and VCACHE.exists():
        c = pd.read_parquet(CACHE); v = pd.read_parquet(VCACHE)
        if set(pool).issubset(set(c.columns)):
            print(f"[fetch] cache hit ({c.shape[1]} names, {c.shape[0]} days)")
            return c[pool], v[pool]
    import yfinance as yf
    print(f"[fetch] downloading {len(pool)} names ({years}y daily) via yfinance ...")
    df = yf.download(pool, period=f"{int(years)}y", interval="1d", progress=False, auto_adjust=True)
    close, vol = df["Close"], df["Volume"]
    close.to_parquet(CACHE); vol.to_parquet(VCACHE)
    return close, vol


def screen(close: pd.DataFrame, vol: pd.DataFrame, pool: dict[str, str]) -> pd.DataFrame:
    rows = []
    for s in close.columns:
        c = close[s].dropna()
        if len(c) < HIST_MIN:
            continue
        v = vol[s].reindex(c.index).fillna(0.0)
        ret = np.log(c / c.shift(1)).dropna()
        if len(ret) < 60 or ret.std() == 0:
            continue
        price = float(c.iloc[-1])
        addv = float((c * v).tail(60).median())            # 60-day median $ volume
        avol = float(ret.tail(252).std() * np.sqrt(252))
        grp = pool.get(s, "equity")
        is_lev = grp in ("leveraged", "inverse")
        # gates (leveraged whitelist bypasses the vol upper bound)
        ok = (price >= PRICE_MIN and addv >= ADDV_MIN and avol >= VOL_MIN
              and (is_lev or avol <= VOL_MAX))
        rows.append(dict(symbol=s, group=grp, price=price, addv=addv, vol=avol,
                         bars=len(c), eligible=ok, leveraged=is_lev))
    return pd.DataFrame(rows).set_index("symbol").sort_values("addv", ascending=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write strategies/config/universe.csv")
    args = ap.parse_args()

    pool = candidate_pool()
    print(f"[pool] {len(pool)} objective candidates "
          f"(S&P500 + {sum(len(v) for v in ETF_POOL.values())} ETFs + {len(LEVERAGED)} lev + "
          f"{len(INVERSE)} inv + {len(CRYPTO)} crypto)")
    close, vol = fetch(list(pool))
    scr = screen(close, vol, pool)
    elig = scr[scr.eligible]
    print(f"\n[screen] {len(elig)}/{len(scr)} pass the objective gates "
          f"(price≥${PRICE_MIN:.0f}, ADDV≥${ADDV_MIN/1e6:.0f}M, {HIST_MIN}+ bars, vol≥{VOL_MIN:.0%})")
    # class breakdown
    def cls(g):
        return "crypto" if g == "crypto" else ("commodity" if g in ("commodity",) else "equity")
    elig = elig.copy(); elig["macro"] = elig["group"].map(cls)
    print("  by macro:", elig["macro"].value_counts().to_dict())
    lev_in = [s for s in LEVERAGED if s in elig.index]
    print(f"  leveraged drivers kept: {len(lev_in)}/{len(LEVERAGED)}  -> {lev_in}")
    print(f"  dropped leveraged: {[s for s in LEVERAGED if s in scr.index and s not in elig.index]}")
    # ── CONVEX-TILT (slot-dilution mitigation): keep ALL ETFs/leveraged/crypto/
    #    commodity, but BOUND single-name equities to the top-K by liquidity, so the
    #    3x drivers are not crowded out of the runtime top-8 equity slots. ──
    SINGLE_CAP = 40
    singles = elig[elig["group"] == "equity"].sort_values("addv", ascending=False)
    non_singles = elig[elig["group"] != "equity"]
    final = pd.concat([non_singles, singles.head(SINGLE_CAP)])
    print(f"\n[convex-tilt] final systematic universe = {len(final)} "
          f"(all {len(non_singles)} ETF/lev/crypto/commodity + top-{SINGLE_CAP} single-names by ADDV)")
    print("  by macro:", final["group"].map(cls).value_counts().to_dict())
    # overlap with the hand-curated universe (shows curated ≈ the rule's output)
    curated = set()
    for l in Path("strategies/config/universe.csv").read_text().splitlines()[1:]:
        p = l.split(",")
        if len(p) > 8 and p[8] == "1":
            curated.add(p[0] if p[2] != "CRYPTO" else p[0])
    fin_syms = set(s.replace("-USD", "") for s in final.index)
    ov = curated & fin_syms
    print(f"  overlap with curated: {len(ov)}/{len(curated)} curated names reproduced by the rule")
    print(f"  rule adds (not in curated): {sorted(fin_syms - curated)[:20]}")
    print(f"  curated not kept by rule : {sorted(curated - fin_syms)[:20]}")
    scr.to_parquet(str(CACHE).replace(".parquet", "_screen.parquet"))
    if args.write:
        write_universe(final)


METAL = {"GLD", "SLV", "GDX", "SLX"}
ENERGY = {"USO", "DBC", "DBA", "UNG"}


def _row(sym, grp):
    """→ (asset_class, group, lumibot_type, long_only, cost_bps, role)."""
    if grp == "leveraged":
        return ("LEVERAGED", "leveraged", "stock", 1, 5, "core")
    if sym in METAL:
        return ("METAL", "metal", "stock", 1, 3, "core")
    if sym in ENERGY:
        return ("ENERGY", "energy", "stock", 1, 4, "core")
    if grp == "equity":
        return ("EQUITY", "equity_single", "stock", 0, 4, "core")
    return ("EQUITY", grp, "stock", 0, 4, "core")          # ETF categories → equity


def write_universe(final: pd.DataFrame):
    """Emit strategies/config/universe.csv: SYSTEMATIC equity/ETF/commodity/leveraged
    (from the convex-tilt screen) + the curated CRYPTO sleeve preserved verbatim
    (yfinance under-covers crypto history locally; live CCXT covers it) + inverse/vol
    kept benched (active=0)."""
    up = Path("strategies/config/universe.csv")
    header = up.read_text().splitlines()[0]
    # systematic active rows (exclude crypto=preserved, inverse+vol=benched by design)
    sys_rows, sys_syms = [], set()
    for sym in final.index:
        grp = final.loc[sym, "group"]
        if grp in ("crypto", "inverse", "vol"):
            continue
        ac, g, lt, lo, cost, role = _row(sym, grp)
        sys_rows.append(f"{sym},{sym},{ac},{g},{lt},{lo},{cost},{role},1")
        sys_syms.add(sym)
    # preserve curated crypto verbatim; bench convex names not in the systematic set
    crypto_rows, benched_rows = [], []
    for l in up.read_text().splitlines()[1:]:
        p = l.split(",")
        if p[2] == "CRYPTO":
            crypto_rows.append(l)
        elif (p[7] == "convex" or p[3] in ("inverse", "volatility")) and p[0] not in sys_syms:
            benched_rows.append(",".join(p[:8] + ["0"]))   # inverse/vol/COIN/MSTR, benched, deduped
    out = [header] + sorted(set(sys_rows)) + crypto_rows + benched_rows
    up.write_text("\n".join(out) + "\n")
    print(f"\n[write] universe.csv: {len(sys_rows)} systematic equity/ETF + "
          f"{len(crypto_rows)} crypto (preserved) + {len(benched_rows)} benched = "
          f"{len(sys_rows)+len(crypto_rows)} active")


if __name__ == "__main__":
    main()
