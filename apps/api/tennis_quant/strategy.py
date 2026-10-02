"""Automatic betting plan: probability from the bookmaker's own prices, bankroll rules.

One module serves both the historical backtest and the live picks, so the plan
shown on the site is exactly the plan that was tested.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import exp, log

from .market import shin


@dataclass(frozen=True)
class Plan:
    # Probability engine: p = sigmoid(slope * logit(p_book) + w_model * (logit(p_model) - logit(p_book)))
    slope: float = 1.10        # >1: market underrates favourites (favourite-longshot bias)
    w_model: float = 0.0       # 2019–2022 fit gave −0.055: the model only adds noise to prices
    # Selection
    p_min: float = 0.70
    odds_min: float = 1.20
    odds_max: float = 1.55
    max_picks_day: int = 4
    # Bankroll
    unit: float = 0.01         # stake per pick, fraction of current bankroll (EV<0: keep it small)
    day_cap: float = 0.05      # max fraction of bankroll at risk per day
    dd_soft: float = 0.10      # drawdown where stakes start shrinking
    dd_hard: float = 0.30      # drawdown where stakes reach the floor
    dd_floor: float = 0.4      # stake multiplier at dd_hard
    stop_day: float = 0.04     # stop for the day after losing this fraction

    def as_dict(self) -> dict:
        return asdict(self)


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return log(p / (1 - p))


def probability(odds_a: float, odds_b: float, plan: Plan, p_model: float | None = None) -> float:
    """Win probability of A from the two prices (Shin de-vig), bias-corrected, model-nudged."""
    import numpy as np
    p_book = float(shin(np.array([odds_a], float), np.array([odds_b], float))[0])
    z = plan.slope * _logit(p_book)
    if p_model is not None:
        z += plan.w_model * (_logit(p_model) - _logit(p_book))
    return 1 / (1 + exp(-z))


def candidates(p_a: float, odds_a: float, odds_b: float, plan: Plan) -> list[dict]:
    """Return the side that passes the plan filters (at most one per match)."""
    out = []
    for side, p, odds in (("a", p_a, odds_a), ("b", 1 - p_a, odds_b)):
        if p >= plan.p_min and plan.odds_min <= odds <= plan.odds_max:
            out.append({"side": side, "p": p, "odds": odds, "ev": p * odds - 1})
    return out


def dd_multiplier(drawdown: float, plan: Plan) -> float:
    if drawdown <= plan.dd_soft:
        return 1.0
    if drawdown >= plan.dd_hard:
        return plan.dd_floor
    frac = (drawdown - plan.dd_soft) / (plan.dd_hard - plan.dd_soft)
    return 1 - frac * (1 - plan.dd_floor)


def stakes(picks: list[dict], bankroll: float, peak: float, plan: Plan, lost_today: float = 0.0,
           staked_today: float = 0.0, picks_today: int = 0) -> list[dict]:
    """Size today's picks: best EV first, unit stake scaled by drawdown, capped per day."""
    if bankroll <= 0 or lost_today >= plan.stop_day * bankroll:
        return []
    mult = dd_multiplier(1 - bankroll / peak if peak > 0 else 0.0, plan)
    budget = plan.day_cap * bankroll - max(lost_today, staked_today)
    out = []
    for pick in sorted(picks, key=lambda p: (-p["ev"], -p["p"]))[:max(plan.max_picks_day - picks_today, 0)]:
        stake = round(min(plan.unit * mult * bankroll, budget), 2)
        if stake < 0.1:
            break
        budget -= stake
        out.append({**pick, "stake": stake})
    return out


def _demo() -> None:
    plan = Plan()
    p = probability(1.30, 3.60, plan)
    assert 0.72 < p < 0.80, p
    c = candidates(p, 1.30, 3.60, plan)
    assert len(c) == 1 and c[0]["side"] == "a"
    s = stakes(c * 6, 1000, 1000, plan)
    assert len(s) == 4 and sum(x["stake"] for x in s) <= 50
    assert dd_multiplier(0.2, plan) < 1 and stakes(c, 1000, 1000, plan, lost_today=40) == []


if __name__ == "__main__":
    _demo()
    print("ok")
