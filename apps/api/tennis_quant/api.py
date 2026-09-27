from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, or_, select

from .db import DATA_DIR, counts, engine, init_db, matches, odds_snapshots, players, predictions, raw_ingestions, fixtures, fixture_odds, recent_results
from .daily import daily_board
from .espn_fixtures import ensure_fresh
from .live_odds import ingest_current_odds
from .parlay import calculate_ticket

app = FastAPI(title="Tennis Quant API", version="0.2.0", description="Investigação quantitativa em ténis")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


@app.on_event("startup")
def startup():
    init_db()


def evaluation() -> dict:
    path = DATA_DIR.parent / "artifacts" / "evaluation.json"
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    comparison_path = DATA_DIR.parent / "artifacts" / "model_comparison.json"
    if comparison_path.exists():
        report["comparison"] = json.loads(comparison_path.read_text(encoding="utf-8"))
    research_path = DATA_DIR.parent / "artifacts" / "layoff_research.json"
    if research_path.exists():
        report["layoff_research"] = json.loads(research_path.read_text(encoding="utf-8"))
    return report


def selected_version() -> str | None:
    report = evaluation()
    family = report.get("selected_by_validation")
    return report.get(family, {}).get("version") if family else None


def _match_query():
    a, b = players.alias("a"), players.alias("b")
    version = selected_version()
    stmt = select(
        matches.c.id, matches.c.tour, matches.c.tournament,
        matches.c.event_date, matches.c.date_precision, matches.c.round,
        matches.c.surface, matches.c.best_of, matches.c.player_a_id,
        matches.c.player_b_id, matches.c.winner_id, matches.c.score,
        matches.c.rank_a, matches.c.rank_b, matches.c.source_url,
        a.c.name.label("player_a"), b.c.name.label("player_b"),
        predictions.c.probability_a, predictions.c.fair_odds_a,
        predictions.c.fair_odds_b, predictions.c.split,
        predictions.c.as_of, predictions.c.model_version,
        predictions.c.features, predictions.c.quality,
    ).select_from(matches.join(a, a.c.id == matches.c.player_a_id)
                  .join(b, b.c.id == matches.c.player_b_id)
                  .outerjoin(predictions, and_(predictions.c.match_id == matches.c.id,
                                                predictions.c.model_version == version)))
    return stmt


def _serialize(record: dict) -> dict:
    for key in ("event_date", "as_of"):
        if record.get(key) is not None:
            record[key] = record[key].isoformat()
    record["winner"] = record.get("player_a") if record.get("winner_id") == record.get("player_a_id") else record.get("player_b")
    record["market_status"] = "sem_odds_temporizadas"
    record["model_status"] = "research_only"
    return record


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/api/daily")
def daily(day: date | None = None):
    local_today = datetime.now(ZoneInfo("Europe/Lisbon")).date()
    requested = day or local_today
    if requested < local_today or requested > local_today + timedelta(days=30):
        raise HTTPException(422, "Escolhe uma data entre hoje e os próximos 30 dias")
    calendar = ensure_fresh(requested)
    return {**daily_board(requested, evaluation().get("operational_version") or selected_version()),
            "calendar": calendar,
            "feed_configured": bool(os.getenv("ODDS_API_KEY")),
            "last_refresh": _last_quote_time()}


@app.get("/api/upcoming")
def upcoming(days: int = Query(3, ge=1, le=7)):
    today = datetime.now(ZoneInfo("Europe/Lisbon")).date()
    version = evaluation().get("operational_version") or selected_version()
    boards = []
    calendars = []
    for offset in range(days):
        target = today + timedelta(days=offset)
        calendars.append(ensure_fresh(target))
        boards.append(daily_board(target, version))
    items = sorted((item for board in boards for item in board["items"]), key=lambda item: item["start_at"])
    return {"date": today.isoformat(), "days": days, "items": items, "count": len(items),
            "calendar": calendars, "status": "research_only", "quote_max_age_hours": 6,
            "feed_configured": bool(os.getenv("ODDS_API_KEY")), "last_refresh": _last_quote_time()}


