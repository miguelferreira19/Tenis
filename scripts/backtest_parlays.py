"""Backtest das múltiplas curtas (strategy.ParlayPlan) com odds de fecho na margem da Betclic.

Protocolo (escrito antes de reportar o teste):
1. Probabilidade: o mesmo motor do plano de apostas simples (Shin + declive 1,091, ajustado em 2019–2022).
2. A forma da múltipla vem do comportamento observado (pernas «seguras» de odd até 1,25, odd total 1,40–1,90,
   1–4 pernas), não de uma otimização. Grelhas exploratórias (tecto de odds por perna, banda de odds, nº de
   pernas) deram retorno negativo em todas; nenhuma foi escolhida por rendimento.
   A margem da Betclic é a MEDIDA em preços reais (overround 1,101 em 126 jogos a 2026-09-30 e 1,102 em 87 a
   2026-10-06), não os 7,5% assumidos no backtest das apostas simples, que ficava otimista.
3. Para medir o custo de cada perna comparam-se 1, 2, 3 e 4 pernas com a mesma banda de odds, e o retorno
   de uma aposta simples por escalão de odds.
4. Ajuste 2019–2022 e teste 2023–2026 lado a lado. Nenhum resultado aqui é promessa de lucro.
Também exporta, por dia, as múltiplas que o plano teria feito: o site usa-as para simular a banca.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))
from backtest_strategy import FIT_YEARS, TEST_YEARS, remargin
from research_market import build, logit, sigmoid
from tennis_quant import market as mk
from tennis_quant.research_io import write_json
from tennis_quant.strategy import ParlayPlan, parlays

OUT = ROOT / "artifacts" / "parlay_strategy.json"
BETCLIC_OVERROUND = 1.10  # medido em preços reais da Betclic (ver protocolo); o plano antigo assumia 1,075
PROJECTION_YEARS = (2019, 2021, 2022, 2023, 2024, 2025, 2026)  # 2020: circuito parado pela pandemia
BY_LEGS_LO = 1.30  # common odds band for the 1–4 legs comparison: a single leg at 77%+ cannot reach 1.40
ALL_YEARS = range(2019, 2027)
LEG_EDGES = (1.03, 1.06, 1.09, 1.12, 1.15, 1.18, 1.21, 1.25, 1.30, 1.40, 1.55)
MARGIN_SAMPLES = [{"date": "2026-09-30", "matches": 126, "overround": 1.101},
                  {"date": "2026-10-06", "matches": 87, "overround": 1.102}]


def favourites(d: pd.DataFrame, slope: float) -> pd.DataFrame:
    """One row per match: the favourite's win chance, Betclic-margin odds and outcome."""
    fair = mk.shin(d.B365_a.to_numpy(float), d.B365_b.to_numpy(float))
    odds_a, odds_b = remargin(fair, BETCLIC_OVERROUND)
    p_a = sigmoid(slope * logit(mk.shin(odds_a, odds_b)))
    fav_a, a_won = p_a >= 0.5, d.y.to_numpy() == 1
    return pd.DataFrame({"day": pd.to_datetime(d.match_date).dt.date, "year": d.year.to_numpy(),
                         "p": np.where(fav_a, p_a, 1 - p_a), "odds": np.where(fav_a, odds_a, odds_b),
                         "won": np.where(fav_a, a_won, ~a_won)})


def play(legs: pd.DataFrame, plan: ParlayPlan, years) -> list[dict]:
    """Every parlay the plan would have placed, day by day."""
    sub = legs[legs.year.isin(years) & (legs.p >= plan.p_min) & legs.odds.between(plan.odds_min, plan.odds_max)]
    out = []
    for day, block in sub.groupby("day", sort=True):
        for par in parlays(block[["p", "odds", "won"]].to_dict("records"), plan):
            out.append({"day": day, "odds": round(par["odds"], 2), "p": par["p"], "n_legs": len(par["legs"]),
                        "won": all(leg["won"] for leg in par["legs"])})
    return out


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {"parlays": 0}
    odds, p = np.array([r["odds"] for r in rows]), np.array([r["p"] for r in rows])
    won, legs = np.array([r["won"] for r in rows]), np.array([r["n_legs"] for r in rows])
    pnl = np.where(won, odds - 1, -1.0)
    return {"parlays": len(rows), "hit_rate": round(float(won.mean()), 4), "avg_odds": round(float(odds.mean()), 3),
            "avg_p": round(float(p.mean()), 4), "roi": round(float(pnl.mean()), 4),
            "roi_se": round(float(pnl.std() / np.sqrt(len(rows))), 4),
            "ev_model": round(float((p * odds - 1).mean()), 4),
            "legs_mix": {str(k): round(float((legs == k).mean()), 3) for k in (1, 2, 3, 4)}}


