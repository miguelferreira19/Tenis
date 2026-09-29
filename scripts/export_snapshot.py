"""Escreve as respostas da API como JSON estático para o site publicado (GitHub Pages).

Falha (exit != 0) se a ESPN não responder para os dias principais, para que o
site anterior fique no ar em vez de ser substituído por uma agenda vazia.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from tennis_quant import api
from tennis_quant.espn_fixtures import refresh_day
from tennis_quant.ingest import bootstrap

LISBON = ZoneInfo("Europe/Lisbon")
HORIZON_DAYS = 7  # hoje + 6; o selector de datas do site estático acaba aqui
UNAVAILABLE = "temporarily_unavailable"


def write(out: Path, name: str, payload: dict) -> None:
    path = out / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    # allow_nan=False: um NaN geraria JSON inválido no browser; melhor falhar aqui.
    path.write_text(json.dumps(jsonable_encoder(payload), ensure_ascii=False, allow_nan=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "apps" / "dashboard" / "public" / "data")
    parser.add_argument("--bootstrap", action="store_true",
                        help="descarrega os CSV fixados e reconstrói a base (uso no CI)")
    args = parser.parse_args()

    if args.bootstrap:
        bootstrap()
    api.init_db()

    generated_at = datetime.now(timezone.utc).isoformat()
    today = datetime.now(LISBON).date()

    upcoming = api.upcoming(days=3)
    recent = api.recent(days=3)
    down = [c for c in upcoming["calendar"] + recent["calendar"] if c.get("status") == UNAVAILABLE]
    if down:
        # ensure_fresh engole o erro; repetir um pedido direto para o log dizer porquê.
        try:
            refresh_day(today)
            why = "pedido direto respondeu bem"
        except Exception as exc:  # noqa: BLE001 - só diagnóstico
            why = f"{type(exc).__name__}: {exc}"[:300]
        raise SystemExit(f"ESPN indisponível em {len(down)} dia(s) ({why}); snapshot anterior mantido")

    write(args.out, "upcoming", {**upcoming, "generated_at": generated_at})
    write(args.out, "recent", recent)
    write(args.out, "meta", {"generated_at": generated_at, "horizon_days": HORIZON_DAYS,
                             **{k: upcoming[k] for k in ("feed_configured", "last_refresh", "quote_max_age_hours")}})
    for offset in range(HORIZON_DAYS):
        day = today + timedelta(days=offset)
        board = api.daily(day=day)
        # Dias distantes podem falhar sem invalidar o resto: o site mostra erro só nesse dia.
        if board["calendar"].get("status") != UNAVAILABLE:
            write(args.out, f"daily/{day.isoformat()}", {**board, "generated_at": generated_at})

    write(args.out, "overview", api.overview())
    write(args.out, "models", api.models())
    try:
        write(args.out, "backtest", api.prediction_backtest())
    except HTTPException:
        print("backtest: relatório em falta, ignorado")
    sources = api.data_sources()
    for row in sources["sources"]:
        row.pop("local_path", None)  # caminho da máquina, sem interesse público
    write(args.out, "data-sources", sources)

    print(f"snapshot em {args.out}: {upcoming['count']} jogos próximos, {recent['count']} resultados recentes")


if __name__ == "__main__":
    main()
