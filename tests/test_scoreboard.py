"""Contract checks for public scoreboard parsing; no network is used."""
from datetime import date, datetime, timezone

import pytest

from tennis_quant.espn_fixtures import parse_results, parse_scoreboard


def _player(order, name, **extra):
    return {"order": order, "athlete": {"displayName": name}, **extra}


def _competition(state, when, players, **extra):
    return {"id": extra.pop("id"), "status": {"type": {"state": state}}, "timeValid": True,
            "date": when, "competitors": players, **extra}


def test_schedule_and_results_are_separated_and_placeholder_excluded():
    day = date(2026, 9, 27)
    now = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
    future = _competition("pre", "2026-09-27T18:00Z", id="1",
                          round={"displayName": "Round 1"}, venue={"court": "Centre"},
                          # fora de ordem na lista: `order` decide quem é A
                          players=[_player(2, "Player Two", curatedRank={"current": 4}), _player(1, "Player One")])
    past = _competition("post", "2026-09-27T08:00Z", id="2", players=[
        _player(1, "Player Three", winner=True, linescores=[{"value": 6.0}, {"value": 7.0}]),
        _player(2, "Player Four", winner=False, linescores=[{"value": 3.0}, {"value": 5.0}])])
    placeholder = _competition("pre", "2026-09-27T19:00Z", id="3", players=[_player(1, "TBD"), _player(2, "Player Five")])
    board = {"events": [{"name": "Example Open", "groupings": [
        {"grouping": {"displayName": "Men's Singles"}, "competitions": [future, past, placeholder]},
        {"grouping": {"displayName": "Men's Doubles"}, "competitions": [future]}]}]}
    lookup = {("ATP", "player one"): ["a"], ("ATP", "player two"): ["b"]}
    scheduled = parse_scoreboard([board], day, now, lookup, [])
    recent = parse_results([board], day, now)
    assert len(scheduled) == 1 and scheduled[0]["id"] == "espn:1"
    assert scheduled[0]["player_a"] == "Player One" and scheduled[0]["player_a_id"] == "a"
    assert scheduled[0]["match_quality"]["surface"] == "Unknown"
    assert scheduled[0]["match_quality"]["tour_level_verified"] is False
    assert scheduled[0]["match_quality"]["rank_b"] == 4 and scheduled[0]["match_quality"]["rank_a"] is None
    assert scheduled[0]["match_quality"]["round"] == "Round 1 - Centre"
    assert len(recent) == 1 and recent[0]["score"] == "6-3 7-5"
    assert recent[0]["winner"] == "Player Three"


def test_shared_tournament_is_not_duplicated_and_bad_layout_fails_closed():
    now = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
    game = _competition("pre", "2026-09-27T18:00Z", id="9", players=[_player(1, "A One"), _player(2, "B Two")])
    shared = {"events": [{"name": "China Open", "groupings": [
        {"grouping": {"displayName": "Women's Singles"}, "competitions": [game]}]}]}
    assert len(parse_scoreboard([shared, shared], date(2026, 9, 27), now, {}, [])) == 1  # endpoints ATP e WTA repetem
    with pytest.raises(ValueError, match="mudou de estrutura"):
        parse_scoreboard([{"unexpected": []}], date(2026, 9, 27), now, {}, [])
