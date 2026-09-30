"""Recover discarded raw fields, strictly lagged to a previous tournament."""
import csv
import hashlib
import io
from math import isfinite, log1p
from pathlib import Path

import numpy as np
from sqlalchemy import select

from .db import DATA_DIR, engine, raw_ingestions

NAMES = ("age_difference", "age_curve_difference", "height_difference",
         "ranking_points_log", "metadata_missing_difference")


def raw_metadata():
    result = {}
    with engine.connect() as conn:
        sources = list(conn.execute(select(raw_ingestions)).mappings())
    for source in sources:
        if "/raw/results/" not in source["local_path"].replace("\\", "/"):
            continue
        path = Path(source["local_path"])
        if not path.is_file():
            # A copied database retains the original workspace's absolute paths.
            path = DATA_DIR / "raw" / "results" / path.parent.name / path.name
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ValueError("Checksum raw divergente")
        tour = "ATP" if path.parent.name == "atp" else "WTA"
        for r in csv.DictReader(io.StringIO(data.decode("utf-8-sig"))):
            key = f"{tour}:{r['tourney_id']}:{r['match_num']}"
            result[key] = {f"{tour}:{r[f'{side}_id']}": {
                field: _valid_number(r.get(f"{side}_{field}"), field)
                for field in ("age", "ht", "rank_points")}
                for side in ("winner", "loser")}
    return result


def _valid_number(value, field):
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    low, high = {"age": (10, 70), "ht": (130, 240), "rank_points": (0, 100000)}[field]
    return number if isfinite(number) and low <= number <= high else None


def metadata_features(rows, raw=None):
    raw = raw_metadata() if raw is None else raw
    history = {}
    extra = np.zeros((len(rows), len(NAMES)))
    coverage = {"prior_age": 0, "prior_height": 0, "prior_ranking_points": 0, "player_snapshots": 2 * len(rows)}
    i = 0
    while i < len(rows):
        first = rows[i]["row"]
        day, tour = first["event_date"], first["tour"]
        j = i
        while j < len(rows) and (rows[j]["row"]["event_date"], rows[j]["row"]["tour"]) == (day, tour):
            j += 1
        for k in range(i, j):
            r = rows[k]["row"]
            vectors = []
            for player in (r["player_a_id"], r["player_b_id"]):
                old_day, old = history.get(player, (day, {}))
                age = old.get("age")
                ht, points = old.get("ht"), old.get("rank_points")
                coverage["prior_age"] += int(age is not None)
                coverage["prior_height"] += int(ht is not None)
                coverage["prior_ranking_points"] += int(points is not None)
                age_now = age + (day - old_day).days / 365.25 if age is not None else 26
                vectors.append(np.array([age_now / 10, ((age_now - 26) / 10) ** 2,
                                         (ht if ht is not None else (185 if tour == "ATP" else 173)) / 20,
                                         log1p(points if points is not None else 0) / 10,
                                         sum(v is None for v in (age, ht, points)) / 3]))
            extra[k] = vectors[0] - vectors[1]
        for k in range(i, j):
            r = rows[k]["row"]
            for player, values in raw.get(r["id"], {}).items():
                history[player] = (day, values)
        i = j
    return extra, coverage
