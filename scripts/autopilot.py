"""Piloto automático: lê a Betclic, decide as apostas, gere a banca e fecha resultados.

Corre no GitHub Actions (ou em local) e escreve:
- artifacts/ledger.json — livro permanente de todas as apostas (congeladas ao criar);
- apps/dashboard/public/data/autopilot.json — o que o site mostra.
Nunca coloca apostas: só diz quais e quanto. Banca em papel, 100 € de partida.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from tennis_quant import betclic
from tennis_quant.espn_fixtures import API as ESPN_API, parse_results
from tennis_quant.live_odds import _normal
from tennis_quant.research_io import write_json
from tennis_quant.strategy import Plan, candidates, probability, stakes

LISBON = ZoneInfo("Europe/Lisbon")
LEDGER = ROOT / "artifacts" / "ledger.json"
STRATEGY = ROOT / "artifacts" / "strategy.json"
OUT = ROOT / "apps" / "dashboard" / "public" / "data" / "autopilot.json"
START_BANK = 100.0
MIN_LEAD, MAX_LEAD = timedelta(minutes=20), timedelta(hours=30)
VOID_AFTER = timedelta(days=3)


def load_plan() -> tuple[Plan, dict]:
    report = json.loads(STRATEGY.read_text(encoding="utf-8")) if STRATEGY.exists() else {}
    return Plan(**report.get("plan", {})), report


def lisbon_day(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(LISBON).date().isoformat()


def names_key(a: str, b: str) -> frozenset:
    return frozenset((_normal(a), _normal(b)))


def surnames_key(a: str, b: str) -> frozenset:
    return frozenset((_normal(a).split()[-1], _normal(b).split()[-1]))


def espn_results(days: set[date]) -> list[dict]:
    now = datetime.now(timezone.utc)
    out = []
    for day in sorted(days):
        boards = []
        for tour in ("atp", "wta"):
            r = httpx.get(ESPN_API.format(tour=tour, day=day.strftime("%Y%m%d")), timeout=20,
                          headers={"User-Agent": "TennisQuant/0.4 (personal research)"})
            r.raise_for_status()
            boards.append(r.json())
        out += parse_results(boards, day, now)
    return out


def settle(ledger: list[dict], now: datetime) -> int:
    pending = [b for b in ledger if b["status"] == "pendente" and datetime.fromisoformat(b["start_at"]) < now]
    if not pending:
        return 0
    days = {datetime.fromisoformat(b["start_at"]).date() + timedelta(days=k) for b in pending for k in (-1, 0, 1)}
    try:
        results = espn_results({d for d in days if d <= now.date()})
    except httpx.HTTPError as exc:
        print(f"ESPN indisponível, liquidação adiada: {exc}")
        results = []
    by_names = {names_key(r["player_a"], r["player_b"]): r for r in results}
    by_surnames = {surnames_key(r["player_a"], r["player_b"]): r for r in results}
    settled = 0
    for bet in pending:
        r = by_names.get(names_key(bet["player_a"], bet["player_b"])) or \
            by_surnames.get(surnames_key(bet["player_a"], bet["player_b"]))
        if r and abs(r["start_at"] - datetime.fromisoformat(bet["start_at"])) < timedelta(hours=36):
            pick_name = bet["player_a"] if bet["side"] == "a" else bet["player_b"]
            won = _normal(r["winner"]).split()[-1] == _normal(pick_name).split()[-1]
            # ponytail: retirements settle on the player who advances (ESPN winner); check Betclic rules if it matters.
            bet.update(status="ganha" if won else "perdida", score=r["score"],
                       pnl=round(bet["stake"] * (bet["odds"] - 1), 2) if won else -bet["stake"],
                       settled_at=now.isoformat())
            settled += 1
        elif now - datetime.fromisoformat(bet["start_at"]) > VOID_AFTER:
            bet.update(status="anulada", pnl=0.0, settled_at=now.isoformat())
            settled += 1
    return settled


def bank_state(ledger: list[dict]) -> dict:
    bank, peak, curve = START_BANK, START_BANK, []
    for bet in sorted((b for b in ledger if b["status"] in ("ganha", "perdida", "anulada")),
                      key=lambda b: b["settled_at"]):
        bank += bet["pnl"]
        peak = max(peak, bank)
        curve.append([bet["settled_at"][:10], round(bank, 2)])
    return {"bank": round(bank, 2), "peak": round(peak, 2), "curve": curve}


def place(ledger: list[dict], market: dict, plan: Plan, now: datetime) -> tuple[list[dict], list[dict]]:
    known = {b["match_id"]: b for b in ledger}
    state = bank_state(ledger)
    board, fresh = [], []
    by_day: dict[str, list[dict]] = {}
    for m in market["matches"]:
        start = datetime.fromisoformat(m["start_at"])
        p_a = probability(m["odds_a"], m["odds_b"], plan)
        row = {**m, "p_a": round(p_a, 4), "picked": m["id"] in known}
        board.append(row)
        if m["id"] in known:
            bet = known[m["id"]]
            if bet["status"] == "pendente" and start > now:
                bet["last_odds"] = m["odds_a"] if bet["side"] == "a" else m["odds_b"]
                bet["last_seen"] = market["observed_at"]
            continue
        if not (MIN_LEAD <= start - now <= MAX_LEAD):
            continue
        for c in candidates(p_a, m["odds_a"], m["odds_b"], plan):
            by_day.setdefault(lisbon_day(m["start_at"]), []).append({**c, "match": m})
    for day, picks in by_day.items():
        today = [b for b in ledger if lisbon_day(b["start_at"]) == day]
        lost = -sum(b["pnl"] for b in today if b.get("pnl", 0) < 0)
        sized = stakes(picks, state["bank"], state["peak"], plan, lost_today=lost,
                       staked_today=sum(b["stake"] for b in today), picks_today=len(today))
        for s in sized:
            m = s["match"]
            bet = {"match_id": m["id"], "created_at": now.isoformat(), "start_at": m["start_at"],
                   "tour": m["tour"], "competition": m["competition"], "player_a": m["player_a"],
                   "player_b": m["player_b"], "side": s["side"],
                   "pick": m["player_a"] if s["side"] == "a" else m["player_b"],
                   "odds": s["odds"], "p": round(s["p"], 4), "ev": round(s["ev"], 4),
                   "stake": s["stake"], "stake_pct": round(s["stake"] / state["bank"], 4),
                   "bank_at_pick": state["bank"], "url": m["url"], "status": "pendente",
                   "last_odds": s["odds"], "last_seen": market["observed_at"]}
            ledger.append(bet)
            fresh.append(bet)
    return board, fresh


def summary(ledger: list[dict]) -> dict:
    done = [b for b in ledger if b["status"] in ("ganha", "perdida")]
    staked = sum(b["stake"] for b in done)
    pnl = sum(b["pnl"] for b in done)
    clv = [b["odds"] / b["last_odds"] - 1 for b in ledger if b.get("last_odds")]
    return {"bets": len(done), "won": sum(b["status"] == "ganha" for b in done),
            "staked": round(staked, 2), "pnl": round(pnl, 2),
            "roi": round(pnl / staked, 4) if staked else None,
            "pending": sum(b["status"] == "pendente" for b in ledger),
            "avg_clv": round(sum(clv) / len(clv), 4) if clv else None}


def main() -> None:
    plan, report = load_plan()
    now = datetime.now(timezone.utc)
    ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else []
    settled = settle(ledger, now)
    try:
        market = betclic.fetch()
    except httpx.HTTPError as exc:
        print(f"Betclic indisponível: {exc}")
        market = {"observed_at": now.isoformat(), "competitions": 0, "matches": [], "error": str(exc)[:200]}
    board, fresh = place(ledger, market, plan, now)
    write_json(LEDGER, ledger)
    state = bank_state(ledger)
    board.sort(key=lambda r: r["start_at"])
    payload = {
        "generated_at": now.isoformat(), "observed_at": market["observed_at"],
        "betclic_ok": bool(market["matches"]), "start_bank": START_BANK,
        "plan": plan.as_dict(), "bank": state, "summary": summary(ledger),
        "bets": sorted(ledger, key=lambda b: b["start_at"], reverse=True),
        "board": [{k: r[k] for k in ("id", "tour", "competition", "start_at", "player_a", "player_b",
                                     "odds_a", "odds_b", "p_a", "picked", "url")} for r in board],
        "backtest": {k: report.get(k) for k in ("test_flat", "test_flat_by_year", "simulation_betclic",
                                                "baseline_all_favourites_betclic", "betclic_overround",
                                                "test_years", "fit_years")},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(f"Betclic: {len(market['matches'])} jogos; novas apostas: {len(fresh)}; liquidadas: {settled}; "
          f"banca {state['bank']} €")


if __name__ == "__main__":
    main()
