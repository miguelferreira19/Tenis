import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np

import autopilot
from tennis_quant import betclic, market, strategy


def test_strategy_rules():
    strategy._demo()


def test_shin_is_fair_and_corrects_favourite_longshot_bias():
    p = market.shin(np.array([1.25]), np.array([4.0]))[0]
    naive = market.proportional(np.array([1.25]), np.array([4.0]))[0]
    assert 0.5 < naive < p < 1  # Shin gives the favourite more than 1/odds normalisation


def test_betclic_circuits_skip_doubles_and_unsettleable_tours():
    assert betclic.circuit("Pequim ATP") == "ATP"
    assert betclic.circuit("Pequim WTA") == "WTA"
    assert betclic.circuit("Adana WTA Challenger") == "WTA"
    assert betclic.circuit("Bari Challenger") is None
    assert betclic.circuit("Pequim ATP - Pares") is None


def test_betclic_parse_reads_main_market_only():
    state = {"x": {"response": {"payload": {"matches": [
        {"matchId": "1", "matchDateUtc": "2026-10-03T09:00:00.0000000Z", "isLive": False,
         "competition": {"id": "36052"}, "contestants": [{}, {}],
         "market": {"mainSelections": [{"name": "Daniil Medvedev", "odds": 1.14, "status": 1},
                                       {"name": "Jan-Lennard Struff", "odds": 4.6, "status": 1}]}},
        {"matchId": "2", "matchDateUtc": "2026-10-03T09:00:00.0000000Z", "isLive": False,
         "competition": {"id": "36052"}, "contestants": [{}, {}],
         "market": {"mainSelections": [{"name": "A B / C D", "odds": 1.5, "status": 1},
                                       {"name": "E F / G H", "odds": 2.5, "status": 1}]}},
    ]}}}}
    rows = betclic.parse(state, "Pequim ATP", "36052")
    assert len(rows) == 1 and rows[0]["odds_a"] == 1.14
    assert rows[0]["url"].endswith("/pequim-atp-c36052/daniil-medvedev-jan-lennard-struff-m1")


def test_settle_uses_result_and_voids_stale(monkeypatch):
    now = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
    start = datetime(2026, 10, 3, 9, tzinfo=timezone.utc)
    ledger = [
        {"match_id": "m1", "start_at": start.isoformat(), "player_a": "Daniil Medvedev",
         "player_b": "Jan-Lennard  Struff", "side": "a", "odds": 1.14, "stake": 1.0, "status": "pendente"},
        {"match_id": "m2", "start_at": (now - timedelta(days=4)).isoformat(), "player_a": "X Y",
         "player_b": "Z W", "side": "b", "odds": 1.2, "stake": 1.0, "status": "pendente"},
    ]
    monkeypatch.setattr(autopilot, "espn_results", lambda days: [{
        "player_a": "Jan-Lennard Struff", "player_b": "Daniil Medvedev", "winner": "Daniil Medvedev",
        "score": "6-3 6-4", "start_at": start + timedelta(minutes=20)}])
    assert autopilot.settle(ledger, now) == 2
    assert ledger[0]["status"] == "ganha" and abs(ledger[0]["pnl"] - 0.14) < 1e-9
    assert ledger[1]["status"] == "anulada" and ledger[1]["pnl"] == 0
    assert autopilot.bank_state(ledger)["bank"] == 100.14
