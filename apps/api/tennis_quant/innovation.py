"""Research-only causal ratings; operational v4 features stay versioned separately."""
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from math import comb, exp, log, pi, sqrt
import re

import numpy as np

NAMES = ("dynamic_skill", "uncertainty_asymmetry", "adjusted_serve",
         "adjusted_return", "surface_adjusted_serve", "surface_adjusted_return",
         "margin_skill", "mechanistic_logit")


def sigmoid(x):
    return 1 / (1 + exp(-max(-30, min(30, x))))


def logit(p):
    p = max(1e-6, min(1 - 1e-6, p))
    return log(p / (1 - p))


def hold_probability(p):
    return p ** 4 * (1 + 4 * (1 - p) + 10 * (1 - p) ** 2) + \
        20 * p ** 3 * (1 - p) ** 3 * p ** 2 / (p ** 2 + (1 - p) ** 2)


def match_probability(pa, pb, best_of=3):
    """iid point model, standard 6-all tiebreak; average first server per set.

    ponytail: historical deciding-set rules and server carry between sets are
    approximated; use a rule-specific state chain for score-market forecasting.
    """
    if not 0 < pa < 1 or not 0 < pb < 1 or best_of not in (3, 5):
        raise ValueError("Probabilidades ou formato inválidos")

    def set_win(first):
        @lru_cache(None)
        def tb(a, b):
            if max(a, b) >= 7 and abs(a - b) >= 2:
                return float(a > b)
            if a == b == 6:
                return pa * (1 - pb) / (pa * (1 - pb) + (1 - pa) * pb)
            n = a + b
            server = first if n == 0 else (first + ((n + 1) // 2) % 2) % 2
            q = pa if server == 0 else 1 - pb
            return q * tb(a + 1, b) + (1 - q) * tb(a, b + 1)

        @lru_cache(None)
        def games(a, b):
            if max(a, b) >= 6 and abs(a - b) >= 2:
                return float(a > b)
            if a == b == 6:
                return tb(0, 0)
            server = (first + a + b) % 2
            q = hold_probability(pa) if server == 0 else 1 - hold_probability(pb)
            return q * games(a + 1, b) + (1 - q) * games(a, b + 1)
        return games(0, 0)
    s = (set_win(0) + set_win(1)) / 2
    needed = best_of // 2 + 1
    return sum(comb(best_of, k) * s ** k * (1 - s) ** (best_of - k)
               for k in range(needed, best_of + 1))


@dataclass
class Rating:
    mean: float = 0.0
    variance: float = 1.0
    day: object = None

    def prior(self, day):
        gap = max(0, (day - self.day).days) if self.day else 0
        return min(2.0, self.variance + 0.002 * gap)


def game_share(score, a_won):
    # Sackmann scores are always winner first, including bracketed match TBs.
    # ponytail: use only sets up to 7 games, excluding ambiguous match TBs and
    # long advantage sets; a rule-aware score parser can recover those later.
    pairs = re.findall(r"(?<![\d\[])(\d+)-(\d+)(?![\d\]])", score or "")
    pairs = [(int(a), int(b)) for a, b in pairs if max(int(a), int(b)) <= 7]
    total = sum(a + b for a, b in pairs)
    if not total:
        return None
    winner = sum(a for a, _ in pairs) / total
    return winner if a_won else 1 - winner


def research_features(rows):
    """Read every feature in a tour/date block before any update in that block."""
    ratings = defaultdict(Rating)
    point = defaultdict(float)
    point_n = defaultdict(int)
    margins = defaultdict(float)
    extra = np.zeros((len(rows), len(NAMES)))
    coverage = {"service_observations": 0, "score_observations": 0}
    i = 0
    while i < len(rows):
        day, tour = rows[i]["row"]["event_date"], rows[i]["row"]["tour"]
        j = i
        while j < len(rows) and (rows[j]["row"]["event_date"], rows[j]["row"]["tour"]) == (day, tour):
            j += 1
        pending = []
        base = logit(0.64 if tour == "ATP" else 0.59)
        for k in range(i, j):
            row = rows[k]["row"]
            a, b = row["player_a_id"], row["player_b_id"]
            surface = row["surface"] or "Unknown"
            ra, rb = ratings[a], ratings[b]
            va, vb = ra.prior(day), rb.prior(day)
            p = sigmoid((ra.mean - rb.mean) / sqrt(1 + pi * (va + vb) / 8))

            def skill(player, kind):
                global_key, local_key = (player, "all", kind), (player, surface, kind)
                w = point_n[local_key] / (point_n[local_key] + 20)
                return (1 - w) * point[global_key] + w * point[local_key]

            sa, sb, da, db = skill(a, "serve"), skill(b, "serve"), skill(a, "return"), skill(b, "return")
            pa, pb = sigmoid(base + sa - db), sigmoid(base + sb - da)
            extra[k] = (logit(p), log(va / vb),
                        point[(a, "all", "serve")] - point[(b, "all", "serve")],
                        point[(a, "all", "return")] - point[(b, "all", "return")],
                        sa - sb, da - db, margins[a] - margins[b],
                        logit(match_probability(pa, pb, row.get("best_of") or 3)))
            # Batch Laplace innovations use the frozen pre-tournament prior.
            pending.append((a, b, va, vb, sigmoid(ra.mean - rb.mean), row, rows[k]["y"]))
        increments, information = defaultdict(float), defaultdict(float)
        point_increments = defaultdict(float)
        margin_increments = defaultdict(float)
        for a, b, va, vb, p, row, y in pending:
            for player, sign in ((a, 1), (b, -1)):
                increments[player] += sign * (y - p)
                information[player] += p * (1 - p)
            share = game_share(row.get("score"), bool(y))
            if share is not None:
                residual = share - sigmoid(margins[a] - margins[b])
                margin_increments[a] += 0.8 * residual
                margin_increments[b] -= 0.8 * residual
                coverage["score_observations"] += 1
            for server, returner, stats in ((a, b, row.get("stats_a")), (b, a, row.get("stats_b"))):
                if not stats:
                    continue
                n, first, second = (stats.get(key) for key in ("svpt", "1stWon", "2ndWon"))
                if not n or first is None or second is None or not 0 <= first + second <= n:
                    continue
                observed = (first + second) / n
                for scope in ("all", row["surface"] or "Unknown"):
                    ks, kr = (server, scope, "serve"), (returner, scope, "return")
                    expected = sigmoid(base + point[ks] - point[kr])
                    residual = observed - expected
                    # Cap effective point count: iid binomial SE would be overconfident.
                    step = 0.8 * min(n, 80) / 80
                    point_increments[ks] += step * residual
                    point_increments[kr] -= step * residual
                    point_n[ks] += 1
                    point_n[kr] += 1
                coverage["service_observations"] += 1
        for player, value in increments.items():
            rating = ratings[player]
            variance = 1 / (1 / rating.prior(day) + information[player])
            rating.mean += variance * value
            rating.variance, rating.day = variance, day
        for key, value in point_increments.items():
            point[key] = (point[key] + value) * 0.995
        for key, value in margin_increments.items():
            margins[key] = (margins[key] + value) * 0.995
        i = j
    return extra, coverage
