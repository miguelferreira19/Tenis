"""Auditable import of current tennis prices from The Odds API.

No credentials are stored in the database or returned by the API. A quote is an
observation, never a promise that a bookmaker will accept a combined ticket.
"""
from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import select

from .db import engine, fixture_odds, fixtures, players
from .ingest import _insert_ignore

BASE = "https://api.the-odds-api.com/v4"


def _normal(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return " ".join("".join(c if c.isalnum() else " " for c in ascii_name).split())


def _player_lookup() -> dict[tuple[str, str], list[str]]:
    with engine.connect() as conn:
        rows = conn.execute(select(players.c.id, players.c.tour, players.c.name)).mappings()
        lookup: dict[tuple[str, str], list[str]] = {}
        for row in rows:
            lookup.setdefault((row["tour"], _normal(row["name"])), []).append(row["id"])
    return lookup


def _get(path: str, api_key: str, **params):
    url = f"{BASE}{path}?{urlencode({**params, 'apiKey': api_key})}"
    request = Request(url, headers={"User-Agent": "TennisQuant/0.2", "Accept": "application/json"})
    with urlopen(request, timeout=20) as response:
        return json.load(response), {
            name: response.headers.get(name) for name in
            ("x-requests-remaining", "x-requests-used", "x-requests-last")
        }


def ingest_current_odds(api_key: str | None = None, *, region: str = "eu", max_sports: int = 12) -> dict:
    api_key = api_key or os.getenv("ODDS_API_KEY", "")
    if not api_key:
        raise ValueError("ODDS_API_KEY não configurada")
    if region not in {"eu", "uk", "us", "au"}:
        raise ValueError("Região inválida")
    if not 1 <= max_sports <= 30:
        raise ValueError("max_sports fora do intervalo 1–30")
    sports, _ = _get("/sports", api_key)
    tennis = [s for s in sports if s.get("active") and
              s.get("key", "").startswith(("tennis_atp_", "tennis_wta_"))]
    # Explicit cap protects the user's request quota. The UI reports truncation.
    selected = tennis[:max_sports]
    lookup = _player_lookup()
    now = datetime.now(timezone.utc)
    event_rows: dict[str, dict] = {}
    price_rows: list[dict] = []
    quota = None
    for sport in selected:
        events, quota = _get(f"/sports/{sport['key']}/odds", api_key,
                             regions=region, markets="h2h", oddsFormat="decimal")
        tour = "ATP" if sport["key"].startswith("tennis_atp_") else "WTA"
        for event in events:
            try:
                start = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
                if start <= now or not event.get("id"):
                    continue
                a, b = event["home_team"].strip(), event["away_team"].strip()
                if not a or not b or _normal(a) == _normal(b):
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            ids_a = lookup.get((tour, _normal(a)), [])
            ids_b = lookup.get((tour, _normal(b)), [])
            matched = len(ids_a) == len(ids_b) == 1 and ids_a[0] != ids_b[0]
            eid = event["id"]
            event_rows[eid] = {
                "id": eid, "sport_key": sport["key"], "tour": tour,
                "tournament": sport.get("title", sport["key"]), "start_at": start,
                "player_a": a, "player_b": b,
                "player_a_id": ids_a[0] if matched else None,
                "player_b_id": ids_b[0] if matched else None,
                "match_quality": {"exact_player_match": matched,
                                  "surface_known": False,
                                  "reason": None if matched else "jogador não identificado sem ambiguidade"},
                "source": "the-odds-api", "last_seen_at": now,
            }
            for bookmaker in event.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    if market.get("key") != "h2h":
                        continue
                    observed_raw = market.get("last_update") or bookmaker.get("last_update")
                    try:
                        observed = datetime.fromisoformat(observed_raw.replace("Z", "+00:00"))
                    except (AttributeError, ValueError):
                        continue
                    if observed.tzinfo is None or observed > now or observed >= start:
                        continue
                    for outcome in market.get("outcomes", []):
                        if outcome.get("name") not in {a, b}:
                            continue
                        try:
                            odd = float(outcome["price"])
                        except (KeyError, ValueError, TypeError):
                            continue
                        if not 1 < odd <= 1000:
                            continue
                        bookmaker_key = bookmaker.get("key", "")
                        if not bookmaker_key:
                            continue
                        identity = f"{eid}|{bookmaker_key}|{outcome['name']}|{observed.isoformat()}|{odd}"
                        price_rows.append({
                            "id": hashlib.sha256(identity.encode()).hexdigest()[:64],
                            "fixture_id": eid, "market": "match_winner",
                            "selection": outcome["name"], "bookmaker": bookmaker_key,
                            "decimal_odds": odd, "observed_at": observed,
                            "source_ref": f"{BASE}/sports/{sport['key']}/odds?regions={region}&markets=h2h",
                        })
    with engine.begin() as conn:
        if event_rows:
            _insert_ignore(conn, fixtures, list(event_rows.values()))
            # Future updates must retain immutable odds snapshots but refresh fixture metadata.
            for row in event_rows.values():
                conn.execute(fixtures.update().where(fixtures.c.id == row["id"]).values(**row))
        if price_rows:
            _insert_ignore(conn, fixture_odds, price_rows)
    return {"events": len(event_rows), "quotes": len(price_rows),
            "sports_scanned": len(selected), "sports_available": len(tennis),
            "truncated": len(tennis) > len(selected), "region": region,
            "quota": quota, "retrieved_at": now.isoformat()}
