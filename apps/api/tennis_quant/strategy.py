"""Automatic betting plan: probability from the bookmaker's own prices, bankroll rules.

One module serves both the historical backtest and the live picks, so the plan
shown on the site is exactly the plan that was tested.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from itertools import combinations
from math import exp, log, prod

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


@dataclass(frozen=True)
class ParlayPlan(Plan):
    """Short accumulators of strong favourites; Plan's bankroll rules apply per parlay.

    Legs are strong favourites (odds up to 1.25): the cheapest part of the market, because heavy
    favourites win a little more often than their prices say. Each extra leg still costs 1–3 points of
    expected value (artifacts/parlay_strategy.json), so the plan uses the fewest legs that reach the
    target odds band and takes the cheapest combination.
    """
    slope: float = 1.091       # fitted 2019–2022 (artifacts/strategy.json)
    p_min: float = 0.70        # per leg
    odds_min: float = 1.03
    odds_max: float = 1.25     # per leg: only "safe" favourites
    max_picks_day: int = 3     # parlays per day
    unit: float = 0.05         # stake per parlay: fraction of the bankroll, never all-in
    day_cap: float = 0.15
    stop_day: float = 0.10
    legs_min: int = 1
    legs_max: int = 4
    odds_lo: float = 1.40      # total odds band: +40%..+90% profit when it lands
    odds_hi: float = 1.90


POOL = 12  # best legs of the day considered: C(12, 4) = 495 combinations


def parlays(legs: list[dict], plan: ParlayPlan) -> list[dict]:
    """Cheapest (best expected value) parlays of the day's legs, every leg used at most once.

    `legs`: dicts with 'p' (win chance) and 'odds' that already passed the per-leg filters.
    """
    pool = sorted(legs, key=lambda leg: -leg["p"])[:POOL]
    out: list[dict] = []
    while len(out) < plan.max_picks_day:
        best = None
        for k in range(plan.legs_min, plan.legs_max + 1):
            for combo in combinations(pool, k):
                odds = prod(leg["odds"] for leg in combo)
                if not plan.odds_lo <= odds <= plan.odds_hi:
                    continue
                p = prod(leg["p"] for leg in combo)
                if best is None or (p * odds, p) > (best["p"] * best["odds"], best["p"]):
                    best = {"legs": list(combo), "odds": odds, "p": p}
        if best is None:
            break
        out.append({**best, "ev": best["p"] * best["odds"] - 1})
        used = {id(leg) for leg in best["legs"]}
        pool = [leg for leg in pool if id(leg) not in used]
    return out


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
    _demo_parlays()


def _demo_parlays() -> None:
    plan = ParlayPlan()
    legs = [{"p": 0.90, "odds": 1.08}, {"p": 0.86, "odds": 1.13}, {"p": 0.82, "odds": 1.18}, {"p": 0.80, "odds": 1.22}]
    out = parlays(legs, plan)
    assert 1 <= len(out) <= plan.max_picks_day
    assert all(plan.odds_lo <= o["odds"] <= plan.odds_hi and o["legs"] for o in out)
    assert out[0]["ev"] == max(o["ev"] for o in out)                       # best EV first
    used = [id(leg) for o in out for leg in o["legs"]]
    assert len(used) == len(set(used))                                      # every leg once
    assert parlays([{"p": 0.9, "odds": 1.05}], plan) == []                  # below the target band
    single = parlays([{"p": 0.72, "odds": 1.41}], plan)
    assert len(single) == 1 and len(single[0]["legs"]) == 1                 # fewest legs: a single can do it
    s = stakes(out, 100, 100, plan)
    assert s and all(abs(x["stake"] - 5.0) < 1e-9 for x in s) and sum(x["stake"] for x in s) <= 15


if __name__ == "__main__":
    _demo()
    print("ok")
