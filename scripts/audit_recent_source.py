"""Stage immutable recent CSVs and audit compatibility; never mutate the archive."""
import csv
import hashlib
import io
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from tennis_quant.db import engine, matches, players
from tennis_quant.live_odds import _normal
from tennis_quant.research_io import write_json


def audit(rows, tour, known, cutoff):
    keys, invalid, missing, conflict, mapping = Counter(), [], set(), set(), {}
    dates = []
    service = recent = future = 0
    for index, row in enumerate(rows):
        try:
            day = datetime.strptime(row["tourney_date"], "%Y%m%d").date()
            if day > date.today():
                future += 1
                continue
            if row["winner_id"] == row["loser_id"]:
                raise ValueError("identical players")
            dates.append(day)
            recent += day > cutoff
            keys[(row["tourney_id"], row["match_num"])] += 1
            service += all(row.get(f"{side}_{field}") for side in ("w", "l")
                           for field in ("svpt", "1stIn", "1stWon", "2ndWon"))
            for side in ("winner", "loser"):
                name, source_id = row[f"{side}_name"], row[f"{side}_id"]
                if not name or not source_id:
                    raise ValueError("empty identity")
                candidates = known.get((tour, _normal(name)), [])
                key = f"{tour}:{source_id}"
                if len(candidates) != 1:
                    missing.add(name)
                elif key in mapping and mapping[key] != candidates[0]:
                    conflict.add(key)
                else:
                    mapping[key] = candidates[0]
        except (KeyError, ValueError) as exc:
            invalid.append({"row":index+2,"reason":str(exc)})
    for key in conflict:
        mapping.pop(key,None)
    return {"rows":len(rows), "future_rows_excluded":future, "minimum_tournament_date":min(dates).isoformat() if dates else None,
            "maximum_tournament_date":max(dates).isoformat() if dates else None,
            "archive_cutoff":cutoff.isoformat(), "rows_after_archive_cutoff":recent,
            "present_service_fields_rows":service, "service_note":"Presence only; numerical plausibility is not validated by this audit", "duplicate_match_keys":sum(n-1 for n in keys.values()),
            "duplicate_keys":[{"tourney_id":key[0],"match_num":key[1],"rows":n} for key,n in keys.items() if n>1],
            "invalid_rows":invalid, "unresolved_names":sorted(missing), "identity_conflicts":sorted(conflict),
            "name_based_identity_candidates":mapping,
            "identity_note":"Exact normalized names are candidates, not independently verified cross-provider IDs"}


def main():
    known = {}
    with engine.connect() as conn:
        for row in conn.execute(select(players)).mappings():
            known.setdefault((row["tour"],_normal(row["name"])),[]).append(row["id"])
        cutoff = {tour:max(conn.execute(select(matches.c.event_date).where(matches.c.tour==tour)).scalars())
                  for tour in ("ATP","WTA")}
    report = {"retrieved_at":datetime.now(timezone.utc).isoformat(), "source":"TennisMyLife website",
              "documentation":"https://stats.tennismylife.org/tennis-match-database",
              "license_note":"Website declares MIT; WTA upstream provenance and licensing still require review",
              "status":"staged_not_ingested_not_used_for_training", "files":{}}
    folder = ROOT / "data" / "external" / "tml"
    folder.mkdir(parents=True,exist_ok=True)
    for tour,name in (("ATP","2026.csv"),("WTA","2026_wta.csv")):
        url = "https://stats.tennismylife.org/data/"+name
        response = httpx.get(url,timeout=30,follow_redirects=True)
        response.raise_for_status()
        raw = response.content
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        if not rows or "tourney_id" not in rows[0]:
            raise ValueError("Unexpected CSV schema")
        digest = hashlib.sha256(raw).hexdigest()
        path = folder / f"{tour.lower()}_2026_{digest[:16]}.csv"
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError("Staged immutable CSV changed")
        if not path.exists():
            path.write_bytes(raw)
        report["files"][tour] = {"url":url,"sha256":digest,"local_path":str(path.relative_to(ROOT)),
                                 **audit(rows,tour,known,cutoff[tour])}
    write_json(ROOT / "artifacts" / "recent_source_audit.json",report)
    print({tour:{key:value for key,value in info.items() if key in {
        "rows","rows_after_archive_cutoff","maximum_tournament_date","duplicate_match_keys"}}
        for tour,info in report["files"].items()})


if __name__ == "__main__":
    main()
