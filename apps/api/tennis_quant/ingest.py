from __future__ import annotations

import csv
import hashlib
import io
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .db import DATA_DIR, engine, init_db, matches, players, raw_ingestions, tournaments

ARCHIVE_REF = "83733587353df8a41f2fd4f516147d5aa83f5a8d"
ARCHIVE_ROOT = "https://raw.githubusercontent.com/Aneeshers/tennis-sackmann-archive"
FEATURE_SOURCE = "Jeff Sackmann / Tennis Abstract; archive mirror by Aneeshers"


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def _date(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def _stats(row: dict[str, str], prefix: str) -> dict[str, int | None]:
    return {name: _int(row.get(f"{prefix}_{name}")) for name in
            ("ace", "df", "svpt", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced")}


def _insert_ignore(conn, table, rows: list[dict]) -> None:
    if not rows:
        return
    dialect = conn.dialect.name
    for offset in range(0, len(rows), 400):
        batch = rows[offset:offset + 400]
        if dialect == "sqlite":
            stmt = sqlite_insert(table).values(batch).on_conflict_do_nothing()
        elif dialect == "postgresql":
            stmt = pg_insert(table).values(batch).on_conflict_do_nothing()
        else:
            stmt = insert(table).values(batch)
        conn.execute(stmt)


def download_year(tour: str, year: int) -> tuple[str, Path, str, str]:
    tour = tour.upper()
    if tour not in ("ATP", "WTA") or year < 2015 or year > date.today().year:
        raise ValueError("Circuito ou ano inválido")
    name = f"{tour.lower()}_matches_{year}.csv"
    url = f"{ARCHIVE_ROOT}/{ARCHIVE_REF}/{tour.lower()}/{name}"
    folder = DATA_DIR / "raw" / "results" / tour.lower()
    folder.mkdir(parents=True, exist_ok=True)
    response = httpx.get(url, timeout=40, follow_redirects=True)
    response.raise_for_status()
    raw = response.content
    if not raw.startswith(b"tourney_id,"):
        raise ValueError(f"Formato inesperado: {url}")
    digest = hashlib.sha256(raw).hexdigest()
    path = folder / f"{name.removesuffix('.csv')}_{digest[:12]}.csv"
    if not path.exists():
        path.write_bytes(raw)
    elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f"Ficheiro raw alterado: {path}")
    return tour, path, url, digest


def ingest_file(tour: str, path: Path, url: str, digest: str) -> dict:
    init_db()
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Checksum raw divergente")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    p_rows: dict[str, dict] = {}
    t_rows: dict[str, dict] = {}
    m_rows: dict[str, dict] = {}
    invalid = 0
    future = 0
    for row in reader:
        try:
            event_day = _date(row["tourney_date"])
            if event_day > date.today():
                future += 1
                continue
            win_source, lose_source = row["winner_id"], row["loser_id"]
            if not win_source or not lose_source or win_source == lose_source:
                raise ValueError("player_id inválido")
            win_id, lose_id = f"{tour}:{win_source}", f"{tour}:{lose_source}"
            a_id, b_id = sorted((win_id, lose_id))
            tournament_id = f"{tour}:{row['tourney_id']}"
            match_id = f"{tournament_id}:{row['match_num']}"
            surface = row.get("surface") or "Unknown"
            t_rows[tournament_id] = {
                "id": tournament_id, "tour": tour, "name": row["tourney_name"],
                "surface": surface, "level": row.get("tourney_level"), "start_date": event_day,
            }
            for side, pid in (("winner", win_id), ("loser", lose_id)):
                p_rows[pid] = {
                    "id": pid, "source_id": row[f"{side}_id"], "tour": tour,
                    "name": row[f"{side}_name"], "country": row.get(f"{side}_ioc"),
                    "hand": row.get(f"{side}_hand"),
                }
            a_is_winner = a_id == win_id
            record = {
                "id": match_id, "tour": tour, "tournament_id": tournament_id,
                "tournament": row["tourney_name"], "event_date": event_day,
                "date_precision": "tournament_start", "round": row.get("round"),
                "surface": surface, "best_of": _int(row.get("best_of")),
                "player_a_id": a_id, "player_b_id": b_id, "winner_id": win_id,
                "score": row.get("score"),
                "rank_a": _int(row.get("winner_rank" if a_is_winner else "loser_rank")),
                "rank_b": _int(row.get("loser_rank" if a_is_winner else "winner_rank")),
                "stats_a": _stats(row, "w" if a_is_winner else "l"),
                "stats_b": _stats(row, "l" if a_is_winner else "w"),
                "source_url": url, "source_sha256": digest,
            }
            if match_id in m_rows:
                raise ValueError("match_id duplicado")
            m_rows[match_id] = record
        except (KeyError, ValueError):
            invalid += 1
    quality = {"accepted": len(m_rows), "invalid": invalid, "future_excluded": future,
               "date_precision": "tournament_start", "source_license": "CC BY-NC-SA 4.0"}
    with engine.begin() as conn:
        for offset in range(0, len(m_rows), 400):
            ids = list(m_rows)[offset:offset + 400]
            existing = conn.execute(select(matches.c.id, matches.c.source_sha256).where(matches.c.id.in_(ids)))
            if any(old_hash != digest for _, old_hash in existing):
                raise ValueError("Conflito com jogo já importado de outro snapshot; usar uma base nova para uma revisão nova")
        _insert_ignore(conn, players, list(p_rows.values()))
        _insert_ignore(conn, tournaments, list(t_rows.values()))
        _insert_ignore(conn, matches, list(m_rows.values()))
        _insert_ignore(conn, raw_ingestions, [{
            "id": digest, "source_url": url, "local_path": str(path), "sha256": digest,
            "ingested_at": datetime.now(timezone.utc), "row_count": len(m_rows), "quality": quality,
        }])
    return {"tour": tour, "year": int(path.stem.split("_")[2]), **quality}


def bootstrap(start: int = 2015, end: int | None = None) -> list[dict]:
    end = min(end or date.today().year, date.today().year)
    jobs = [(tour, year) for tour in ("ATP", "WTA") for year in range(start, end + 1)]
    downloads = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(download_year, *job): job for job in jobs}
        for future in as_completed(futures):
            downloads.append(future.result())
    results = [ingest_file(*item) for item in sorted(downloads, key=lambda x: (x[0], x[1].name))]
    manifest = {
        "archive_ref": ARCHIVE_REF, "source": FEATURE_SOURCE,
        "license": "CC BY-NC-SA 4.0; investigação não comercial",
        "created_at": datetime.now(timezone.utc).isoformat(), "files": results,
    }
    (DATA_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return results

