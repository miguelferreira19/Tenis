"""Causal opponent residuals, multiscale form and matchup geometry.

These are testable hypotheses, not claims of globally novel algorithms.
"""
from collections import defaultdict, deque
from math import log1p

import numpy as np

from .innovation import hold_probability, sigmoid

NAMES = ("first_serve_quality", "second_serve_quality", "ace_error_balance",
         "break_pressure_residual", "break_exposure", "common_opponent_residual",
         "head_to_head_residual", "innovation_short_long", "point_workload_14d",
         "style_wedge")
BLOCKS = {"service_detail": (0, 1, 2), "pressure": (3, 4), "network": (5, 6),
          "multiscale": (7, 8), "style": (9,), "all_dynamics": tuple(range(10))}


def dynamics_features(rows):
    history = defaultdict(lambda: deque(maxlen=60))
    profile = defaultdict(lambda: deque(maxlen=30))
    extra = np.zeros((len(rows), len(NAMES)))
    coverage = {"common_opponent_matches": 0, "head_to_head_matches": 0,
                "valid_service_profiles": 0, "valid_pressure_profiles": 0}

    def recent(player, day, half_life):
        values = history[player]
        weights = [0.5 ** ((day - item[0]).days / half_life) for item in values]
        return sum(w * item[2] for w, item in zip(weights, values)) / (5 + sum(weights))

    def skills(player, day):
        observations = profile[player]
        # Rates have effective-count shrinkage; aggregate first/second serve
        # denominators separately instead of treating each match equally.
        priors = np.array([0.70, 0.50, 0.04, 0.0, 0.0])
        sums, counts = 300 * priors, np.full(5, 300.0)
        for old_day, rates, denominators in observations:
            weight = 0.5 ** ((day - old_day).days / 180)
            sums += weight * rates * denominators
            counts += weight * denominators
        return sums / counts

    i = 0
    while i < len(rows):
        r = rows[i]["row"]
        tour, day = r["tour"], r["event_date"]
        j = i
        while j < len(rows) and (rows[j]["row"]["tour"], rows[j]["row"]["event_date"]) == (tour, day):
            j += 1
        for k in range(i, j):
            r = rows[k]["row"]
            a, b = r["player_a_id"], r["player_b_id"]
            sa, sb = skills(a, day), skills(b, day)
            def by_opponent(player):
                groups = defaultdict(list)
                for old_day, opponent, residual, points in history[player]:
                    if (day - old_day).days <= 365:
                        groups[opponent].append(residual)
                return {opponent: np.mean(values) for opponent, values in groups.items()}
            ha, hb = by_opponent(a), by_opponent(b)
            common = ha.keys() & hb.keys()
            common_value = sum(ha[o] - hb[o] for o in common) / (len(common) + 8)
            direct = [v[2] for v in history[a] if v[1] == b and (day - v[0]).days <= 730]
            h2h = sum(direct) / (len(direct) + 8)
            coverage["common_opponent_matches"] += int(bool(common))
            coverage["head_to_head_matches"] += int(bool(direct))
            workload = lambda player: log1p(sum(v[3] for v in history[player] if 0 < (day-v[0]).days <= 14)) / 8
            # Antisymmetric wedge: unlike a rating difference, this can encode
            # intransitive style matchups while preserving player-swap symmetry.
            wedge = (sa[2] * (sb[1] - .5) - sb[2] * (sa[1] - .5)) * 20
            extra[k] = (*((sa-sb)[:5]), common_value, h2h,
                        (recent(a, day, 45)-recent(a, day, 180)) - (recent(b, day, 45)-recent(b, day, 180)),
                        workload(a)-workload(b), wedge)
        for k in range(i, j):
            r = rows[k]["row"]
            a, b = r["player_a_id"], r["player_b_id"]
            p = rows[k]["elo_probability"]
            y = rows[k]["y"]
            total = sum((r.get(key) or {}).get("svpt") or 0 for key in ("stats_a", "stats_b"))
            history[a].append((day, b, y-p, total))
            history[b].append((day, a, p-y, total))
            for player, stats in ((a, r.get("stats_a")), (b, r.get("stats_b"))):
                if not stats:
                    continue
                n, first, first_won, second_won = (stats.get(key) for key in ("svpt", "1stIn", "1stWon", "2ndWon"))
                if n is None or first is None or first_won is None or second_won is None:
                    continue
                if not (0 < first < n and 0 <= first_won <= first and 0 <= second_won <= n-first):
                    continue
                rates = np.array([first_won/first, second_won/(n-first), .04, 0., .40])
                denominators = np.array([min(first, 80), min(n-first, 80), 0., 0., 0.])
                ace, df = stats.get("ace"), stats.get("df")
                if ace is not None and df is not None and 0 <= ace <= n and 0 <= df <= n:
                    rates[2], denominators[2] = (ace-df)/n, min(n, 80)
                saved, faced, games = (stats.get(key) for key in ("bpSaved", "bpFaced", "SvGms"))
                if saved is not None and faced is not None and games and 0 <= saved <= faced:
                    serve = (first_won + second_won)/n
                    if faced:
                        rates[3], denominators[3] = saved/faced - serve, min(faced, 20)
                    rates[4], denominators[4] = (faced-saved)/games - (1-hold_probability(serve)), min(games, 20)
                    coverage["valid_pressure_profiles"] += 1
                profile[player].append((day, rates, denominators))
                coverage["valid_service_profiles"] += 1
        i = j
    return extra, coverage
