"""Backtest do plano automático com odds de fecho convertidas para a margem da Betclic.

1. Ajusta slope (viés favorito-azarão) e peso do modelo em 2019–2022.
2. Escolhe filtros de seleção em 2019–2022 (grelha pequena, registada).
3. Valida 2023–2026 sem tocar em nada: simulação diária da banca com as regras
   de `strategy.Plan` (stake por unidade, teto diário, travão de drawdown).
Bet365 é a casa de referência; a versão "Betclic" reaplica a margem observada
na Betclic (~7,5%) às probabilidades justas, carregando mais o azarão (power).
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))
from research_market import build, logit, sigmoid
from tennis_quant import market as mk
from tennis_quant.research_io import write_json
from tennis_quant.strategy import Plan, candidates, stakes

BETCLIC_OVERROUND = 1.075
FIT_YEARS, TEST_YEARS = range(2019, 2023), range(2023, 2027)


def remargin(p_fair: np.ndarray, overround: float) -> tuple[np.ndarray, np.ndarray]:
    """Odds whose implied probs p^(1/k) sum to `overround` (power method: longshots carry more margin)."""
    lo, hi = np.full(len(p_fair), 0.5), np.full(len(p_fair), 1.0)
    for _ in range(60):
        k = (lo + hi) / 2
        total = p_fair ** k + (1 - p_fair) ** k
        lo, hi = np.where(total > overround, k, lo), np.where(total > overround, hi, k)
    k = (lo + hi) / 2
    return np.round(1 / p_fair ** k, 2), np.round(1 / (1 - p_fair) ** k, 2)


def fit_probability(d: pd.DataFrame, odds_a, odds_b) -> tuple[float, float]:
    rows = d.year.isin(FIT_YEARS).to_numpy()
    pb = mk.shin(odds_a[rows], odds_b[rows])
    X = np.c_[logit(pb), logit(d.p_cand.to_numpy()[rows]) - logit(pb)]
    y = d.y.to_numpy()[rows]
    m = LogisticRegression(fit_intercept=False, C=1e4).fit(np.r_[X, -X], np.r_[y, 1 - y])
    return round(float(m.coef_[0][0]), 3), round(float(m.coef_[0][1]), 3)


def flat(d: pd.DataFrame, odds_a, odds_b, plan: Plan, years) -> dict:
    rows = np.where(d.year.isin(years).to_numpy())[0]
    pb = mk.shin(odds_a[rows], odds_b[rows])
    p = sigmoid(plan.slope * logit(pb) + plan.w_model * (logit(d.p_cand.to_numpy()[rows]) - logit(pb)))
    pnl, ps = [], []
    for i, pa in zip(rows, p):
        for c in candidates(float(pa), float(odds_a[i]), float(odds_b[i]), plan):
            won = (d.y.iat[i] == 1) == (c["side"] == "a")
            pnl.append(c["odds"] - 1 if won else -1.0)
            ps.append(c["p"])
    pnl = np.array(pnl)
    return {"bets": int(len(pnl)), "hit_rate": round(float((pnl > 0).mean()), 4) if len(pnl) else None,
            "roi": round(float(pnl.mean()), 4) if len(pnl) else None,
            "roi_se": round(float(pnl.std() / np.sqrt(len(pnl))), 4) if len(pnl) > 1 else None,
            "avg_prob": round(float(np.mean(ps)), 4) if ps else None}


def simulate(d: pd.DataFrame, odds_a, odds_b, plan: Plan, start: float = 100.0) -> dict:
    rows = d[d.year.isin(TEST_YEARS)].sort_values("match_date")
    bank = peak = start
    curve, max_dd, n = [], 0.0, 0
    for day, block in rows.groupby("match_date", sort=True):
        picks = []
        for i in block.index:
            pb = float(mk.shin(odds_a[[i]], odds_b[[i]])[0])
            pa = float(sigmoid(plan.slope * logit(pb) + plan.w_model * (logit(d.p_cand.iat[i]) - logit(pb))))
            for c in candidates(pa, float(odds_a[i]), float(odds_b[i]), plan):
                picks.append({**c, "won": (d.y.iat[i] == 1) == (c["side"] == "a")})
        # ponytail: day-level settlement; intra-day stop-loss only applies across days here.
        for s in stakes(picks, bank, peak, plan):
            bank += s["stake"] * (s["odds"] - 1) if s["won"] else -s["stake"]
            n += 1
        peak = max(peak, bank)
        max_dd = max(max_dd, 1 - bank / peak)
        curve.append([day.isoformat(), round(bank, 2)])
    weekly = curve[::7] + ([curve[-1]] if curve else [])
    return {"start": start, "end": round(bank, 2), "bets": n, "max_drawdown": round(max_dd, 4),
            "return": round(bank / start - 1, 4), "curve_weekly": weekly}


def main():
    d = build().reset_index(drop=True)
    b365_a, b365_b = d.B365_a.to_numpy(float), d.B365_b.to_numpy(float)
    fair = mk.shin(b365_a, b365_b)
    bc_a, bc_b = remargin(fair, BETCLIC_OVERROUND)
    books = {"bet365": (b365_a, b365_b), "betclic_proxy": (bc_a, bc_b)}
    slope, w_model = fit_probability(d, bc_a, bc_b)
    # Model weight fitted negative: dropped (w_model=0), kept only as a diagnostic.
    base = replace(Plan(), slope=slope, w_model=0.0)
    grid = []
    for p_min in (0.60, 0.65, 0.70, 0.75, 0.80):
        for odds_min, odds_max in ((1.10, 1.50), (1.20, 1.55), (1.25, 1.70), (1.15, 1.40)):
            plan = replace(base, p_min=p_min, odds_min=odds_min, odds_max=odds_max)
            r = flat(d, bc_a, bc_b, plan, FIT_YEARS)
            grid.append({"p_min": p_min, "odds_min": odds_min, "odds_max": odds_max, **r})
    # Robust choice: maximise ROI minus one standard error (penalises thin bands).
    # The first run maximised raw ROI and picked odds 1.20–1.25, which live
    # Betclic prices almost never offer; this criterion was set after that.
    eligible = [g for g in grid if g["bets"] >= 300]
    best = max(eligible, key=lambda g: g["roi"] - g["roi_se"])
    plan = replace(base, p_min=best["p_min"], odds_min=best["odds_min"], odds_max=best["odds_max"])
    report = {
        "protocol": __doc__.strip(), "betclic_overround": BETCLIC_OVERROUND,
        "plan": plan.as_dict(), "fitted_model_weight": w_model, "selection_rule": "max(roi - roi_se) em 2019–2022, >= 300 apostas", "fit_years": list(FIT_YEARS), "test_years": list(TEST_YEARS),
        "grid_fit": grid,
        "test_flat": {name: flat(d, a, b, plan, TEST_YEARS) for name, (a, b) in books.items()},
        "test_flat_by_year": {int(Y): flat(d, bc_a, bc_b, plan, [Y]) for Y in TEST_YEARS},
        "simulation_betclic": simulate(d, bc_a, bc_b, plan),
        "simulation_bet365": simulate(d, b365_a, b365_b, plan),
        "baseline_all_favourites_betclic": flat(d, bc_a, bc_b, replace(plan, p_min=0.5, odds_min=1.01, odds_max=2.0), TEST_YEARS),
    }
    write_json(ROOT / "artifacts" / "strategy.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in ("grid_fit", "protocol")}, indent=1)[:4000])


if __name__ == "__main__":
    main()
