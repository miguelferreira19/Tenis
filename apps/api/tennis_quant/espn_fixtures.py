"""Low-frequency read of public ESPN tennis scoreboard pages for future fixtures.

This source supplies a schedule, not odds or an official settlement feed. The
embedded page JSON is parsed defensively; a changed layout fails closed.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from threading import Lock

import httpx
from sqlalchemy import select

from .db import engine, fixtures, recent_results, source_refreshes, tournaments
from .ingest import _insert_ignore
from .live_odds import _normal, _player_lookup

REFRESH_LOCK = Lock()
REFRESH_INTERVAL = timedelta(hours=1)
FAILED_UNTIL: dict[date, datetime] = {}
SOURCE = "espn-scoreboard"
# Current tour-level events checked against ATP/WTA 2026 schedules. The ESPN
# scoreboard includes lower-tier singles under the same gender groupings.
MAIN_EVENTS = {
    ("ATP", "aito hangzhou open"): ("Hard", "https://www.atptour.com/en/news/what-is-the-2026-atp-tour-calendar/"),
    ("ATP", "chengdu open"): ("Hard", "https://www.atptour.com/en/tournaments/chengdu/7581/overview"),
    ("ATP", "china open"): ("Hard", "https://www.atptour.com/en/tournaments/beijing/747/overview"),
    ("ATP", "kinoshita group japan open tennis championships"): ("Hard", "https://www.atptour.com/en/news/what-is-the-2026-atp-tour-calendar/"),
    ("WTA", "china open"): ("Hard", "https://www.wtatennis.com/tournaments/china-open"),
}


def _surface_lookup() -> list[tuple[str, str, str]]:
    with engine.connect() as conn:
        rows = conn.execute(select(tournaments.c.tour, tournaments.c.name, tournaments.c.surface)).mappings()
        return [(row["tour"], _normal(row["name"]), row["surface"])
                for row in rows if row["surface"] in {"Hard", "Clay", "Grass", "Carpet"}]


def _infer_surface(tour: str, name: str, known: list[tuple[str, str, str]]) -> tuple[str, str]:
    normalized = _normal(name)
    if (tour, normalized) in MAIN_EVENTS:
        return MAIN_EVENTS[(tour, normalized)][0], "official_2026_schedule"
    exact = {surface for circuit, historic, surface in known if circuit == tour and historic == normalized}
    if len(exact) == 1:
        return exact.pop(), "historical_exact_tournament"
    # A sponsored current title may contain a longer historical tournament name.
    candidates = {(historic, surface) for circuit, historic, surface in known
                  if circuit == tour and len(historic) >= 8 and historic in normalized}
    if candidates:
        longest = max(len(historic) for historic, _ in candidates)
        values = {surface for historic, surface in candidates if len(historic) == longest}
        if len(values) == 1:
            return values.pop(), "historical_name_in_title"
    return "Unknown", "unverified"


def _board(html: str, day: date) -> dict:
    marker = "window['__espnfitt__']="
    if marker not in html:
        raise ValueError("A página de calendário mudou de estrutura")
    doc, _ = json.JSONDecoder().raw_decode(html.split(marker, 1)[1])
    board = doc["page"]["content"]["scoreboard"]
    if board.get("date") != day.strftime("%Y%m%d"):
        raise ValueError("A fonte devolveu uma data diferente da pedida")
    return board


def parse_scoreboard(html: str, day: date, now: datetime,
                     lookup: dict[tuple[str, str], list[str]],
                     surfaces: list[tuple[str, str, str]]) -> list[dict]:
    board = _board(html, day)
    competitions = board.get("competitions", {})
    records: dict[str, dict] = {}
    for tournament in board.get("tournaments", []):
        title = tournament.get("name", "")
        for group in tournament.get("groupings", []):
            if group.get("name") not in {"Men's Singles", "Women's Singles"}:
                continue
            tour = "ATP" if group["name"] == "Men's Singles" else "WTA"
            surface, surface_source = _infer_surface(tour, title, surfaces)
            official_event = MAIN_EVENTS.get((tour, _normal(title)))
            for competition_id in group.get("competitionIds", []):
                competition = competitions.get(str(competition_id), {})
                if competition.get("status", {}).get("state") != "pre":
                    continue
                players = competition.get("competitors", [])
                if len(players) != 2 or not competition.get("tmVld", False):
                    continue
                try:
                    start = datetime.fromisoformat(competition["date"].replace("Z", "+00:00"))
                    if start <= now or start.tzinfo is None:
                        continue
                    a, b = (player["nm"].strip() for player in players)
                    if not a or not b or _normal(a) == _normal(b) or "tbd" in {_normal(a), _normal(b)}:
                        continue
                except (KeyError, TypeError, ValueError):
                    continue
                ids_a = lookup.get((tour, _normal(a)), [])
                ids_b = lookup.get((tour, _normal(b)), [])
                matched = len(ids_a) == len(ids_b) == 1 and ids_a[0] != ids_b[0]
                identity = f"espn:{competition_id}"
                records[identity] = {
                    "id": identity, "sport_key": f"tennis_{tour.lower()}_scoreboard",
                    "tour": tour, "tournament": title[:180], "start_at": start,
                    "player_a": a[:140], "player_b": b[:140],
                    "player_a_id": ids_a[0] if matched else None,
                    "player_b_id": ids_b[0] if matched else None,
                    "match_quality": {
                        "exact_player_match": matched, "surface": surface,
                        "surface_source": surface_source,
                        "tour_level_verified": bool(official_event),
                        "event_source_url": official_event[1] if official_event else None,
                        "round": competition.get("note"),
                        "rank_a": players[0].get("rnk"), "rank_b": players[1].get("rnk"),
                        "reason": None if matched else "jogador não identificado sem ambiguidade",
                    },
                    "source": f"https://www.espn.com/tennis/scoreboard/_/date/{day.strftime('%Y%m%d')}",
                    "last_seen_at": now,
                }
    return list(records.values())


def parse_results(html: str, day: date, now: datetime) -> list[dict]:
    board = _board(html, day)
    competitions = board.get("competitions", {})
    records: dict[str, dict] = {}
    url = f"https://www.espn.com/tennis/scoreboard/_/date/{day.strftime('%Y%m%d')}"
    for tournament in board.get("tournaments", []):
        for group in tournament.get("groupings", []):
            if group.get("name") not in {"Men's Singles", "Women's Singles"}:
                continue
            tour = "ATP" if group["name"] == "Men's Singles" else "WTA"
            for competition_id in group.get("competitionIds", []):
                competition = competitions.get(str(competition_id), {})
                if competition.get("status", {}).get("state") != "post":
                    continue
                players = competition.get("competitors", [])
                if len(players) != 2:
                    continue
                try:
                    start = datetime.fromisoformat(competition["date"].replace("Z", "+00:00"))
                    a, b = (player["nm"].strip() for player in players)
                    if not a or not b or start.tzinfo is None or start > now or "tbd" in {_normal(a), _normal(b)}:
                        continue
                except (KeyError, TypeError, ValueError):
                    continue
                scores_a = [str(s.get("v", "")) for s in players[0].get("lnescrs", [])]
                scores_b = [str(s.get("v", "")) for s in players[1].get("lnescrs", [])]
                score = " ".join(f"{x}-{y}" for x, y in zip(scores_a, scores_b) if x and y)
                winner = a if players[0].get("wnr") else b if players[1].get("wnr") else None
                if not winner or not score:
                    continue
                records[f"espn:{competition_id}"] = {
                    "id": f"espn:{competition_id}", "tour": tour,
                    "tournament": tournament.get("name", "")[:180], "start_at": start,
                    "player_a": a[:140], "player_b": b[:140],
                    "score": score[:140] or None, "winner": winner,
                    "round": (competition.get("note") or "")[:100],
                    "source_url": url, "last_seen_at": now,
                }
    return list(records.values())


def refresh_day(day: date) -> dict:
    url = f"https://www.espn.com/tennis/scoreboard/_/date/{day.strftime('%Y%m%d')}"
    response = httpx.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; TennisQuant/0.3; personal research)"},
                         follow_redirects=True, timeout=20)
    response.raise_for_status()
    now = datetime.now(timezone.utc)
    records = parse_scoreboard(response.text, day, now, _player_lookup(), _surface_lookup())
    results = parse_results(response.text, day, now)
    with engine.begin() as conn:
        if records:
            _insert_ignore(conn, fixtures, records)
            for row in records:
                conn.execute(fixtures.update().where(fixtures.c.id == row["id"]).values(**row))
        if results:
            _insert_ignore(conn, recent_results, results)
            for row in results:
                conn.execute(recent_results.update().where(recent_results.c.id == row["id"]).values(**row))
        _insert_ignore(conn, source_refreshes, [{"source": SOURCE, "day": day,
            "refreshed_at": now, "event_count": len(records)}])
        conn.execute(source_refreshes.update().where(
            source_refreshes.c.source == SOURCE, source_refreshes.c.day == day
        ).values(refreshed_at=now, event_count=len(records)))
    return {"source": SOURCE, "day": day.isoformat(), "events": len(records), "results": len(results),
            "refreshed_at": now.isoformat(), "url": url}


def ensure_fresh(day: date) -> dict:
    now = datetime.now(timezone.utc)
    if FAILED_UNTIL.get(day, datetime.min.replace(tzinfo=timezone.utc)) > now:
        return {"status": "temporarily_unavailable"}
    with REFRESH_LOCK:
        with engine.connect() as conn:
            last = conn.execute(select(source_refreshes.c.refreshed_at).where(
                source_refreshes.c.source == SOURCE, source_refreshes.c.day == day)).scalar_one_or_none()
        if last:
            last = last.replace(tzinfo=timezone.utc) if last.tzinfo is None else last.astimezone(timezone.utc)
        if last and now - last < REFRESH_INTERVAL:
            return {"status": "cached", "refreshed_at": last.isoformat()}
        try:
            return {"status": "refreshed", **refresh_day(day)}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            FAILED_UNTIL[day] = now + timedelta(minutes=5)
            return {"status": "temporarily_unavailable"}
