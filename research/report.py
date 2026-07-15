"""
═══════════════════════════════════════════════════════════════════════════════
  REPORT — full multi-asset portfolio tearsheet + strategy documentation
═══════════════════════════════════════════════════════════════════════════════

Builds a self-contained HTML report for the WHOLE multi-asset book (crypto +
equities + ETFs), not just the crypto-vs-BTC Lumibot smoke test. It runs the
vectorised engine twin on daily data and documents, in detail:

  * equity curve vs multiple benchmarks (BTC, SPY, 60/40, equal-weight)
  * drawdown, rolling metrics, walk-forward, Monte-Carlo month distribution
  * every instrument with its asset class, cluster and handcrafted weight
  * every forecast rule with its family, forecast weight and STANDALONE Sharpe
  * the full Carver construction parameters (vol target, IDM, FDM, caps, convex)

Output: ``research/portfolio_report.html`` (open in a browser).

Usage
-----
    python research/report.py
"""

from __future__ import annotations

import base64
import copy
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import robustness as R
from strategies.engine.config import EngineConfig
from strategies.engine.instruments import (
    load_universe, handcraft_weights, groups_map, class_map, macro_class,
)

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "research" / "portfolio_report.html"
BPY = 252.0

# Dark theme (house style).
T = dict(BG="#0b0b0b", PANEL="#0e0e0e", GRID="#232323", FG="#e6e6e6", MUT="#8a8a8a",
         ACC="#4fd1c5", ACC2="#f6ad55", ACC3="#fc8181", ACC4="#63b3ed", ACC5="#b794f4")
plt.rcParams.update({
    "figure.facecolor": T["BG"], "axes.facecolor": T["PANEL"], "savefig.facecolor": T["BG"],
    "axes.edgecolor": T["GRID"], "axes.labelcolor": T["FG"], "text.color": T["FG"],
    "xtick.color": T["MUT"], "ytick.color": T["MUT"], "grid.color": T["GRID"],
    "font.family": "monospace", "font.size": 9, "axes.grid": True, "grid.alpha": 0.4,
})


