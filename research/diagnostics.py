"""
═══════════════════════════════════════════════════════════════════════════════
  DIAGNOSTICS — assets, strategies, weights, and correlation structure
═══════════════════════════════════════════════════════════════════════════════

Answers: what assets/strategies do we run, at what weights, and how correlated
are the strategies to each other (the real test of whether they diversify) and
the assets to each other. Uses the daily vectorised engine twin.

    python research/diagnostics.py
Also writes research/strategy_corr.png (heatmap).
"""

from __future__ import annotations

import copy
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

# rule key -> (config attribute, family, label)
RULES = [
    ("ewmac", "ewmac", "Trend", "EWMAC"),
    ("acceleration", "acceleration", "Trend", "Acceleration"),
    ("kama", "kama", "Trend", "KAMA"),
    ("mtf", "mtf_pullback", "Trend", "MTF-pullback"),
    ("breakout", "breakout", "Breakout", "Donchian"),
    ("mr", "mean_reversion", "Reversion", "z-MR"),
    ("connors", "connors", "Reversion", "ConnorsRSI"),
    ("safer_mr", "safer_fast_mr", "Reversion", "SaferFastMR"),
    ("residual_mr", "residual_mr", "Reversion", "Residual-MR"),
    ("intmkt", "intermarket_div", "Reversion", "IntermktDiv"),
    ("xs", "xs_momentum", "XS-mom", "XS-mom"),
    ("residual", "residual_mom", "XS-mom", "Residual-mom"),
    ("leadlag", "leadlag", "XS-mom", "LeadLag"),
    ("maxlot", "max_lottery", "Lottery", "MAX-lottery"),
]


def main():
    cfg = EngineConfig()
    core = load_universe(roles=("core",))
    conv = load_universe(roles=("convex",))
    iw = handcraft_weights(core, cfg.macro_weights)
    groups, classes = groups_map(core), class_map(core)
    px, is_crypto = R.load_daily(core)

    # ── assets ────────────────────────────────────────────────────────────
    print("═══════════ ASSETS (active core) ═══════════")
    from collections import defaultdict
    bym = defaultdict(list)
    for ins in core:
        bym[macro_class(ins.asset_class)].append(ins.symbol)
    for m, syms in sorted(bym.items(), key=lambda kv: -sum(iw.get(s, 0) for s in kv[1])):
        tot = sum(iw.get(s, 0) for s in syms)
        print(f"  {m:<10} {tot:6.1%}  ({len(syms)})  {', '.join(syms)}")
    print(f"  convex sleeve ({len(conv)}): {', '.join(i.symbol for i in conv)}")

    # ── strategy weights ──────────────────────────────────────────────────
    wsum = sum(getattr(cfg, a).weight for _, a, _, _ in RULES)
    print("\n═══════════ STRATEGIES (forecast weights) ═══════════")
    for k, a, fam, lbl in RULES:
        w = getattr(cfg, a).weight
        print(f"  {lbl:<14} {fam:<10} {w/wsum:6.1%}" + ("   [disabled]" if w == 0 else ""))

    # ── per-strategy standalone daily returns ─────────────────────────────
    print("\n[computing standalone return series per strategy ...]")
    rets = {}
    for k, a, fam, lbl in RULES:
        if getattr(cfg, a).weight == 0:
            continue
        c2 = copy.deepcopy(cfg)
        for _, aa, _, _ in RULES:
            getattr(c2, aa).weight = 0.0
        getattr(c2, a).weight = 1.0
        c2.convex.enabled = False
        w2, _ = R.target_weights_frame(px, c2, iw, groups, classes, is_crypto, True)
        rets[lbl] = R.simulate(px, w2, R.FEE, buffer=cfg.execution.no_trade_buffer,
                               max_turnover=cfg.execution.max_turnover_per_step)
    RET = pd.DataFrame(rets).dropna(how="all")

    # ── strategy-strategy correlation ─────────────────────────────────────
    corr = RET.corr()
    print("\n═══════════ STRATEGY–STRATEGY CORRELATION ═══════════")
    labels = list(corr.columns)
    abbr = [l[:9] for l in labels]
    print("            " + " ".join(f"{a:>9}" for a in abbr))
    for i, l in enumerate(labels):
        print(f"  {l:<11} " + " ".join(f"{corr.iloc[i, j]:>9.2f}" for j in range(len(labels))))
    # diversification summary
    off = corr.where(~np.eye(len(corr), dtype=bool))
    print(f"\n  avg |pairwise corr| = {off.abs().stack().mean():.2f}  "
          f"(lower = more diversified)")
    mean_corr = off.mean().sort_values()
    print("  most diversifying (lowest avg corr):",
          ", ".join(f"{k}={v:+.2f}" for k, v in mean_corr.head(4).items()))
    print("  most redundant   (highest avg corr):",
          ", ".join(f"{k}={v:+.2f}" for k, v in mean_corr.tail(4).items()))

    # ── asset correlation summary (by macro class) ────────────────────────
    aret = px.pct_change(fill_method=None)
    acorr = aret.corr()
    print("\n═══════════ ASSET CORRELATION (avg pairwise) ═══════════")
    macros = sorted(set(macro_class(i.asset_class) for i in core))
    msyms = {m: [i.symbol for i in core if macro_class(i.asset_class) == m and i.symbol in acorr.columns] for m in macros}
    def avg_block(a, b):
        va = [x for x in msyms[a] if x in acorr.columns]; vb = [x for x in msyms[b] if x in acorr.columns]
        if not va or not vb: return float("nan")
        sub = acorr.loc[va, vb].values
        if a == b:
            iu = ~np.eye(len(va), dtype=bool)
            return float(np.nanmean(sub[iu])) if len(va) > 1 else float("nan")
        return float(np.nanmean(sub))
    print("            " + " ".join(f"{m[:8]:>8}" for m in macros))
    for a in macros:
        print(f"  {a:<10} " + " ".join(f"{avg_block(a,b):>8.2f}" for b in macros))
    print(f"\n  IDM (1/sqrt(w'Cw)) estimated = {R.__dict__.get('idm_from_returns', None) and ''}"
          f"{__import__('strategies.engine.instruments', fromlist=['idm_from_returns']).idm_from_returns(aret, iw, cap=cfg.risk.idm_cap):.2f}")

    # ── heatmap ───────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, rotation=90, fontsize=7)
    ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels, fontsize=7)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, f"{corr.iloc[i,j]:.1f}", ha="center", va="center", fontsize=6,
                    color="white" if abs(corr.iloc[i,j]) > 0.5 else "black")
    fig.colorbar(im, fraction=0.046, pad=0.04)
    ax.set_title("Strategy–strategy return correlation (daily)")
    fig.tight_layout()
    out = Path(__file__).resolve().parent / "strategy_corr.png"
    fig.savefig(out, dpi=120); print(f"\n[saved heatmap] {out}")


if __name__ == "__main__":
    main()
