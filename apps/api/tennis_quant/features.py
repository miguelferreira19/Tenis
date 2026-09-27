from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from math import log

import numpy as np
from sqlalchemy import select

from .db import engine, matches

FEATURE_VERSION = "prematch-v4"
FEATURE_NAMES = (
    "elo_global", "elo_surface", "ranking_log", "form_10",
    "serve_points", "return_points", "rest_days", "experience_log",
    "surface_serve_shrunk", "surface_return_shrunk", "match_load_30d",
)


@dataclass
class PlayerState:
    elo: float = 1500.0
    surface_elo: dict[str, float] = field(default_factory=dict)
    surface_n: dict[str, int] = field(default_factory=dict)
    outcomes: deque = field(default_factory=lambda: deque(maxlen=10))
    serve: deque = field(default_factory=lambda: deque(maxlen=20))
    returns: deque = field(default_factory=lambda: deque(maxlen=20))
    surface_serve: dict[str, deque] = field(default_factory=dict)
    surface_returns: dict[str, deque] = field(default_factory=dict)
    recent_dates: deque = field(default_factory=lambda: deque(maxlen=40))
    last_event: date | None = None
    last_rank: int | None = None
    n_matches: int = 0

    def surface_rating(self, surface: str) -> float:
        n = self.surface_n.get(surface, 0)
        weight = n / (n + 20)
        return self.elo + weight * (self.surface_elo.get(surface, 1500.0) - self.elo)

    def form(self) -> float:
        return sum(self.outcomes) / len(self.outcomes) if self.outcomes else 0.5

    def recent_serve(self) -> float:
        return sum(self.serve) / len(self.serve) if self.serve else 0.62

    def recent_return(self) -> float:
        return sum(self.returns) / len(self.returns) if self.returns else 0.38

    def rest(self, event_date: date) -> int:
        if self.last_event is None:
            return 14
        return min(max((event_date - self.last_event).days, 0), 14)

    def surface_stat(self, surface: str, kind: str) -> float:
        sample = (self.surface_serve if kind == "serve" else self.surface_returns).get(surface, ())
        prior = self.recent_serve() if kind == "serve" else self.recent_return()
        # Ten effective prior matches avoid extreme estimates on rare surfaces.
        return (sum(sample) + 10 * prior) / (len(sample) + 10)

    def load_30d(self, event_date: date) -> int:
        return sum(0 < (event_date - previous).days <= 30 for previous in self.recent_dates)


def _service_points_won(stats: dict | None) -> float | None:
    if not stats:
        return None
    svpt, first_won, second_won = (stats.get(k) for k in ("svpt", "1stWon", "2ndWon"))
    if not svpt or first_won is None or second_won is None:
        return None
    value = (first_won + second_won) / svpt
    return value if 0 <= value <= 1 else None


def _elo_probability(diff: float) -> float:
    return 1 / (1 + 10 ** (-diff / 400))


def _feature_record(row: dict, states: dict[str, PlayerState]) -> dict:
    a, b = states[row["player_a_id"]], states[row["player_b_id"]]
    surface = row["surface"] or "Unknown"
    event_date = row["event_date"]
    rank_a, rank_b = a.last_rank, b.last_rank
    rank_diff = log((rank_b or 1000) + 1) - log((rank_a or 1000) + 1)
    details = {
        "elo_a": round(a.elo, 2), "elo_b": round(b.elo, 2),
        "surface_elo_a": round(a.surface_rating(surface), 2),
        "surface_elo_b": round(b.surface_rating(surface), 2),
        "form_a": round(a.form(), 3), "form_b": round(b.form(), 3),
        "serve_a": round(a.recent_serve(), 3), "serve_b": round(b.recent_serve(), 3),
        "return_a": round(a.recent_return(), 3), "return_b": round(b.recent_return(), 3),
        "rest_a": a.rest(event_date), "rest_b": b.rest(event_date),
        "matches_a": a.n_matches, "matches_b": b.n_matches,
        "rank_a": rank_a, "rank_b": rank_b,
        "surface_serve_a": round(a.surface_stat(surface, "serve"), 3),
        "surface_serve_b": round(b.surface_stat(surface, "serve"), 3),
        "surface_return_a": round(a.surface_stat(surface, "return"), 3),
        "surface_return_b": round(b.surface_stat(surface, "return"), 3),
        "load_30d_a": a.load_30d(event_date), "load_30d_b": b.load_30d(event_date),
    }
    features = np.array([
        (a.elo - b.elo) / 400,
        (a.surface_rating(surface) - b.surface_rating(surface)) / 400,
        rank_diff,
        a.form() - b.form(),
        a.recent_serve() - b.recent_serve(),
        a.recent_return() - b.recent_return(),
        (a.rest(event_date) - b.rest(event_date)) / 14,
        log1p(a.n_matches) - log1p(b.n_matches),
        a.surface_stat(surface, "serve") - b.surface_stat(surface, "serve"),
        a.surface_stat(surface, "return") - b.surface_stat(surface, "return"),
        (a.load_30d(event_date) - b.load_30d(event_date)) / 12,
    ], dtype=float)
    baseline = _elo_probability((a.elo - b.elo) * 0.55 +
                                (a.surface_rating(surface) - b.surface_rating(surface)) * 0.45)
    return {
        "row": row, "x": features, "y": int(row["winner_id"] == row["player_a_id"]),
        "elo_probability": baseline, "details": details,
        "quality": {
            "experience_a": a.n_matches, "experience_b": b.n_matches,
            "serve_sample_a": len(a.serve), "serve_sample_b": len(b.serve),
            "return_sample_a": len(a.returns), "return_sample_b": len(b.returns),
            "date_precision": "tournament_start",
        },
    }


