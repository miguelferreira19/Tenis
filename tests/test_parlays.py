import json
import sys
from datetime import datetime, timedelta, timezone
from math import prod
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

import autopilot
from tennis_quant.strategy import ParlayPlan

NOW = datetime(2026, 10, 6, 8, tzinfo=timezone.utc)


def match(i, odds_a, odds_b, hours=5):
    return {"id": f"betclic:{i}", "tour": "ATP", "competition": "Pequim ATP", "live": False,
            "start_at": (NOW + timedelta(hours=hours)).isoformat(), "player_a": f"Aa{i} Alpha", "player_b": f"Bb{i} Beta",
            "odds_a": odds_a, "odds_b": odds_b, "url": f"https://betclic.pt/m{i}", "observed_at": NOW.isoformat()}


MARKET = {"observed_at": NOW.isoformat(), "matches": [match(1, 1.12, 6.4), match(2, 1.15, 5.2), match(3, 1.18, 4.5),
                                                      match(4, 1.20, 4.2), match(5, 1.9, 1.95)]}


def test_place_builds_short_parlays_of_safe_legs_and_freezes_them():
    plan, ledger = ParlayPlan(), []
    _, fresh = autopilot.place(ledger, MARKET, plan, NOW)
    assert fresh and ledger == fresh
    ids = [leg["match_id"] for b in fresh for leg in b["legs"]]
    assert len(ids) == len(set(ids)) and "betclic:5" not in ids          # each match once; the coin-flip match is out
    for b in fresh:
        assert plan.odds_lo <= b["odds"] <= plan.odds_hi and b["status"] == "pendente"
        assert all(leg["odds"] <= plan.odds_max and leg["p"] >= plan.p_min for leg in b["legs"])
        assert b["stake"] == 5.0 and b["stake_pct"] == 0.05             # a fraction of the bank, never all-in
    assert sum(b["stake"] for b in fresh) <= plan.day_cap * 100
    assert autopilot.place(ledger, MARKET, plan, NOW)[1] == []            # frozen: no second parlay from the same legs
    assert autopilot.place([], MARKET, plan, NOW, allow_new=False)[1] == []


def parlay(legs, stake=5.0):
    rows = [{"match_id": f"m{i}", "player_a": a, "player_b": b, "side": "a", "odds": o, "p": 0.8,
             "start_at": s.isoformat(), "status": "pendente"} for i, (a, b, o, s) in enumerate(legs)]
    return {"id": "p", "start_at": rows[0]["start_at"], "legs": rows, "stake": stake, "odds": round(prod(r["odds"] for r in rows), 2),
            "status": "pendente"}


def test_parlay_loses_with_one_leg_waits_for_the_rest_and_drops_voids(monkeypatch):
    past = NOW - timedelta(hours=6)
    results = [{"player_a": "Anna Wintersen", "player_b": "Bela Losefeld", "winner": "Anna Wintersen", "score": "6-3 6-4", "start_at": past},
               {"player_a": "Cara Dorn", "player_b": "Dina Wells", "winner": "Dina Wells", "score": "6-1 6-1", "start_at": past}]
    monkeypatch.setattr(autopilot, "espn_results", lambda days: results)
    lost = parlay([("Anna Wintersen", "Bela Losefeld", 1.2, past), ("Cara Dorn", "Dina Wells", 1.3, past)])  # leg 2 picks the loser
    waiting = parlay([("Anna Wintersen", "Bela Losefeld", 1.2, past), ("Xavi Yarn", "Zoe Wick", 1.3, NOW + timedelta(hours=2))])
    voided = parlay([("Anna Wintersen", "Bela Losefeld", 1.2, past), ("Gone Alpha", "Gone Beta", 1.3, NOW - timedelta(days=4))])
    ledger = [lost, waiting, voided]
    assert autopilot.settle(ledger, NOW) == 2
    assert lost["status"] == "perdida" and lost["pnl"] == -5.0
    assert waiting["status"] == "pendente" and waiting["legs"][0]["status"] == "ganha"
    assert voided["status"] == "ganha" and voided["pnl"] == round(5 * (1.2 - 1), 2)   # the void leg drops out of the odds
    assert autopilot.bank_state(ledger)["bank"] == round(100 - 5 + 1.0, 2)


def test_old_single_bets_become_one_leg_parlays():
    old = {"match_id": "m1", "created_at": "x", "start_at": "2026-10-03T09:00:00+00:00", "player_a": "A B", "player_b": "C D",
           "side": "a", "pick": "A B", "odds": 1.14, "p": 0.85, "ev": -0.03, "stake": 1.0, "stake_pct": 0.01,
           "bank_at_pick": 100.0, "url": "u", "status": "ganha", "last_odds": 1.14, "last_seen": "t", "score": "6-4",
           "pnl": 0.14, "settled_at": "2026-10-03T16:40:40+00:00"}
    new = autopilot.as_parlay(old)
    assert new["id"] == "s:m1" and len(new["legs"]) == 1 and new["legs"][0]["status"] == "ganha"
    assert new["legs"][0]["match_id"] == "m1" and new["odds"] == 1.14 and new["pnl"] == 0.14 and new["stake"] == 1.0
    assert autopilot.as_parlay(new) is new
    assert autopilot.bank_state([new])["bank"] == 100.14 and autopilot.summary([new])["won"] == 1


def test_published_backtest_matches_the_code_and_says_each_leg_costs_more():
    report = json.loads((ROOT / "artifacts" / "parlay_strategy.json").read_text(encoding="utf-8"))
    assert ParlayPlan(**report["plan"]) == ParlayPlan()                  # the plan on the site is the plan that was tested
    ev = [row["all"]["ev_model"] for row in report["by_legs"]]
    assert ev == sorted(ev, reverse=True) and report["policy"]["all"]["parlays"] > 500
    assert 1.09 < report["betclic_overround"] < 1.11
    plan = ParlayPlan()
    for day, items in report["days"].items():
        assert len(items) <= plan.max_picks_day and all(plan.odds_lo <= o <= plan.odds_hi and 0 < p < 1 and w in (0, 1) for o, p, w in items)
    assert all(a <= b for a, b in report["calendar"])


def test_real_record_is_internally_consistent_and_public_safe():
    record = json.loads((ROOT / "artifacts" / "real_bets.json").read_text(encoding="utf-8"))
    bets = record["bets"]
    assert len(bets) == 12 and sum(b["result"] == "ganha" for b in bets) == 10
    for b in bets:
        assert 0 < b["stake_pct"] < 1
        if b["legs"]:
            assert abs(round(prod(leg["odds"] for leg in b["legs"]), 2) - b["odds"]) < 1e-9
            assert (b["result"] == "ganha") == all(leg["outcome"] == "ganha" for leg in b["legs"])
    text = json.dumps(record)
    assert "€" not in text and "Ref " not in text                         # no amounts or account references in a public repo
