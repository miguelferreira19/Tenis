from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select

from tennis_quant import live_odds
from tennis_quant import daily
from tennis_quant.daily import _surface
from tennis_quant.db import fixture_odds, fixtures, metadata
from tennis_quant.parlay import calculate_ticket


def test_ticket_system_and_same_match_guard():
    legs = [{"fixture_id": str(i), "decimal_odds": 2.0, "bookmaker": "book", "source": "provider"}
            for i in range(3)]
    result = calculate_ticket(legs, "system", 12, 2)
    assert result["line_count"] == 3
    assert result["max_gross_return"] == 48
    assert result["same_bookmaker"]
    assert calculate_ticket(legs, "round_robin", 12)["line_count"] == 4
    with pytest.raises(ValueError, match="mesmo jogo"):
        calculate_ticket([legs[0], legs[0]], "accumulator")


def test_live_import_preserves_prices_and_does_not_guess_players(monkeypatch):
    database = create_engine("sqlite:///:memory:")
    metadata.create_all(database)
    monkeypatch.setattr(live_odds, "engine", database)
    monkeypatch.setattr(live_odds, "_player_lookup", lambda: {})
    now = datetime.now(timezone.utc)
    future = (now + timedelta(hours=5)).isoformat().replace("+00:00", "Z")
    observed = (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    sports = [{"key": "tennis_atp_french_open", "active": True, "title": "French Open"}]
    events = [{"id": "event-1", "commence_time": future, "home_team": "Player One",
               "away_team": "Player Two", "bookmakers": [{"key": "book", "last_update": observed,
               "markets": [{"key": "h2h", "last_update": observed,
               "outcomes": [{"name": "Player One", "price": 1.8},
                            {"name": "Player Two", "price": 2.1}]}]}]}]
    monkeypatch.setattr(live_odds, "_get", lambda path, _key, **_kw: (sports if path == "/sports" else events, {}))
    result = live_odds.ingest_current_odds("test-key")
    assert result["events"] == 1 and result["quotes"] == 2
    with database.connect() as conn:
        event = conn.execute(select(fixtures)).mappings().one()
        assert event["player_a_id"] is None
        assert event["match_quality"]["exact_player_match"] is False
        assert len(conn.execute(select(fixture_odds)).all()) == 2
    monkeypatch.setattr(daily, "engine", database)
    board = daily.daily_board((now + timedelta(hours=5)).astimezone(daily.LISBON).date(), None)
    assert board["count"] == 1
    assert len(board["items"][0]["offers"]) == 2
    assert board["items"][0]["probability_a"] is None


def test_surface_is_inferred_only_for_known_tournaments():
    assert _surface("tennis_atp_french_open") == "Clay"
    assert _surface("tennis_wta_wimbledon") == "Grass"
    assert _surface("tennis_atp_unknown_cup") == "Unknown"