def log1p(value: int) -> float:
    return log(1 + value)


def _update(row: dict, states: dict[str, PlayerState]) -> None:
    a, b = states[row["player_a_id"]], states[row["player_b_id"]]
    a_win = row["winner_id"] == row["player_a_id"]
    score_a = 1.0 if a_win else 0.0
    surface = row["surface"] or "Unknown"
    p = _elo_probability(a.elo - b.elo)
    delta = 32 * (score_a - p)
    a.elo += delta
    b.elo -= delta
    sa, sb = a.surface_elo.get(surface, 1500.0), b.surface_elo.get(surface, 1500.0)
    sp = _elo_probability(sa - sb)
    sdelta = 24 * (score_a - sp)
    a.surface_elo[surface], b.surface_elo[surface] = sa + sdelta, sb - sdelta
    a.surface_n[surface] = a.surface_n.get(surface, 0) + 1
    b.surface_n[surface] = b.surface_n.get(surface, 0) + 1
    a.outcomes.append(int(a_win))
    b.outcomes.append(int(not a_win))
    serve_a, serve_b = _service_points_won(row["stats_a"]), _service_points_won(row["stats_b"])
    if serve_a is not None:
        a.serve.append(serve_a)
        b.returns.append(1 - serve_a)
        a.surface_serve.setdefault(surface, deque(maxlen=20)).append(serve_a)
        b.surface_returns.setdefault(surface, deque(maxlen=20)).append(1 - serve_a)
    if serve_b is not None:
        b.serve.append(serve_b)
        a.returns.append(1 - serve_b)
        b.surface_serve.setdefault(surface, deque(maxlen=20)).append(serve_b)
        a.surface_returns.setdefault(surface, deque(maxlen=20)).append(1 - serve_b)
    for state in (a, b):
        state.n_matches += 1
        state.last_event = row["event_date"]
        state.recent_dates.append(row["event_date"])
    if row["rank_a"] is not None:
        a.last_rank = row["rank_a"]
    if row["rank_b"] is not None:
        b.last_rank = row["rank_b"]


def eligible_for_model(row: dict) -> bool:
    score = (row.get("score") or "").upper()
    return bool(score) and not any(marker in score for marker in ("W/O", "RET", "DEF", "ABN", "UNP"))


def build_feature_rows() -> list[dict]:
    with engine.connect() as conn:
        records = [dict(r) for r in conn.execute(select(matches).order_by(
            matches.c.tour, matches.c.event_date, matches.c.tournament_id, matches.c.id)).mappings()]
    # Walkovers and retirements have different bookmaker settlement rules and
    # do not represent an observed completed-match outcome for this target.
    records = [r for r in records if eligible_for_model(r)]
    states: dict[str, dict[str, PlayerState]] = {
        "ATP": defaultdict(PlayerState), "WTA": defaultdict(PlayerState),
    }
    result = []
    i = 0
    while i < len(records):
        tour, day = records[i]["tour"], records[i]["event_date"]
        j = i
        while j < len(records) and (records[j]["tour"], records[j]["event_date"]) == (tour, day):
            j += 1
        group = records[i:j]
        for row in group:
            result.append(_feature_record(row, states[tour]))
        for row in group:
            _update(row, states[tour])
        i = j
    return result


@lru_cache(maxsize=24)
def _states_before(tour: str, event_date: date) -> dict[str, PlayerState]:
    if tour not in {"ATP", "WTA"}:
        raise ValueError("Circuito desconhecido")
    with engine.connect() as conn:
        records = [dict(r) for r in conn.execute(select(matches).where(
            matches.c.tour == tour, matches.c.event_date < event_date
        ).order_by(matches.c.event_date, matches.c.tournament_id, matches.c.id)).mappings()]
    states: dict[str, PlayerState] = defaultdict(PlayerState)
    for record in records:
        if eligible_for_model(record):
            _update(record, states)
    return states


def fixture_feature(player_a_id: str, player_b_id: str, event_date: date,
                    tour: str, surface: str = "Unknown") -> dict:
    """Use only completed tournament groups strictly before the fixture date."""
    states = _states_before(tour, event_date)
    row = {"player_a_id": player_a_id, "player_b_id": player_b_id,
           "event_date": event_date, "surface": surface, "winner_id": player_a_id}
    return _feature_record(row, states)

