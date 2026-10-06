"""Piloto automático: lê a Betclic, monta as múltiplas do plano, gere a banca e fecha resultados.

Corre no PC (a Betclic bloqueia os IPs do GitHub) e, só em leitura, no GitHub Actions. Escreve:
- artifacts/ledger.json — livro permanente das múltiplas (congeladas ao criar); uma simples é uma múltipla de 1 perna;
- apps/dashboard/public/data/autopilot.json — o que o site mostra, mais cópias do backtest e do registo real.
Nunca coloca apostas: só diz quais e quanto. Banca em papel, 100 € de partida.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from math import prod
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from tennis_quant import betclic
from tennis_quant.espn_fixtures import API as ESPN_API, parse_results
from tennis_quant.live_odds import _normal
from tennis_quant.research_io import write_json
from tennis_quant.strategy import ParlayPlan, candidates, parlays, probability, stakes

LISBON = ZoneInfo("Europe/Lisbon")
LEDGER = ROOT / "artifacts" / "ledger.json"
SNAPSHOT = ROOT / "artifacts" / "betclic_snapshot.json"
SNAPSHOT_MAX_AGE = timedelta(hours=6)
STRATEGY = ROOT / "artifacts" / "parlay_strategy.json"
PUBLISHED = ("parlay_strategy", "real_bets")  # artefactos copiados para o site
DATA = ROOT / "apps" / "dashboard" / "public" / "data"
OUT = DATA / "autopilot.json"
START_BANK = 100.0
MIN_LEAD, MAX_LEAD = timedelta(minutes=20), timedelta(hours=30)
VOID_AFTER = timedelta(days=3)
LEG_FIELDS = ("match_id", "tour", "competition", "player_a", "player_b", "side", "pick", "odds", "p", "start_at",
              "url", "last_odds", "last_seen", "score")


def load_plan() -> tuple[ParlayPlan, dict]:
    report = json.loads(STRATEGY.read_text(encoding="utf-8")) if STRATEGY.exists() else {}
    return ParlayPlan(**report.get("plan", {})), report


def as_parlay(bet: dict) -> dict:
    """Ledger rows from the single-bet era become parlays of one leg."""
    if "legs" in bet:
        return bet
    head = {k: v for k, v in bet.items() if k not in LEG_FIELDS and k != "match_id"}
    return {"id": f"s:{bet['match_id']}", **head, "start_at": bet["start_at"], "odds": bet["odds"], "p": bet["p"],
            "legs": [{**{k: bet[k] for k in LEG_FIELDS if k in bet}, "status": bet["status"]}]}


def load_ledger() -> list[dict]:
    return [as_parlay(b) for b in json.loads(LEDGER.read_text(encoding="utf-8"))] if LEDGER.exists() else []


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
                          headers={"User-Agent": "TennisQuant/0.5 (personal research)"})
            r.raise_for_status()
            boards.append(r.json())
        out += parse_results(boards, day, now)
    return out


def close(bet: dict, now: datetime) -> bool:
    """A parlay is lost as soon as one leg is; it pays when every leg is settled and none lost (voids drop out)."""
    states = [leg["status"] for leg in bet["legs"]]
    if "perdida" in states:
        status, pnl = "perdida", -bet["stake"]
    elif "pendente" in states:
        return False
    else:
        won = [leg["odds"] for leg in bet["legs"] if leg["status"] == "ganha"]
        status, pnl = ("ganha", round(bet["stake"] * (round(prod(won), 2) - 1), 2)) if won else ("anulada", 0.0)
    bet.update(status=status, pnl=pnl, settled_at=now.isoformat())
    return True


def settle(ledger: list[dict], now: datetime) -> int:
    due = [leg for b in ledger if b["status"] == "pendente" for leg in b["legs"]
           if leg["status"] == "pendente" and datetime.fromisoformat(leg["start_at"]) < now]
    if due:
        days = {datetime.fromisoformat(leg["start_at"]).date() + timedelta(days=k) for leg in due for k in (-1, 0, 1)}
        try:
            results = espn_results({d for d in days if d <= now.date()})
        except httpx.HTTPError as exc:
            print(f"ESPN indisponível, liquidação adiada: {exc}")
            results = []
        by_names = {names_key(r["player_a"], r["player_b"]): r for r in results}
        by_surnames = {surnames_key(r["player_a"], r["player_b"]): r for r in results}
        for leg in due:
            start = datetime.fromisoformat(leg["start_at"])
            r = by_names.get(names_key(leg["player_a"], leg["player_b"])) or \
                by_surnames.get(surnames_key(leg["player_a"], leg["player_b"]))
            if r and abs(r["start_at"] - start) < timedelta(hours=36):
                pick_name = leg["player_a"] if leg["side"] == "a" else leg["player_b"]
                won = _normal(r["winner"]).split()[-1] == _normal(pick_name).split()[-1]
                # ponytail: retirements settle on the player who advances (ESPN winner); check Betclic rules if it matters.
                leg.update(status="ganha" if won else "perdida", score=r["score"])
            elif now - start > VOID_AFTER:
                leg["status"] = "anulada"
    return sum(close(b, now) for b in ledger if b["status"] == "pendente")


def bank_state(ledger: list[dict]) -> dict:
    bank, peak, curve = START_BANK, START_BANK, []
    for bet in sorted((b for b in ledger if b["status"] in ("ganha", "perdida", "anulada")),
                      key=lambda b: b["settled_at"]):
        bank += bet["pnl"]
        peak = max(peak, bank)
        curve.append([bet["settled_at"][:10], round(bank, 2)])
    return {"bank": round(bank, 2), "peak": round(peak, 2), "curve": curve}


def new_parlay(sized: dict, bank: float, now: datetime, observed: str) -> dict:
    legs = []
    for pick in sized["legs"]:
        m = pick["match"]
        legs.append({"match_id": m["id"], "tour": m["tour"], "competition": m["competition"],
                     "player_a": m["player_a"], "player_b": m["player_b"], "side": pick["side"],
                     "pick": m["player_a"] if pick["side"] == "a" else m["player_b"],
                     "odds": pick["odds"], "p": round(pick["p"], 4), "start_at": m["start_at"], "url": m["url"],
                     "status": "pendente", "last_odds": pick["odds"], "last_seen": observed})
    return {"id": "p:" + "|".join(sorted(leg["match_id"] for leg in legs)), "created_at": now.isoformat(),
            "start_at": min(leg["start_at"] for leg in legs), "legs": legs, "odds": round(sized["odds"], 2),
            "p": round(sized["p"], 4), "ev": round(sized["ev"], 4), "stake": sized["stake"],
            "stake_pct": round(sized["stake"] / bank, 4), "bank_at_pick": bank, "status": "pendente"}


def place(ledger: list[dict], market: dict, plan: ParlayPlan, now: datetime,
          allow_new: bool = True) -> tuple[list[dict], list[dict]]:
    in_ledger = {leg["match_id"]: leg for b in ledger for leg in b["legs"]}
    state = bank_state(ledger)
    board, fresh = [], []
    by_day: dict[str, list[dict]] = {}
    for m in market["matches"]:
        start = datetime.fromisoformat(m["start_at"])
        p_a = probability(m["odds_a"], m["odds_b"], plan)
        board.append({**m, "p_a": round(p_a, 4), "picked": m["id"] in in_ledger})
        if m["id"] in in_ledger:
            leg = in_ledger[m["id"]]
            if leg["status"] == "pendente" and start > now:
                leg["last_odds"] = m["odds_a"] if leg["side"] == "a" else m["odds_b"]
                leg["last_seen"] = market["observed_at"]
            continue
        if not allow_new or not (MIN_LEAD <= start - now <= MAX_LEAD):
            continue
        for c in candidates(p_a, m["odds_a"], m["odds_b"], plan):
            by_day.setdefault(lisbon_day(m["start_at"]), []).append({**c, "match": m})
    for day, picks in by_day.items():
        today = [b for b in ledger if lisbon_day(b["start_at"]) == day]
        lost = -sum(b["pnl"] for b in today if b.get("pnl", 0) < 0)
        for sized in stakes(parlays(picks, plan), state["bank"], state["peak"], plan, lost_today=lost,
                            staked_today=sum(b["stake"] for b in today), picks_today=len(today)):
            bet = new_parlay(sized, state["bank"], now, market["observed_at"])
            ledger.append(bet)
            fresh.append(bet)
    return board, fresh


def summary(ledger: list[dict]) -> dict:
    done = [b for b in ledger if b["status"] in ("ganha", "perdida")]
    staked = sum(b["stake"] for b in done)
    pnl = sum(b["pnl"] for b in done)
    clv = [prod(leg["odds"] / leg["last_odds"] for leg in b["legs"]) - 1
           for b in ledger if all(leg.get("last_odds") for leg in b["legs"])]
    return {"bets": len(done), "won": sum(b["status"] == "ganha" for b in done),
            "staked": round(staked, 2), "pnl": round(pnl, 2),
            "roi": round(pnl / staked, 4) if staked else None,
            "pending": sum(b["status"] == "pendente" for b in ledger),
            "avg_clv": round(sum(clv) / len(clv), 4) if clv else None}


def read_market(now: datetime) -> tuple[dict, bool]:
    """Live Betclic read; if blocked (GitHub IPs), fall back to the PC's recent snapshot."""
    try:
        market = betclic.fetch()
    except httpx.HTTPError as exc:
        market = {"observed_at": now.isoformat(), "competitions": 0, "matches": [], "error": str(exc)[:200]}
    if market["matches"]:
        write_json(SNAPSHOT, market)
        return market, True
    print(f"Betclic sem jogos nesta leitura: {market.get('error', 'resposta vazia')}")
    if SNAPSHOT.exists():
        snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        if now - datetime.fromisoformat(snap["observed_at"]) <= SNAPSHOT_MAX_AGE:
            return snap, False
    return market, False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true",
                        help="não cria apostas nem grava o livro (uso no GitHub Actions)")
    args = parser.parse_args()
    plan, report = load_plan()
    now = datetime.now(timezone.utc)
    ledger = load_ledger()
    settled = settle(ledger, now)
    market, live = read_market(now)
    board, fresh = place(ledger, market, plan, now, allow_new=live and not args.read_only)
    if not args.read_only:
        write_json(LEDGER, ledger)
    state = bank_state(ledger)
    board.sort(key=lambda r: r["start_at"])
    payload = {
        "generated_at": now.isoformat(), "observed_at": market["observed_at"],
        "betclic_ok": bool(market["matches"]),
        "betclic_live_read": live, "start_bank": START_BANK,
        "plan": plan.as_dict(), "bank": state, "summary": summary(ledger),
        "bets": sorted(ledger, key=lambda b: b["start_at"], reverse=True),
        "board": [{k: r[k] for k in ("id", "tour", "competition", "start_at", "player_a", "player_b",
                                     "odds_a", "odds_b", "p_a", "picked", "url")} for r in board],
    }
    DATA.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    for name in PUBLISHED:
        if (ROOT / "artifacts" / f"{name}.json").exists():
            shutil.copyfile(ROOT / "artifacts" / f"{name}.json", DATA / f"{name}.json")
    print(f"Betclic: {len(market['matches'])} jogos; novas múltiplas: {len(fresh)}; liquidadas: {settled}; "
          f"banca {state['bank']} €")


if __name__ == "__main__":
    main()
