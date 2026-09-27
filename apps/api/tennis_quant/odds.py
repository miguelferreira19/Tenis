from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from .db import DATA_DIR, engine, matches, odds_snapshots, raw_ingestions
from .ingest import _insert_ignore

REQUIRED = {"match_id", "market", "selection_id", "bookmaker", "decimal_odds", "observed_at", "source_ref"}


def import_odds_csv(path: Path, source: str) -> dict:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
        raise ValueError(f"Colunas obrigatórias: {', '.join(sorted(REQUIRED))}")
    with engine.connect() as conn:
        known = {r["id"]: (r["player_a_id"], r["player_b_id"])
                 for r in conn.execute(select(matches.c.id, matches.c.player_a_id, matches.c.player_b_id)).mappings()}
    records = []
    for line, row in enumerate(reader, start=2):
        if row["match_id"] not in known:
            raise ValueError(f"Linha {line}: match_id desconhecido")
        if row["market"] != "match_winner":
            raise ValueError(f"Linha {line}: v0.1 só suporta match_winner")
        if row["selection_id"] not in known[row["match_id"]]:
            raise ValueError(f"Linha {line}: seleção não pertence ao jogo")
        odd = float(row["decimal_odds"])
        if not 1 < odd <= 1000:
            raise ValueError(f"Linha {line}: odd inválida")
        observed = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError(f"Linha {line}: observed_at tem de incluir timezone")
        observed = observed.astimezone(timezone.utc)
        if observed > datetime.now(timezone.utc):
            raise ValueError(f"Linha {line}: timestamp futuro")
        if not row["bookmaker"] or not row["source_ref"]:
            raise ValueError(f"Linha {line}: proveniência incompleta")
        identifier = hashlib.sha256((digest + str(line)).encode()).hexdigest()[:32]
        records.append({
            "id": identifier, "match_id": row["match_id"], "market": row["market"],
            "selection_id": row["selection_id"], "bookmaker": row["bookmaker"],
            "decimal_odds": odd, "observed_at": observed, "source": source,
            "source_ref": row["source_ref"],
        })
    folder = DATA_DIR / "raw" / "odds"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"odds_{digest[:12]}.csv"
    if not target.exists():
        target.write_bytes(raw)
    elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise ValueError("Cópia raw alterada")
    with engine.begin() as conn:
        _insert_ignore(conn, odds_snapshots, records)
        _insert_ignore(conn, raw_ingestions, [{
            "id": digest, "source_url": source, "local_path": str(target), "sha256": digest,
            "ingested_at": datetime.now(timezone.utc), "row_count": len(records),
            "quality": {"accepted": len(records), "timing_verified": False,
                        "reason": "hora real do jogo desconhecida"},
        }])
    return {"rows": len(records), "sha256": digest, "timing_verified": False}