@app.get("/api/recent")
def recent(days: int = Query(3, ge=1, le=7)):
    today = datetime.now(ZoneInfo("Europe/Lisbon")).date()
    calendars = [ensure_fresh(today - timedelta(days=offset)) for offset in range(days)]
    earliest = datetime.combine(today - timedelta(days=days - 1), datetime.min.time(), tzinfo=ZoneInfo("Europe/Lisbon"))
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(select(recent_results).where(
            recent_results.c.start_at >= earliest,
            recent_results.c.start_at <= datetime.now(ZoneInfo("Europe/Lisbon")),
            recent_results.c.winner.is_not(None), recent_results.c.score.is_not(None),
        ).order_by(desc(recent_results.c.start_at)).limit(300)).mappings()]
    for row in rows:
        row["tour"] = "Masculino" if row["tour"] == "ATP" else "Feminino"
        row["start_at"] = row["start_at"].isoformat()
        row["last_seen_at"] = row["last_seen_at"].isoformat()
    return {"items": rows, "count": len(rows), "calendar": calendars,
            "source": "ESPN scoreboard", "training_status": "not_in_training_archive"}


def _last_quote_time() -> str | None:
    with engine.connect() as conn:
        value = conn.execute(select(func.max(fixture_odds.c.observed_at))).scalar_one()
    return value.isoformat() if value else None


@app.post("/api/odds/refresh")
def refresh_odds(region: str = Query("eu", pattern="^(eu|uk|us|au)$")):
    if not os.getenv("ODDS_API_KEY"):
        raise HTTPException(409, "Configura ODDS_API_KEY no servidor antes de atualizar")
    try:
        return ingest_current_odds(region=region)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        # Never return URLs, provider responses or credentials to the browser.
        raise HTTPException(502, "A fonte de odds não respondeu; tenta novamente mais tarde") from exc


class TicketLeg(BaseModel):
    selection: str = Field(min_length=1, max_length=140)
    decimal_odds: float = Field(gt=1, le=1000)
    fixture_id: str | None = None
    bookmaker: str | None = None
    source: str = Field(default="manual", pattern="^(manual|provider)$")
    observed_at: datetime | None = None
    start_at: datetime | None = None


class TicketRequest(BaseModel):
    legs: list[TicketLeg] = Field(min_length=1, max_length=8)
    kind: str = Field(pattern="^(single|accumulator|system|round_robin)$")
    total_stake: float = Field(gt=0, le=100000)
    system_size: int | None = None


@app.post("/api/parlay/calculate")
def parlay_calculate(ticket: TicketRequest):
    try:
        return calculate_ticket([leg.model_dump() for leg in ticket.legs],
                                ticket.kind, ticket.total_stake, ticket.system_size)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/overview")
def overview():
    init_db()
    report = evaluation()
    family = report.get("selected_by_validation")
    with engine.connect() as conn:
        latest = conn.execute(select(func.max(matches.c.event_date))).scalar_one()
        first = conn.execute(select(func.min(matches.c.event_date))).scalar_one()
        sources = conn.execute(select(func.count(raw_ingestions.c.id))).scalar_one()
    return {
        "counts": counts(), "first_event_date": first.isoformat() if first else None,
        "last_event_date": latest.isoformat() if latest else None,
        "raw_files": sources, "selected_family": family,
        "selected_version": selected_version(),
        "validation": report.get(family, {}).get("validation") if family else None,
        "test_oos": report.get(family, {}).get("test_oos") if family else None,
        "betting_backtest": report.get("betting_backtest", "not_run"),
        "status": "investigacao_sem_sinais_aprovados",
        "date_precision": "inicio_do_torneio",
    }


@app.get("/api/models")
def models():
    return evaluation()


@app.get("/api/backtest/predictions")
def prediction_backtest():
    path = DATA_DIR.parent / "artifacts" / "prediction_backtest.json"
    if not path.exists():
        raise HTTPException(404, "Executa scripts/backtest_predictions.py para criar o relatório")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/matches")
