"""Public Betclic.pt tennis prices, read from the server-rendered page state.

Only the public "Vencedor do encontro" prices are read; no account data, no
login, no bet placement. A changed page layout yields zero matches (fail closed).
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone

import httpx

BASE = "https://www.betclic.pt"
SPORT = "/tenis-stennis"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/154 Safari/537.36",
           "Accept-Language": "pt-PT,pt;q=0.9"}
STATE = re.compile(r'<script id="ng-state" type="application/json">(.*?)</script>', re.S)


def slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")


def _state(client: httpx.Client, path: str) -> dict:
    response = client.get(BASE + path)
    response.raise_for_status()
    found = STATE.search(response.content.decode("utf-8", "replace"))
    return json.loads(found.group(1)) if found else {}


def _walk(node, key):
    if isinstance(node, dict):
        if key in node:
            yield node
        for value in node.values():
            yield from _walk(value, key)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value, key)


def competitions(state: dict) -> dict[str, str]:
    return {c["competitionId"]: c["competitionName"] for c in _walk(state, "competitionId")
            if c.get("sportCode") == "tennis"}


def circuit(name: str) -> str | None:
    """Betclic competition -> circuit we can settle with ESPN; None = skip."""
    n = slug(name)
    if "pares" in n or "duplas" in n or "mist" in n:
        return None
    if "wta" in n or n.endswith("-f"):
        return "WTA"
    if "challenger" in n or "itf" in n or "utr" in n:
        return None  # ATP Challengers/ITF: no free results feed to settle them
    if "atp" in n or n.endswith("-m"):
        return "ATP"
    return None


def parse(state: dict, competition_name: str, competition_id: str) -> list[dict]:
    out = {}
    for payload in _walk(state, "matches"):
        for m in payload.get("matches") or []:
            market = m.get("market") or {}
            sel = market.get("mainSelections") or []
            players = m.get("contestants") or []
            if len(sel) != 2 or len(players) != 2 or (m.get("competition") or {}).get("id") != competition_id:
                continue
            a, b = sel[0].get("name", ""), sel[1].get("name", "")
            if not a or not b or "/" in a or "/" in b:
                continue
            try:
                odds_a, odds_b = float(sel[0]["odds"]), float(sel[1]["odds"])
            except (KeyError, TypeError, ValueError):
                continue
            if odds_a <= 1 or odds_b <= 1 or sel[0].get("status") != 1 or sel[1].get("status") != 1:
                continue
            out[m["matchId"]] = {
                "id": f"betclic:{m['matchId']}", "competition": competition_name,
                "start_at": m["matchDateUtc"][:19] + "+00:00", "live": bool(m.get("isLive")),
                "player_a": a, "player_b": b, "odds_a": odds_a, "odds_b": odds_b,
                "url": f"{BASE}{SPORT}/{slug(competition_name)}-c{competition_id}/{slug(a)}-{slug(b)}-m{m['matchId']}",
            }
    return list(out.values())


def fetch() -> dict:
    """All pre-match singles prices for circuits we can settle."""
    observed = datetime.now(timezone.utc).isoformat()
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        comps = competitions(_state(client, SPORT))
        matches = []
        for cid, name in comps.items():
            tour = circuit(name)
            if not tour:
                continue
            for row in parse(_state(client, f"{SPORT}/{slug(name)}-c{cid}"), name, cid):
                if not row["live"]:
                    matches.append({**row, "tour": tour, "observed_at": observed})
    return {"observed_at": observed, "competitions": len(comps), "matches": matches}


if __name__ == "__main__":
    data = fetch()
    print(data["competitions"], len(data["matches"]))
    for m in data["matches"][:10]:
        print(m["start_at"], m["tour"], m["player_a"], m["odds_a"], "-", m["player_b"], m["odds_b"])
