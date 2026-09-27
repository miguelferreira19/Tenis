from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import (
    JSON, CheckConstraint, Column, Date, DateTime, Float, ForeignKey,
    Integer, MetaData, String, Table, Text, UniqueConstraint, create_engine, event,
    func,
)

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.getenv("TENNIS_DATA_DIR", str(ROOT / "data"))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'tennis_quant.db'}")
engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _sqlite_settings(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
metadata = MetaData()

players = Table(
    "players", metadata,
    Column("id", String(32), primary_key=True),
    Column("source_id", String(20), nullable=False),
    Column("tour", String(3), nullable=False),
    Column("name", String(140), nullable=False),
    Column("country", String(3)),
    Column("hand", String(2)),
    UniqueConstraint("tour", "source_id"),
)

tournaments = Table(
    "tournaments", metadata,
    Column("id", String(80), primary_key=True),
    Column("tour", String(3), nullable=False),
    Column("name", String(180), nullable=False),
    Column("surface", String(30)),
    Column("level", String(8)),
    Column("start_date", Date, nullable=False),
)

matches = Table(
    "matches", metadata,
    Column("id", String(110), primary_key=True),
    Column("tour", String(3), nullable=False, index=True),
    Column("tournament_id", String(80), ForeignKey("tournaments.id"), nullable=False),
    Column("tournament", String(180), nullable=False),
    Column("event_date", Date, nullable=False, index=True),
    Column("date_precision", String(24), nullable=False),
    Column("round", String(12)),
    Column("surface", String(30)),
    Column("best_of", Integer),
    Column("player_a_id", String(32), ForeignKey("players.id"), nullable=False),
    Column("player_b_id", String(32), ForeignKey("players.id"), nullable=False),
    Column("winner_id", String(32), ForeignKey("players.id"), nullable=False),
    Column("score", String(150)),
    Column("rank_a", Integer),
    Column("rank_b", Integer),
    Column("stats_a", JSON),
    Column("stats_b", JSON),
    Column("source_url", Text, nullable=False),
    Column("source_sha256", String(64), nullable=False),
    CheckConstraint("player_a_id <> player_b_id", name="different_players"),
)

model_versions = Table(
    "model_versions", metadata,
    Column("id", String(100), primary_key=True),
    Column("family", String(32), nullable=False),
    Column("trained_at", DateTime(timezone=True), nullable=False),
    Column("train_end", Date, nullable=False),
    Column("validation_end", Date, nullable=False),
    Column("dataset_hash", String(64), nullable=False),
    Column("feature_version", String(32), nullable=False),
    Column("parameters", JSON, nullable=False),
    Column("status", String(32), nullable=False),
)

predictions = Table(
    "predictions", metadata,
    Column("id", String(150), primary_key=True),
    Column("match_id", String(110), ForeignKey("matches.id"), nullable=False, index=True),
    Column("model_version", String(100), ForeignKey("model_versions.id"), nullable=False),
    Column("feature_version", String(32), nullable=False),
    Column("as_of", DateTime(timezone=True), nullable=False),
    Column("probability_a", Float, nullable=False),
    Column("fair_odds_a", Float, nullable=False),
    Column("fair_odds_b", Float, nullable=False),
    Column("split", String(16), nullable=False),
    Column("features", JSON, nullable=False),
    Column("quality", JSON, nullable=False),
    CheckConstraint("probability_a > 0 AND probability_a < 1", name="valid_probability"),
    UniqueConstraint("match_id", "model_version"),
)

odds_snapshots = Table(
    "odds_snapshots", metadata,
    Column("id", String(120), primary_key=True),
    Column("match_id", String(110), ForeignKey("matches.id"), nullable=False, index=True),
    Column("market", String(60), nullable=False),
    Column("selection_id", String(32), nullable=False),
    Column("bookmaker", String(80), nullable=False),
    Column("decimal_odds", Float, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("source", String(200), nullable=False),
    Column("source_ref", String(300), nullable=False),
    CheckConstraint("decimal_odds > 1", name="valid_odds"),
)

backtest_runs = Table(
    "backtest_runs", metadata,
    Column("id", String(100), primary_key=True),
    Column("model_version", String(100), ForeignKey("model_versions.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("split", String(16), nullable=False),
    Column("metrics", JSON, nullable=False),
    Column("status", String(32), nullable=False),
)

raw_ingestions = Table(
    "raw_ingestions", metadata,
    Column("id", String(100), primary_key=True),
    Column("source_url", Text, nullable=False),
    Column("local_path", Text, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
    Column("row_count", Integer, nullable=False),
    Column("quality", JSON, nullable=False),
)


def init_db() -> None:
    metadata.create_all(engine)


def counts() -> dict[str, int]:
    with engine.connect() as conn:
        return {
            "players": conn.execute(func.count(players.c.id).select()).scalar_one(),
            "tournaments": conn.execute(func.count(tournaments.c.id).select()).scalar_one(),
            "matches": conn.execute(func.count(matches.c.id).select()).scalar_one(),
            "odds_snapshots": conn.execute(func.count(odds_snapshots.c.id).select()).scalar_one(),
            "predictions": conn.execute(func.count(predictions.c.id).select()).scalar_one(),
        }