def _png(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _metrics(net: pd.Series) -> dict:
    eq = (1 + net).cumprod()
    dd = (eq / eq.cummax() - 1.0)
    downside = net[net < 0].std()
    return {
        "Total return": eq.iloc[-1] - 1.0,
        "CAGR": eq.iloc[-1] ** (BPY / len(net)) - 1.0,
        "Ann. vol": net.std() * np.sqrt(BPY),
        "Sharpe": (net.mean() / net.std() * np.sqrt(BPY)) if net.std() > 0 else 0.0,
        "Sortino": (net.mean() / downside * np.sqrt(BPY)) if downside > 0 else 0.0,
        "Max drawdown": dd.min(),
        "Calmar": (eq.iloc[-1] ** (BPY / len(net)) - 1.0) / abs(dd.min()) if dd.min() < 0 else 0.0,
    }


def _bench(px: pd.DataFrame, weights: dict) -> pd.Series:
    rets = px.pct_change(fill_method=None).fillna(0.0)
    cols = [c for c in weights if c in rets.columns]
    w = np.array([weights[c] for c in cols])
    w = w / w.sum()
    return (rets[cols] * w).sum(axis=1)


def build():
    cfg = EngineConfig()
    core = load_universe(roles=("core",))
    conv = load_universe(roles=("convex",))
    iw = handcraft_weights(core, cfg.macro_weights)
    groups = groups_map(core)
    classes = class_map(core)

    px, is_crypto = R.load_daily(core)
    px_conv, _ = R.load_daily(conv)
    px_conv = px_conv.reindex(px.index).ffill()

    coreW, idm = R.target_weights_frame(px, cfg, iw, groups, classes, is_crypto, True)
    tgt = R.add_convex(px_conv, coreW, cfg)
    px_all = px.join(px_conv[[c for c in px_conv.columns if c not in px.columns]])
    buf = cfg.execution.no_trade_buffer
    net = R.simulate(px_all, tgt, R.FEE, buffer=buf)
    eq = (1 + net).cumprod()

    # ── benchmarks ────────────────────────────────────────────────────────
    benches = {}
    if "BTC" in px: benches["BTC buy&hold"] = (1 + px["BTC"].pct_change(fill_method=None).fillna(0)).cumprod()
    if "SPY" in px: benches["SPY buy&hold"] = (1 + px["SPY"].pct_change(fill_method=None).fillna(0)).cumprod()
    if "SPY" in px and "TLT" in px:
        benches["60/40 SPY-TLT"] = (1 + _bench(px, {"SPY": 0.6, "TLT": 0.4})).cumprod()
    benches["Equal-weight all"] = (1 + _bench(px, {s: 1 for s in px.columns})).cumprod()

    # ── per-rule standalone Sharpe ─────────────────────────────────────────
    rules = [("ewmac", "Trend EWMAC"), ("acceleration", "Acceleration"),
             ("breakout", "Breakout Donchian"), ("mr", "MR z-score"),
             ("connors", "Connors RSI"), ("safer_mr", "Safer Fast MR"),
             ("xs", "XS momentum"), ("residual", "Residual mom"), ("maxlot", "MAX lottery")]
    rule_attr = {}
    for key, _ in rules:
        c2 = copy.deepcopy(cfg)
        for k in ("ewmac", "acceleration", "breakout", "mean_reversion", "connors",
                  "safer_fast_mr", "xs_momentum", "residual_mom", "max_lottery"):
            getattr(c2, k).weight = 0.0
        {"ewmac": c2.ewmac, "acceleration": c2.acceleration, "breakout": c2.breakout,
         "mr": c2.mean_reversion, "connors": c2.connors, "safer_mr": c2.safer_fast_mr,
         "xs": c2.xs_momentum, "residual": c2.residual_mom, "maxlot": c2.max_lottery}[key].weight = 1.0
        c2.convex.enabled = False
        w2, _ = R.target_weights_frame(px, c2, iw, groups, classes, is_crypto, True)
        n2 = R.simulate(px, w2, R.FEE, buffer=buf)
        rule_attr[key] = _metrics(n2)

    return dict(cfg=cfg, core=core, conv=conv, iw=iw, idm=idm, classes=classes,
                px=px, tgt=tgt, net=net, eq=eq, benches=benches, rules=rules,
                rule_attr=rule_attr)


# ─────────────────────────────────────────────────────────────────────────────
#  Charts
# ─────────────────────────────────────────────────────────────────────────────
def chart_equity(eq, benches):
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(eq.index, eq.values, color=T["ACC"], lw=2.0, label="Portfolio (net)")
    palette = [T["ACC2"], T["ACC3"], T["ACC4"], T["ACC5"]]
    for (name, s), c in zip(benches.items(), palette):
        ax.plot(s.index, s.reindex(eq.index).values, color=c, lw=1.1, alpha=0.85, label=name)
    ax.set_yscale("log")
    ax.set_title("Growth of $1 — full multi-asset portfolio vs benchmarks (daily, 3y)", color=T["FG"])
    ax.legend(facecolor=T["PANEL"], edgecolor=T["GRID"], labelcolor=T["FG"], fontsize=8, loc="upper left")
    return _png(fig)


def chart_drawdown(eq):
    dd = (eq / eq.cummax() - 1.0) * 100
    fig, ax = plt.subplots(figsize=(11, 2.4))
    ax.fill_between(dd.index, dd.values, 0, color=T["ACC3"], alpha=0.5)
    ax.plot(dd.index, dd.values, color=T["ACC3"], lw=0.8)
    ax.set_title("Drawdown (%)", color=T["FG"])
    return _png(fig)


def chart_class_alloc(tgt, classes):
    macro = {}
    for s in tgt.columns:
        m = macro_class(classes.get(s, "other")) if s in classes else "convex"
        macro[m] = macro.get(m, 0.0) + tgt[s].mean()
    items = sorted(macro.items(), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    ax.barh([k for k, _ in items], [v * 100 for _, v in items], color=T["ACC"])
    ax.set_title("Avg allocation by macro class (%)", color=T["FG"])
    return _png(fig)


def chart_asset_alloc(tgt):
    avg = (tgt.mean().sort_values(ascending=True) * 100)
    avg = avg[avg > 0.01]
    fig, ax = plt.subplots(figsize=(5.4, max(3.2, len(avg) * 0.16)))
    ax.barh(avg.index, avg.values, color=T["ACC4"])
    ax.set_title("Avg realised weight by instrument (%)", color=T["FG"])
    ax.tick_params(labelsize=6)
    return _png(fig)


def chart_rule_sharpe(rules, rule_attr):
    names = [lbl for _, lbl in rules]
    sh = [rule_attr[k]["Sharpe"] for k, _ in rules]
    cols = [T["ACC"] if x >= 0 else T["ACC3"] for x in sh]
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    ax.bar(names, sh, color=cols)
    ax.axhline(0, color=T["MUT"], lw=0.6)
    ax.set_title("Standalone Sharpe per forecast rule (daily 3y)", color=T["FG"])
    ax.tick_params(axis="x", rotation=40, labelsize=7)
    return _png(fig)


# ─────────────────────────────────────────────────────────────────────────────
#  HTML
# ─────────────────────────────────────────────────────────────────────────────
RULE_META = {
    "ewmac": ("Trend", "EWMA(fast)−EWMA(slow), vol-normalised; 4 speeds 8/32…64/256"),
    "breakout": ("Breakout", "position in Donchian channel, smoothed; 40/80/160/320"),
    "mr": ("Reversion", "−z-score of price vs EWMA (contrarian)"),
    "connors": ("Reversion", "cumulative RSI(3) oversold, gated by SMA200"),
    "xs": ("XS-momentum", "cross-sectional demeaned return, class-relative"),
    "residual": ("XS-momentum", "beta-stripped residual momentum, class-relative"),
    "maxlot": ("Lottery", "long low-MAX (avoid lottery-like names), class-relative"),
    "acceleration": ("Trend", "2nd derivative of the EWMAC forecast (Carver)"),
    "safer_mr": ("Reversion", "trend-gated, vol-attenuated fast mean-reversion (Carver)"),
}


def render(d) -> str:
    cfg, iw = d["cfg"], d["iw"]
    m = _metrics(d["net"])
    wf = [(_metrics(chunk)) for chunk in np.array_split(d["net"], 3)]
    mc = R.block_bootstrap(d["net"], block=5, n_paths=2000, horizon=int(BPY / 12))

    def pct(x): return f"{x*100:+.2f}%"
    def num(x): return f"{x:+.2f}"

    # metrics table
    met_rows = "".join(f"<tr><td>{k}</td><td class=num>{(pct(v) if 'return' in k.lower() or 'vol' in k.lower() or 'drawdown' in k.lower() or 'CAGR' in k else num(v))}</td></tr>" for k, v in m.items())
    wf_rows = "".join(f"<tr><td>Third {i+1}</td><td class=num>{pct(w['Total return'])}</td><td class=num>{num(w['Sharpe'])}</td><td class=num>{pct(w['Max drawdown'])}</td></tr>" for i, w in enumerate(wf))
    mc_rows = "".join(f"<tr><td>p{q}</td><td class=num>{pct(np.percentile(mc,q))}</td></tr>" for q in (5,25,50,75,95))

    # universe table (by macro class)
    uni = sorted(d["core"], key=lambda x: (macro_class(x.asset_class), -iw.get(x.symbol,0)))
    uni_rows = "".join(
        f"<tr><td>{x.symbol}</td><td>{x.asset_class}</td><td>{x.group}</td>"
        f"<td>{'crypto' if x.is_crypto else 'stock'}</td><td class=num>{iw.get(x.symbol,0)*100:.2f}%</td>"
        f"<td class=num>{x.cost_bps:.0f}</td></tr>" for x in uni)
    conv_rows = "".join(
        f"<tr><td>{x.symbol}</td><td>{x.asset_class}</td><td>convex sleeve</td>"
        f"<td>stock</td><td class=num>—</td><td class=num>{x.cost_bps:.0f}</td></tr>" for x in d["conv"])

    # strategy table
    wsum = sum(getattr(cfg, k).weight for k in ("ewmac","breakout","mean_reversion","connors","xs_momentum","residual_mom","max_lottery"))
    wmap = {"ewmac":cfg.ewmac.weight,"breakout":cfg.breakout.weight,"mr":cfg.mean_reversion.weight,
            "connors":cfg.connors.weight,"xs":cfg.xs_momentum.weight,"residual":cfg.residual_mom.weight,
            "maxlot":cfg.max_lottery.weight}
    strat_rows = "".join(
        f"<tr><td>{lbl}</td><td>{RULE_META[k][0]}</td><td class=num>{wmap[k]/wsum*100:.0f}%</td>"
        f"<td class=num>{d['rule_attr'][k]['Sharpe']:+.2f}</td><td class=num>{d['rule_attr'][k]['Total return']*100:+.1f}%</td>"
        f"<td class=formula>{RULE_META[k][1]}</td></tr>" for k, lbl in d["rules"])

    r = cfg.risk
    params = [
        ("Cadence (sleeptime)", cfg.sleeptime + " (hourly)"),
        ("Annual vol target (τ)", f"{r.vol_target_annual:.0%}"),
        ("IDM (estimated, daily 3y)", f"{d['idm']:.2f}  (cap {r.idm_cap})"),
        ("FDM", f"{r.fdm}"),
        ("Max weight / instrument", f"{r.max_weight_per_asset:.0%}"),
        ("Max concentration / class", f"{r.max_class_conc:.0%}"),
        ("Cash buffer / gross cap", f"{r.cash_buffer:.0%} / {r.gross_cap:.0%} (long-flat, no leverage)"),
        ("Convex sleeve", f"{cfg.convex.fraction:.0%} in top-{cfg.convex.top_n} momentum (leveraged ETFs)"),
        ("Vol-managed overlay (G1)", f"target {cfg.vol_managed.target_vol_annual:.0%}, on {', '.join(cfg.vol_managed.applies_to)}"),
        ("Forecast frame", f"±{cfg.forecast_cap:.0f}, soft-cap={cfg.soft_cap}, target avg|f|={cfg.forecast_target:.0f}"),
        ("Cost model", "per-instrument bps (see universe) + volume-aware fill cap"),
    ]
    param_rows = "".join(f"<tr><td>{k}</td><td class=num>{v}</td></tr>" for k, v in params)

    imgs = dict(
        eq=chart_equity(d["eq"], d["benches"]),
        dd=chart_drawdown(d["eq"]),
        cls=chart_class_alloc(d["tgt"], d["classes"]),
        ast=chart_asset_alloc(d["tgt"]),
        rule=chart_rule_sharpe(d["rules"], d["rule_attr"]),
    )

    return f"""<!doctype html><html><head><meta charset=utf-8>
<title>SoAI 2026 — Portfolio Report</title><style>
body{{background:{T['BG']};color:{T['FG']};font-family:ui-monospace,Menlo,Consolas,monospace;margin:0;padding:28px;max-width:1120px;margin:auto}}
h1{{font-size:20px;margin:0 0 2px}} h2{{font-size:14px;color:{T['ACC']};margin:26px 0 8px;border-bottom:1px solid {T['GRID']};padding-bottom:4px}}
.sub{{color:{T['MUT']};font-size:12px;margin-bottom:6px}}
.grid{{display:flex;gap:18px;flex-wrap:wrap}} .grid>div{{flex:1;min-width:300px}}
img{{max-width:100%;border:1px solid {T['GRID']};border-radius:6px;background:{T['BG']}}}
table{{border-collapse:collapse;width:100%;font-size:11.5px;margin-top:6px}}
th,td{{text-align:left;padding:4px 8px;border-bottom:1px solid {T['GRID']}}}
th{{color:{T['ACC2']};font-weight:600}} td.num{{text-align:right}} td.formula{{color:{T['MUT']};font-size:10.5px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap;margin:10px 0}}
.card{{background:{T['PANEL']};border:1px solid {T['GRID']};border-radius:8px;padding:10px 14px;min-width:130px}}
.card .v{{font-size:18px;color:{T['ACC']}}} .card .k{{font-size:10px;color:{T['MUT']}}}
.warn{{color:{T['ACC2']};font-size:11px;background:{T['PANEL']};border:1px solid {T['GRID']};border-radius:8px;padding:10px 14px}}
</style></head><body>
<h1>SoAI 2026 — Multi-Asset Systematic Portfolio</h1>
<div class=sub>Carver-style engine · {len(d['core'])} core instruments + {len(d['conv'])} convex · hourly (60M) live · validated on 3y daily</div>

<div class=cards>
<div class=card><div class=v>{pct(m['Total return'])}</div><div class=k>total return (3y)</div></div>
<div class=card><div class=v>{m['CAGR']*100:+.1f}%</div><div class=k>CAGR</div></div>
<div class=card><div class=v>{m['Sharpe']:+.2f}</div><div class=k>Sharpe</div></div>
<div class=card><div class=v>{pct(m['Max drawdown'])}</div><div class=k>max drawdown</div></div>
<div class=card><div class=v>{(mc>0).mean()*100:.0f}%</div><div class=k>P(positive month)</div></div>
<div class=card><div class=v>{d['idm']:.2f}</div><div class=k>IDM (diversification)</div></div>
</div>

<div class=warn>⚠ This is the vectorised engine twin on <b>daily</b> data across the full multi-asset universe — the structural
validation of the whole book. The live competition runs the SAME engine at 60M; free intraday equity data is scarce
locally, so the exact 60M multi-asset P&L is supplied by the organizers' feed. Local numbers are an approximation, not the official result.</div>

<h2>Equity curve vs benchmarks</h2>
<img src="data:image/png;base64,{imgs['eq']}">
<img src="data:image/png;base64,{imgs['dd']}">

<h2>Performance metrics</h2>
<div class=grid>
<div><table><tr><th>Metric</th><th>Value</th></tr>{met_rows}</table></div>
<div><table><tr><th>Walk-forward</th><th>Return</th><th>Sharpe</th><th>MaxDD</th></tr>{wf_rows}</table>
<table style=margin-top:10px><tr><th>Monte-Carlo 1-month</th><th>Return</th></tr>{mc_rows}</table></div>
</div>

<h2>Allocation</h2>
<div class=grid>
<div><img src="data:image/png;base64,{imgs['cls']}"></div>
<div><img src="data:image/png;base64,{imgs['ast']}"></div>
</div>

<h2>Strategies (forecast rules) — weights &amp; standalone performance</h2>
<div class=sub>Forecast weight = share in the combine (renormalised). Standalone = that rule alone driving the whole book.</div>
<table><tr><th>Strategy</th><th>Family</th><th>Forecast weight</th><th>Standalone Sharpe</th><th>Standalone ret (3y)</th><th>Signal</th></tr>{strat_rows}</table>
<img style=margin-top:10px src="data:image/png;base64,{imgs['rule']}">

<h2>Portfolio construction parameters (Carver)</h2>
<table><tr><th>Parameter</th><th>Value</th></tr>{param_rows}</table>

<h2>Instrument universe — asset class, cluster &amp; handcrafted weight</h2>
<div class=sub>Handcrafted: equal risk per macro class (crypto/equity/commodity/bond), then equal within class. Weights sum to 100%.</div>
<table><tr><th>Symbol</th><th>Asset class</th><th>Cluster</th><th>Type</th><th>Handcraft weight</th><th>Cost (bps)</th></tr>{uni_rows}{conv_rows}</table>

<div class=sub style=margin-top:26px>Generated by research/report.py · engine = strategies/engine · full strategy sourcing in research/strategy_catalog.md</div>
</body></html>"""


if __name__ == "__main__":
    d = build()
    html = render(d)
    OUT.write_text(html)
    print(f"[report] wrote {OUT} ({len(html)//1024} KB)")
