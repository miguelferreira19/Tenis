"""Daily quote view and exploratory pre-match probabilities."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib
import numpy as np
from sqlalchemy import select

from .db import DATA_DIR, engine, fixture_odds, fixtures
from .features import fixture_feature
from .live_odds import _normal
from .model import _calibrate, _raw_predict

LISBON = ZoneInfo("Europe/Lisbon")
SURFACES = {"aus_open": "Hard", "australian_open": "Hard", "french_open": "Clay",
            "wimbledon": "Grass", "us_open": "Hard", "roland_garros": "Clay"}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _surface(sport_key: str) -> str:
    return next((surface for token, surface in SURFACES.items() if token in sport_key), "Unknown")


@lru_cache(maxsize=3)
def _artifact(version: str):
    path = Path(DATA_DIR).parent / "artifacts" / f"{version}.joblib"
    return joblib.load(path) if path.is_file() else None


def _forecast(fixture: dict, version: str | None) -> tuple[float | None, dict, dict | None]:
    quality = dict(fixture["match_quality"] or {})
    quality["surface"] = quality.get("surface") or _surface(fixture["sport_key"])
    if fixture["id"].startswith("espn:") and not quality.get("tour_level_verified"):
        quality["reason"] = "nível da prova ainda não confirmado para o modelo ATP/WTA"
        return None, quality, None
    if not version or not fixture["player_a_id"] or not fixture["player_b_id"]:
        quality["reason"] = quality.get("reason") or "modelo ou identificação de jogadores indisponível"
        return None, quality, None
    artifact = _artifact(version)
    if not artifact:
        quality["reason"] = "artefacto do modelo indisponível"
        return None, quality, None
    start = _utc(fixture["start_at"])
    feature = fixture_feature(fixture["player_a_id"], fixture["player_b_id"],
                              start.date(), fixture["tour"], quality["surface"])
    x = np.stack([feature["x"]])
    raw = _raw_predict(artifact["family"], artifact["model"], x,
                       np.array([feature["elo_probability"]]))
    probability = float(_calibrate(artifact["calibrator"], raw)[0])
    quality.update(feature["quality"])
    quality["surface_known"] = quality["surface"] != "Unknown"
    quality["archive_date_precision"] = "tournament_start"
    return probability, quality, feature["details"]


def daily_board(day: date, version: str | None) -> dict:
    start = datetime.combine(day, time.min, tzinfo=LISBON).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=LISBON).astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    with engine.connect() as conn:
        events = [dict(r) for r in conn.execute(select(fixtures).where(
            fixtures.c.start_at >= start, fixtures.c.start_at < end,
            fixtures.c.start_at > now,
        ).order_by(fixtures.c.start_at)).mappings()]
        if not events:
            return {"date": day.isoformat(), "items": [], "count": 0,
                    "status": "no_fixtures", "quote_max_age_hours": 6,
                    "model_status": "research_only"}
        all_prices = [dict(r) for r in conn.execute(select(fixture_odds).where(
            fixture_odds.c.fixture_id.in_([e["id"] for e in events]))).mappings()]
    prices_by_event: dict[str, list[dict]] = defaultdict(list)
    for price in all_prices:
        prices_by_event[price["fixture_id"]].append(price)
    items = []
    for event in events:
        start_at = _utc(event["start_at"])
        probability_a, quality, analysis = _forecast(event, version) if start_at > now else (None, dict(event["match_quality"] or {}), None)
        latest: dict[tuple[str, str], dict] = {}
        for price in prices_by_event[event["id"]]:
            observed = _utc(price["observed_at"])
            if observed > now or observed >= start_at or now - observed > timedelta(hours=6):
                continue
            key = (price["bookmaker"], price["selection"])
            if key not in latest or _utc(latest[key]["observed_at"]) < observed:
                latest[key] = price
        offers = []
        for (bookmaker, selection), price in latest.items():
            if selection not in {event["player_a"], event["player_b"]}:
                continue
            p = probability_a if selection == event["player_a"] else (1 - probability_a if probability_a is not None else None)
            opposing = event["player_b"] if selection == event["player_a"] else event["player_a"]
            other = latest.get((bookmaker, opposing))
            odd = price["decimal_odds"]
            offers.append({
                "id": price["id"], "bookmaker": bookmaker, "selection": selection,
                "decimal_odds": odd, "observed_at": _utc(price["observed_at"]).isoformat(),
                "source_ref": price["source_ref"], "probability": p,
                "fair_odds": round(1 / p, 3) if p else None,
                "model_price_edge": round(p * odd - 1, 4) if p else None,
                "no_vig_market_probability": round((1 / odd) / (1 / odd + 1 / other["decimal_odds"]), 4) if other else None,
            })
        offers.sort(key=lambda q: (q["model_price_edge"] if q["model_price_edge"] is not None else -999), reverse=True)
        display_tour = event["tour"] if not event["id"].startswith("espn:") or quality.get("tour_level_verified") else (
            "Masculino" if event["tour"] == "ATP" else "Feminino")
        items.append({"id": event["id"], "tour": display_tour,
                      "tournament": event["tournament"], "start_at": start_at.isoformat(),
                      "player_a": event["player_a"], "player_b": event["player_b"],
                      "probability_a": probability_a, "quality": quality,
                      "analysis": analysis, "source_url": event["source"],
                      "offers": offers, "model_version": version,
                      "status": "exploratory_only" if probability_a is not None else "prices_only"})
    unique: dict[tuple, dict] = {}
    for item in items:
        key = (item["tour"], datetime.fromisoformat(item["start_at"]).astimezone(LISBON).date().isoformat(),
               tuple(sorted((_normal(item["player_a"]), _normal(item["player_b"])))))
        previous = unique.get(key)
        if previous is None or (len(item["offers"]), bool(item["probability_a"]),
                                bool(item["quality"].get("surface_known"))) > (
                len(previous["offers"]), bool(previous["probability_a"]),
                bool(previous["quality"].get("surface_known"))):
            unique[key] = item
    items = sorted(unique.values(), key=lambda item: item["start_at"])
    return {"date": day.isoformat(), "items": items, "count": len(items),
            "status": "research_only", "quote_max_age_hours": 6,
            "model_status": "research_only"}
