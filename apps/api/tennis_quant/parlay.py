"""Price combinatorial tickets without asserting bookmaker acceptance."""
from __future__ import annotations

from itertools import combinations
from datetime import datetime, timedelta, timezone
from math import prod


def calculate_ticket(legs: list[dict], kind: str, total_stake: float = 10,
                     system_size: int | None = None) -> dict:
    if not 1 <= len(legs) <= 8:
        raise ValueError("O bilhete aceita entre 1 e 8 seleções")
    if not 0 < total_stake <= 100_000:
        raise ValueError("Montante inválido")
    if any(not 1 < float(leg["decimal_odds"]) <= 1000 for leg in legs):
        raise ValueError("Odds decimais inválidas")
    if len({leg["fixture_id"] for leg in legs if leg.get("fixture_id")}) != len(
            [leg for leg in legs if leg.get("fixture_id")]):
        raise ValueError("Não é possível combinar seleções do mesmo jogo sem preço conjunto da casa")
    n = len(legs)
    if kind == "single":
        if n != 1:
            raise ValueError("Aposta simples exige uma seleção")
        sizes = [1]
    elif kind == "accumulator":
        if n < 2:
            raise ValueError("Combinada exige duas ou mais seleções")
        sizes = [n]
    elif kind == "system":
        if system_size is None or not 2 <= system_size <= n:
            raise ValueError("Escolhe um sistema k/N com 2 ≤ k ≤ N")
        sizes = [system_size]
    elif kind == "round_robin":
        if n < 3:
            raise ValueError("Round robin exige pelo menos três seleções")
        sizes = list(range(2, n + 1))
    else:
        raise ValueError("Tipo de bilhete desconhecido")
    line_indices = [combo for size in sizes for combo in combinations(range(n), size)]
    stake_line = total_stake / len(line_indices)
    lines = [{"indices": list(indices),
              "decimal_odds": round(prod(float(legs[i]["decimal_odds"]) for i in indices), 4),
              "stake": round(stake_line, 4)} for indices in line_indices]
    # Manual legs, cross-book mixes and accepted provider quotes have different
    # execution guarantees. Never report the ticket as executable.
    books = {leg.get("bookmaker") for leg in legs}
    comparable_book = len(books) == 1 and None not in books and "" not in books
    now = datetime.now(timezone.utc)
    observed_provider_prices = all(
        leg.get("source") == "provider"
        and isinstance(leg.get("observed_at"), datetime)
        and isinstance(leg.get("start_at"), datetime)
        and leg["observed_at"].tzinfo is not None
        and leg["start_at"].tzinfo is not None
        and timedelta(0) <= now - leg["observed_at"] <= timedelta(hours=6)
        and leg["observed_at"] < leg["start_at"]
        and leg["start_at"] > now
        for leg in legs)
    return {"kind": kind, "line_count": len(lines), "lines": lines,
            "total_stake": total_stake,
            "max_gross_return": round(sum(stake_line * line["decimal_odds"] for line in lines), 2),
            "max_net_profit": round(sum(stake_line * line["decimal_odds"] for line in lines) - total_stake, 2),
            "same_bookmaker": comparable_book,
            "provider_prices": observed_provider_prices,
            "status": "indicative_quote_not_accepted",
            "note": "Preço teórico. A casa pode não aceitar a combinada ou aplicar regras e preços próprios."
            if comparable_book and observed_provider_prices else
            "Cenário matemático: há odds manuais ou seleções sem uma casa comum verificável."}