def list_matches(
    tour: str | None = Query(None, pattern="^(ATP|WTA)$"),
    surface: str | None = Query(None, pattern="^(Hard|Clay|Grass|Carpet|Unknown)$"),
    year: int | None = Query(None, ge=2015, le=2100),
    search: str | None = Query(None, max_length=100),
    limit: int = Query(40, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = _match_query()
    filters = []
    if tour:
        filters.append(matches.c.tour == tour)
    if surface:
        filters.append(matches.c.surface == surface)
    if year:
        filters.append(func.extract("year", matches.c.event_date) == year)
    if search:
        a, b = players.alias("sa"), players.alias("sb")
        # Search is parameterized through SQLAlchemy. IDs are used so no duplicate rows appear.
        pattern = f"%{search.strip()}%"
        filters.append(or_(matches.c.tournament.ilike(pattern),
                           matches.c.player_a_id.in_(select(a.c.id).where(a.c.name.ilike(pattern))),
                           matches.c.player_b_id.in_(select(b.c.id).where(b.c.name.ilike(pattern)))))
    stmt = stmt.where(*filters).order_by(desc(matches.c.event_date), matches.c.tournament, matches.c.id)
    with engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(matches).where(*filters)).scalar_one()
        records = [dict(r) for r in conn.execute(stmt.limit(limit).offset(offset)).mappings()]
    return {"total": total, "limit": limit, "offset": offset,
            "items": [_serialize(r) for r in records]}


@app.get("/api/matches/{match_id:path}")
def match_detail(match_id: str):
    with engine.connect() as conn:
        record = conn.execute(_match_query().where(matches.c.id == match_id)).mappings().first()
        if not record:
            raise HTTPException(404, "Jogo não encontrado")
        odds = [dict(r) for r in conn.execute(select(odds_snapshots).where(
            odds_snapshots.c.match_id == match_id).order_by(odds_snapshots.c.observed_at)).mappings()]
    for item in odds:
        item["observed_at"] = item["observed_at"].isoformat()
    return {**_serialize(dict(record)), "odds_history": odds,
            "odds_timing_verified": False,
            "time_note": "A fonte de resultados fornece apenas a data inicial do torneio; não a hora deste jogo."}


class PriceScenario(BaseModel):
    match_id: str
    selection: str = Field(pattern="^(a|b)$")
    decimal_odds: float = Field(gt=1, le=1000)
    opposing_odds: float | None = Field(default=None, gt=1, le=1000)


@app.post("/api/price-scenario")
def price_scenario(scenario: PriceScenario):
    version = selected_version()
    if not version:
        raise HTTPException(409, "Modelo ainda não treinado")
    with engine.connect() as conn:
        row = conn.execute(select(predictions).where(and_(
            predictions.c.match_id == scenario.match_id,
            predictions.c.model_version == version))).mappings().first()
    if not row:
        raise HTTPException(404, "Previsão indisponível")
    p = row["probability_a"] if scenario.selection == "a" else 1 - row["probability_a"]
    implied = 1 / scenario.decimal_odds
    no_vig = (implied / (implied + 1 / scenario.opposing_odds)) if scenario.opposing_odds else None
    return {
        "probability": p, "fair_odds": 1 / p, "market_implied_probability": implied,
        "market_no_vig_probability": no_vig,
        "probability_edge": p - no_vig if no_vig is not None else None,
        "price_edge": scenario.decimal_odds * p - 1,
        "expected_value": scenario.decimal_odds * p - 1,
        "status": "cenario_hipotetico_nao_validado",
        "note": "Preço introduzido manualmente. Não constitui odd histórica verificada nem sinal de aposta.",
    }


@app.get("/api/data-sources")
def data_sources():
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(select(raw_ingestions).order_by(raw_ingestions.c.id)).mappings()]
    for row in rows:
        row["ingested_at"] = row["ingested_at"].isoformat()
    return {"sources": rows, "license": "CC BY-NC-SA 4.0", "use": "investigação não comercial"}

