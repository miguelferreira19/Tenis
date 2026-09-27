"""Contract checks for public scoreboard parsing; no network is used."""
import json
from datetime import date, datetime, timezone

from tennis_quant.espn_fixtures import parse_results, parse_scoreboard


def test_schedule_and_results_are_separated_and_placeholder_excluded():
    day = date(2026, 9, 27)
    now = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
    competitions = {
        "future": {"status": {"state": "pre"}, "tmVld": True,
                   "date": "2026-09-27T18:00:00Z", "competitors": [{"nm": "Player One"}, {"nm": "Player Two"}]},
        "past": {"status": {"state": "post"}, "date": "2026-09-27T08:00:00Z",
                 "competitors": [{"nm": "Player Three", "wnr": True, "lnescrs": [{"v": 6}, {"v": 7}]},
                                 {"nm": "Player Four", "wnr": False, "lnescrs": [{"v": 3}, {"v": 5}]}]},
        "placeholder": {"status": {"state": "pre"}, "tmVld": True,
                        "date": "2026-09-27T19:00:00Z", "competitors": [{"nm": "TBD"}, {"nm": "Player Five"}]},
    }
    board = {"date": "20260927", "competitions": competitions,
             "tournaments": [{"name": "Example Open", "groupings": [
                 {"name": "Men's Singles", "competitionIds": list(competitions)},
                 {"name": "Men's Doubles", "competitionIds": ["future"]}]}]}
    html = "<script>window['__espnfitt__']=" + json.dumps({"page": {"content": {"scoreboard": board}}}) + ";</script>"
    lookup = {("ATP", "player one"): ["a"], ("ATP", "player two"): ["b"]}
    future = parse_scoreboard(html, day, now, lookup, [])
    recent = parse_results(html, day, now)
    assert len(future) == 1 and future[0]["player_a_id"] == "a"
    assert future[0]["match_quality"]["surface"] == "Unknown"
    assert future[0]["match_quality"]["tour_level_verified"] is False
    assert len(recent) == 1 and recent[0]["score"] == "6-3 7-5"
    assert recent[0]["winner"] == "Player Three"
