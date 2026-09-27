from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, or_, select

from .db import DATA_DIR, counts, engine, init_db, matches, odds_snapshots, players, predictions, raw_ingestions

app = FastAPI(title="Tennis Quant API", version="0.1.0", description="Investigação quantitativa em ténis")
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
    return {"status": "ok", "version": "0.1.0"}


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

