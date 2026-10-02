"""Historical closing odds (tennis-data.co.uk) joined to the results archive.

The archive dates are tournament starts; tennis-data rows carry the real match
day and closing prices (Bet365, Pinnacle until 2025, market average and max).
"""
from __future__ import annotations

import hashlib
import unicodedata
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import select

from .db import DATA_DIR, engine, matches, players

TD_DIR = DATA_DIR / "external" / "tennisdata"
TD_ROOT = "https://www.tennis-data.co.uk/hrjk-85HytOjkhth76j_ygh4jf7"
PRICE_COLUMNS = ("B365", "PS", "Avg", "Max")


def letters(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    return "".join(c for c in ascii_name if c.isalpha())


def td_key(name: str) -> tuple[str, str]:
    """'Carreno Busta P.' -> ('carrenobusta', 'p'); 'Auger-Aliassime F.' -> ('augeraliassime', 'f')."""
    parts = str(name).strip().split()
    initials = [p for p in parts if p.endswith(".")]
    surname = [p for p in parts if not p.endswith(".")] or parts[:1]
    return letters(" ".join(surname)), letters(initials[0])[:1] if initials else ""


def download(years=range(2015, 2027)) -> list[Path]:
    import httpx
    TD_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for tour, suffix in (("atp", ""), ("wta", "w")):
        for year in years:
            path = TD_DIR / f"{tour}_{year}.xlsx"
            response = httpx.get(f"{TD_ROOT}/{year}{suffix}/{year}.xlsx", timeout=60,
                                 follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            if not response.content.startswith(b"PK"):
                raise ValueError(f"tennis-data devolveu algo que não é xlsx: {tour} {year}")
            path.write_bytes(response.content)
            paths.append(path)
    return paths


def load_odds() -> pd.DataFrame:
    frames = []
    for path in sorted(TD_DIR.glob("*_20*.xlsx")):
        frame = pd.read_excel(path)
        frame["tour"] = path.stem.split("_")[0].upper()
        frame["source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        frames.append(frame)
    if not frames:
        raise FileNotFoundError(f"Sem ficheiros tennis-data em {TD_DIR}")
    odds = pd.concat(frames, ignore_index=True)
    odds["Date"] = pd.to_datetime(odds["Date"]).dt.date
    numeric = [f"{c}{s}" for c in PRICE_COLUMNS for s in "WL"] + \
        [f"{s}{k}" for s in "WL" for k in range(1, 6)] + ["Wsets", "Lsets", "WRank", "LRank", "WPts", "LPts"]
    for col in numeric:
        if col in odds:
            odds[col] = pd.to_numeric(odds[col], errors="coerce")
    return odds


def shin(odds_a: np.ndarray, odds_b: np.ndarray) -> np.ndarray:
    """Shin (1993) de-vig for two outcomes; corrects favourite-longshot bias unlike 1/odds normalisation."""
    pi_a, pi_b = 1 / odds_a, 1 / odds_b
    total = pi_a + pi_b

    def probs(z):
        pa = (np.sqrt(z ** 2 + 4 * (1 - z) * pi_a ** 2 / total) - z) / (2 * (1 - z))
        pb = (np.sqrt(z ** 2 + 4 * (1 - z) * pi_b ** 2 / total) - z) / (2 * (1 - z))
        return pa, pb

    # Sum of probs falls as insider share z rises: bisection for sum == 1.
    lo, hi = np.zeros(len(pi_a)), np.full(len(pi_a), 0.4)
    for _ in range(50):
        z = (lo + hi) / 2
        pa, pb = probs(z)
        over = pa + pb > 1
        lo, hi = np.where(over, z, lo), np.where(over, hi, z)
    pa, pb = probs((lo + hi) / 2)
    return pa / (pa + pb)


def proportional(odds_a: np.ndarray, odds_b: np.ndarray) -> np.ndarray:
    return (1 / odds_a) / (1 / odds_a + 1 / odds_b)


def power(odds_a: np.ndarray, odds_b: np.ndarray) -> np.ndarray:
    """Find k with (1/oa)^k + (1/ob)^k = 1 by bisection."""
    lo, hi = np.full(len(odds_a), 1.0), np.full(len(odds_a), 3.0)
    for _ in range(50):
        k = (lo + hi) / 2
        too_big = (1 / odds_a) ** k + (1 / odds_b) ** k > 1
        lo, hi = np.where(too_big, k, lo), np.where(too_big, hi, k)
    k = (lo + hi) / 2
    return (1 / odds_a) ** k


SCHEDULE = ("days_prev", "games_prev", "sets_prev", "n_14d", "games_7d")


def schedule_features(odds: pd.DataFrame) -> pd.DataFrame:
    """Per-player workload from real match days, using only strictly earlier days.

    tennis-data gives the actual match day and set scores, which the archive
    (tournament start only) cannot. Same-day matches never see each other.
    """
    odds = odds.sort_values(["tour", "Date"], kind="stable").reset_index(drop=True)
    games = np.zeros(len(odds))
    for k in range(1, 6):
        games += odds.get(f"W{k}", pd.Series(0, index=odds.index)).fillna(0).astype(float)
        games += odds.get(f"L{k}", pd.Series(0, index=odds.index)).fillna(0).astype(float)
    sets = odds.get("Wsets", 0).fillna(0).astype(float) + odds.get("Lsets", 0).fillna(0).astype(float)
    history: dict[tuple, list] = {}
    feats = {f"{side}_{name}": np.zeros(len(odds)) for side in "wl" for name in SCHEDULE}
    for (tour, day), block in odds.groupby(["tour", "Date"], sort=False):
        for i in block.index:
            for side, col in (("w", "Winner"), ("l", "Loser")):
                past = history.get((tour, odds.at[i, col]), [])
                if past:
                    last_day, last_games, last_sets = past[-1]
                    feats[f"{side}_days_prev"][i] = min((day - last_day).days, 30)
                    feats[f"{side}_games_prev"][i] = last_games
                    feats[f"{side}_sets_prev"][i] = last_sets
                else:
                    feats[f"{side}_days_prev"][i] = 30
                feats[f"{side}_n_14d"][i] = sum((day - d).days <= 14 for d, _, _ in past[-12:])
                feats[f"{side}_games_7d"][i] = sum(g for d, g, _ in past[-8:] if (day - d).days <= 7)
        for i in block.index:
            for col in ("Winner", "Loser"):
                history.setdefault((tour, odds.at[i, col]), []).append((day, games[i], sets[i]))
    for name, values in feats.items():
        odds[name] = values
    return odds


@lru_cache(maxsize=1)
def archive_frame() -> pd.DataFrame:
    with engine.connect() as conn:
        names = {r.id: r.name for r in conn.execute(select(players.c.id, players.c.name))}
        rows = [dict(r) for r in conn.execute(select(
            matches.c.id, matches.c.tour, matches.c.event_date, matches.c.player_a_id,
            matches.c.player_b_id, matches.c.winner_id, matches.c.tournament)).mappings()]
    frame = pd.DataFrame(rows)
    frame["winner_name"] = frame["winner_id"].map(names)
    frame["loser_name"] = np.where(frame["winner_id"] == frame["player_a_id"],
                                   frame["player_b_id"], frame["player_a_id"])
    frame["loser_name"] = frame["loser_name"].map(names)
    return frame


def _matches_name(full: str, key: tuple[str, str]) -> bool:
    surname, initial = key
    norm = letters(full)
    if not surname or not norm.endswith(surname):
        return False
    first = letters(full.split()[0])[:1] if full else ""
    return not initial or first == initial or len(norm) - len(surname) == 0


def join_archive(odds: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per archive match with closing odds oriented to the winner.

    A tennis-data row is accepted only if exactly one archive match in the same
    tour, within [-4, +16] days of the tournament start, has both names matching.
    Ambiguous or missing rows are dropped and counted.
    """
    odds = schedule_features(load_odds() if odds is None else odds)
    archive = archive_frame()
    # Index by the last two letters of both names: a full name ends with its surname.
    index: dict[tuple, list] = {}
    for m in archive.itertuples(index=False):
        if m.winner_name and m.loser_name:
            index.setdefault((m.tour, letters(m.winner_name)[-2:], letters(m.loser_name)[-2:]), []).append(m)
    out, ambiguous, missing = [], 0, 0
    for row in odds.itertuples(index=False):
        kw, kl = td_key(row.Winner), td_key(row.Loser)
        lo, hi = row.Date - timedelta(days=16), row.Date + timedelta(days=4)
        hits = [m for m in index.get((row.tour, kw[0][-2:], kl[0][-2:]), [])
                if lo <= m.event_date <= hi
                and _matches_name(m.winner_name, kw) and _matches_name(m.loser_name, kl)]
        if len(hits) != 1:
            ambiguous += len(hits) > 1
            missing += not hits
            continue
        hit = hits[0]
        record = {"match_id": hit.id, "match_date": row.Date, "comment": row.Comment,
                  "td_tournament": row.Tournament, "series": getattr(row, "Series", None) or getattr(row, "Tier", None),
                  "round": row.Round, "court": row.Court, "w_rank": row.WRank, "l_rank": row.LRank,
                  "w_pts": row.WPts, "l_pts": row.LPts}
        for name in SCHEDULE:
            record[f"w_{name}"] = getattr(row, f"w_{name}", np.nan)
            record[f"l_{name}"] = getattr(row, f"l_{name}", np.nan)
        for col in PRICE_COLUMNS:
            record[f"{col}_w"] = getattr(row, f"{col}W", np.nan)
            record[f"{col}_l"] = getattr(row, f"{col}L", np.nan)
        out.append(record)
    joined = pd.DataFrame(out).drop_duplicates("match_id", keep=False)
    joined.attrs["coverage"] = {"tennis_data_rows": int(len(odds)), "joined": int(len(joined)),
                                "ambiguous": int(ambiguous), "missing": int(missing)}
    return joined