def leg_curve(legs: pd.DataFrame, years) -> list[dict]:
    """Single-bet return by the favourite's odds: what one leg costs, before any parlay."""
    sub, out = legs[legs.year.isin(years)], []
    for lo, hi in zip(LEG_EDGES[:-1], LEG_EDGES[1:]):
        s = sub[(sub.odds >= lo) & (sub.odds < hi)]
        pnl = np.where(s.won, s.odds - 1, -1.0)
        out.append({"odds_lo": lo, "odds_hi": hi, "bets": int(len(s)), "hit_rate": round(float(s.won.mean()), 4),
                    "avg_p": round(float(s.p.mean()), 4), "roi": round(float(pnl.mean()), 4),
                    "roi_se": round(float(pnl.std() / np.sqrt(len(s))), 4)})
    return out


def calendar(legs: pd.DataFrame, years) -> list[list[str]]:
    """Contiguous date ranges of whole years; the last one ends at the latest match in the data."""
    last, out = max(legs.day), []
    for y in years:
        end = min(date(y, 12, 31), last).isoformat()
        if out and out[-1][1] == date(y - 1, 12, 31).isoformat():
            out[-1][1] = end
        else:
            out.append([date(y, 1, 1).isoformat(), end])
    return out


def main() -> None:
    plan = ParlayPlan()
    legs = favourites(build().reset_index(drop=True), plan.slope)
    rows = play(legs, plan, ALL_YEARS)
    by_legs = []
    for k in (1, 2, 3, 4):
        one = replace(plan, legs_min=k, legs_max=k, max_picks_day=1, odds_lo=BY_LEGS_LO, odds_max=2.0)
        by_legs.append({"legs": k, **{name: summarize(play(legs, one, years))
                                      for name, years in (("fit", FIT_YEARS), ("test", TEST_YEARS), ("all", ALL_YEARS))}})
    days: dict[str, list] = {}  # the parlays per day, best expected value first: [odds, win chance, won]
    for r in rows:
        if r["day"].year in PROJECTION_YEARS:
            days.setdefault(r["day"].isoformat(), []).append([r["odds"], round(r["p"], 4), int(r["won"])])
    report = {
        "protocol": __doc__.strip(), "betclic_overround": BETCLIC_OVERROUND, "margin_measured": MARGIN_SAMPLES,
        "plan": plan.as_dict(), "fit_years": list(FIT_YEARS), "test_years": list(TEST_YEARS),
        "policy": {"fit": summarize([r for r in rows if r["day"].year in FIT_YEARS]),
                   "test": summarize([r for r in rows if r["day"].year in TEST_YEARS]), "all": summarize(rows),
                   "by_year": {int(y): summarize([r for r in rows if r["day"].year == y]) for y in ALL_YEARS}},
        "by_legs": by_legs, "by_legs_band": [BY_LEGS_LO, plan.odds_hi],
        "leg_curve": leg_curve(legs, ALL_YEARS), "calendar": calendar(legs, PROJECTION_YEARS), "days": days,
    }
    write_json(OUT, report)
    for name in ("fit", "test", "all"):
        s = report["policy"][name]
        print(f"plano {name:4s}: {s['parlays']} múltiplas, {s['hit_rate']:.1%} ganhas, odd {s['avg_odds']:.2f}, "
              f"retorno {s['roi']:+.1%} ± {s['roi_se']:.1%}, modelo {s['ev_model']:+.1%}, pernas {s['legs_mix']}")
    for row in by_legs:
        s = row["all"]
        print(f"{row['legs']} perna(s): n={s['parlays']} odd {s['avg_odds']:.2f} ganhas {s['hit_rate']:.1%} "
              f"retorno {s['roi']:+.1%} ± {s['roi_se']:.1%} (modelo {s['ev_model']:+.1%})")


if __name__ == "__main__":
    main()
