"""Ronda 4: o modelo contra o mercado e modelos residuais sobre o mercado.

Pergunta: existe informação que as odds de fecho não incorporam? Protocolo fixado
antes de correr (02-10-2026):
- Referência: probabilidade sem margem (Shin) da média das casas (Avg).
- Origens móveis 2021–2026: treino em 2019..Y−1, teste em Y. Previsões do
  modelo são as fora-da-amostra já guardadas (iteration_predictions.npz).
- Configurações (todas registadas): mercado recalibrado; mercado+modelo;
  mercado+carga real de jogos; mercado+momento de surpresa; resíduo logístico e
  XGBoost com todas as variáveis; controlo com variáveis baralhadas.
- Apostas: só Bet365 (proxy de casa "soft" como a Betclic), stake fixo, limiares
  {0, 2, 4, 6, 8, 10}%. Seleção múltipla corrigida por DSR e PBO (CSCV).
Nenhum resultado aqui é promessa de lucro.
"""
from __future__ import annotations

import hashlib
import json
import sys
from itertools import combinations
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from tennis_quant import market as mk
from tennis_quant.research_io import write_json

TAUS = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10)
TEST_YEARS = range(2021, 2027)
SEED = 20261002


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def surprise_momentum(frame: pd.DataFrame, halflife: float) -> np.ndarray:
    """EWMA per player of (result − market probability), strictly before each match day."""
    alpha = 1 - 0.5 ** (1 / halflife)
    state: dict[str, float] = {}
    out = np.zeros(len(frame))
    order = frame.sort_values("match_date", kind="stable")
    for day, block in order.groupby("match_date", sort=True):
        for i in block.index:
            out[i] = state.get(frame.at[i, "pa_id"], 0.0) - state.get(frame.at[i, "pb_id"], 0.0)
        for i in block.index:
            r = frame.at[i, "y"] - frame.at[i, "pm"]
            for pid, sign in ((frame.at[i, "pa_id"], 1), (frame.at[i, "pb_id"], -1)):
                state[pid] = (1 - alpha) * state.get(pid, 0.0) + alpha * sign * r
    return out


def build() -> pd.DataFrame:
    joined = mk.join_archive()
    it = np.load(ROOT / "artifacts" / "iteration_predictions.npz", allow_pickle=True)
    en = np.load(ROOT / "artifacts" / "enrichment_predictions.npz", allow_pickle=True)
    inn = np.load(ROOT / "artifacts" / "innovation_predictions.npz", allow_pickle=True)
    preds = pd.DataFrame({"match_id": it["match_id"], "y": it["y"], "year": it["years"],
                          "p_cand": it["recency_730d"], "p_v4": en["v4"]})
    blocks = {"dyn": it["dynamics_matrix"], "meta": en["metadata_matrix"], "inn": inn["feature_matrix"]}
    for name, matrix in blocks.items():
        for k in range(matrix.shape[1]):
            preds[f"{name}{k}"] = matrix[:, k]
    archive = mk.archive_frame().set_index("id")
    d = preds.merge(joined, on="match_id")
    a_won = archive.loc[d.match_id, "winner_id"].values == archive.loc[d.match_id, "player_a_id"].values
    if not np.array_equal(a_won.astype(int), d.y.values):
        raise ValueError("Orientação vencedor/jogador A inconsistente")
    d["pa_id"] = archive.loc[d.match_id, "player_a_id"].values
    d["pb_id"] = archive.loc[d.match_id, "player_b_id"].values
    d["tournament_id"] = archive.loc[d.match_id, "tournament"].values + d.year.astype(str)

    def orient(w, l):
        return np.where(a_won, d[w], d[l]), np.where(a_won, d[l], d[w])
    for col in mk.PRICE_COLUMNS:
        d[f"{col}_a"], d[f"{col}_b"] = orient(f"{col}_w", f"{col}_l")
    for name in mk.SCHEDULE:
        d[f"a_{name}"], d[f"b_{name}"] = orient(f"w_{name}", f"l_{name}")
    d["rank_a"], d["rank_b"] = orient("w_rank", "l_rank")
    valid = ((d.B365_a > 1) & (d.B365_b > 1) & (d.Avg_a > 1) & (d.Avg_b > 1)
             & (d.comment == "Completed") & (d.year >= 2019))
    d = d[valid].reset_index(drop=True)
    d["pm"] = mk.shin(d.Avg_a.values, d.Avg_b.values)
    d["p365"] = mk.shin(d.B365_a.values, d.B365_b.values)
    d["mom5"] = surprise_momentum(d, 5)
    d["mom20"] = surprise_momentum(d, 20)
    return d


def feature_sets(d: pd.DataFrame) -> dict[str, np.ndarray]:
    sched = np.c_[(d.a_days_prev - d.b_days_prev) / 30, (d.a_games_prev - d.b_games_prev) / 30,
                  (d.a_sets_prev - d.b_sets_prev) / 3, (d.a_n_14d - d.b_n_14d) / 5,
                  (d.a_games_7d - d.b_games_7d) / 60]
    model = np.c_[logit(d.p_cand) - logit(d.pm), logit(d.p_v4) - logit(d.pm)]
    mom = np.c_[d.mom5, d.mom20]
    rank = lambda r: np.log(pd.to_numeric(r, errors="coerce").fillna(1000).clip(1, 2000).to_numpy(float))
    books = np.c_[logit(d.p365) - logit(d.pm), rank(d.rank_b) - rank(d.rank_a)]
    research = d[[c for c in d.columns if c[:3] in ("dyn", "met", "inn") and c[-1].isdigit()]].to_numpy(float)
    return {
        "market_recal": np.zeros((len(d), 0)),
        "market_model": model,
        "market_schedule": sched,
        "market_momentum": mom,
        "residual_logistic_all": np.c_[model, sched, mom, books],
        "residual_xgb_all": np.c_[model, sched, mom, books, research],
    }


def fit_predict(name: str, X: np.ndarray, base: np.ndarray, y: np.ndarray, train: np.ndarray, test: np.ndarray) -> np.ndarray:
    """Antisymmetric fit: augment with (−X, −base, 1−y); market logit enters as offset."""
    Xa = np.r_[X[train], -X[train]]
    ba = np.r_[base[train], -base[train]]
    ya = np.r_[y[train], 1 - y[train]]
    if name.startswith("residual_xgb"):
        model = XGBClassifier(n_estimators=150, max_depth=2, learning_rate=0.03, subsample=0.8,
                              colsample_bytree=0.8, reg_lambda=20, min_child_weight=50,
                              random_state=SEED, n_jobs=4, base_score=0.5)
        model.fit(Xa, ya, base_margin=ba)
        f = model.predict(X[test], output_margin=True, base_margin=base[test])
        r = model.predict(-X[test], output_margin=True, base_margin=-base[test])
        return sigmoid((f - r) / 2)
    # Logistic with market slope free (FLB recalibration) and L2 on the rest.
    Z = np.c_[ba, Xa]
    model = LogisticRegression(fit_intercept=False, C=0.5, max_iter=1000).fit(Z, ya)
    return sigmoid(np.c_[base[test], X[test]] @ model.coef_[0])


def bets(p: np.ndarray, d: pd.DataFrame, tau: float) -> pd.DataFrame:
    """At most one side per match at Bet365 closing price, stake 1."""
    ea, eb = p * d.B365_a - 1, (1 - p) * d.B365_b - 1
    pick_a = (ea > tau) & (ea >= eb)
    pick_b = (eb > tau) & ~pick_a
    pnl = np.where(pick_a, np.where(d.y == 1, d.B365_a - 1, -1.0), 0.0)
    pnl = np.where(pick_b, np.where(d.y == 0, d.B365_b - 1, -1.0), pnl)
    return pd.DataFrame({"bet": pick_a | pick_b, "pnl": pnl, "date": d.match_date,
                         "tournament": d.tournament_id})


def tournament_bootstrap(values: pd.DataFrame, column: str, reps: int = 2000) -> list[float]:
    rng = np.random.default_rng(SEED)
    groups = values.groupby("tournament")[column].agg(["sum", "count"])
    s, c = groups["sum"].to_numpy(), groups["count"].to_numpy()
    idx = rng.integers(0, len(s), size=(reps, len(s)))
    stats = s[idx].sum(1) / np.maximum(c[idx].sum(1), 1)
    return [round(float(np.quantile(stats, 0.025)), 6), round(float(np.quantile(stats, 0.975)), 6)]


def norm_cdf(x):
    return 0.5 * (1 + erf(x / sqrt(2)))


def deflated_sharpe(returns: np.ndarray, trials_sr: np.ndarray) -> float:
    """Bailey & López de Prado (2014): P(true SR > expected max SR of N trials)."""
    n = len(returns)
    if n < 30 or returns.std() == 0:
        return 0.0
    sr = returns.mean() / returns.std()
    skew = float(((returns - returns.mean()) ** 3).mean() / returns.std() ** 3)
    kurt = float(((returns - returns.mean()) ** 4).mean() / returns.std() ** 4)
    N, var = len(trials_sr), np.var(trials_sr)
    gamma = 0.5772156649
    from statistics import NormalDist
    z = NormalDist().inv_cdf
    sr0 = sqrt(var) * ((1 - gamma) * z(1 - 1 / N) + gamma * z(1 - 1 / (N * np.e))) if N > 1 else 0
    denom = sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr ** 2))
    return float(norm_cdf((sr - sr0) * sqrt(n - 1) / denom))


def pbo_cscv(matrix: np.ndarray, blocks: int = 10) -> float:
    """Probability of backtest overfitting via combinatorially symmetric CV (Bailey et al.)."""
    T, N = matrix.shape
    parts = np.array_split(np.arange(T), blocks)
    lambdas = []
    for train_ids in combinations(range(blocks), blocks // 2):
        tr = np.concatenate([parts[i] for i in train_ids])
        te = np.concatenate([parts[i] for i in range(blocks) if i not in train_ids])
        best = np.argmax(matrix[tr].mean(0))
        rank = (matrix[te].mean(0) < matrix[te, best].mean()).mean()
        rank = min(max(rank, 1 / (N + 1)), N / (N + 1))
        lambdas.append(np.log(rank / (1 - rank)))
    return float(np.mean(np.array(lambdas) <= 0))


def main():
    d = build()
    y = d.y.to_numpy()
    base = logit(d.pm)
    sets = feature_sets(d)
    rng = np.random.default_rng(SEED)
    shuffled = sets["residual_xgb_all"].copy()
    for year in np.unique(d.year):
        rows = np.where(d.year == year)[0]
        shuffled[rows] = shuffled[rng.permutation(rows)]
    sets["control_shuffled_xgb"] = shuffled
    test_mask = d.year.isin(TEST_YEARS).to_numpy()
    preds = {"market": d.pm.to_numpy().copy(), "model_cand": d.p_cand.to_numpy().copy()}
    for name, X in sets.items():
        p = np.full(len(d), np.nan)
        for year in TEST_YEARS:
            train, test = (d.year < year).to_numpy(), (d.year == year).to_numpy()
            p[test] = fit_predict(name.replace("control_shuffled_xgb", "residual_xgb"), X, base, y, train, test)
        preds[name] = p
    t = d[test_mask].reset_index(drop=True)
    yt = y[test_mask]
    results, strategies = {}, {}
    for name, p in preds.items():
        pt = np.clip(p[test_mask], 1e-6, 1 - 1e-6)
        ll = -(yt * np.log(pt) + (1 - yt) * np.log(1 - pt))
        pm = np.clip(t.pm.to_numpy(), 1e-6, 1 - 1e-6)
        ll_m = -(yt * np.log(pm) + (1 - yt) * np.log(1 - pm))
        gain = pd.DataFrame({"tournament": t.tournament_id, "g": ll_m - ll})
        yearly = {int(Y): {"n": int((t.year == Y).sum()),
                           "brier": round(float(np.mean((pt[t.year == Y] - yt[t.year == Y]) ** 2)), 6),
                           "log_loss": round(float(ll[t.year == Y].mean()), 6)} for Y in TEST_YEARS}
        betting = {}
        for tau in TAUS:
            b = bets(pt, t, tau)
            placed = b[b.bet]
            key = f"{name}@{tau:.2f}"
            strategies[key] = b
            betting[f"{tau:.2f}"] = {
                "bets": int(len(placed)),
                "roi": round(float(placed.pnl.mean()), 6) if len(placed) else None,
                "roi_ci95_tournament": tournament_bootstrap(placed.assign(one=1), "pnl") if len(placed) > 30 else None,
                "positive_years": int(sum(placed[placed.date.map(lambda x: x.year) == Y].pnl.sum() > 0 for Y in TEST_YEARS)),
            }
        results[name] = {
            "brier": round(float(np.mean((pt - yt) ** 2)), 6), "log_loss": round(float(ll.mean()), 6),
            "log_loss_gain_vs_market": round(float((ll_m - ll).mean()), 7),
            "gain_ci95_tournament": tournament_bootstrap(gain, "g"),
            "yearly": yearly, "betting_b365": betting,
        }
    # Multiple-testing: daily P&L matrix of every (config, tau) strategy.
    days = sorted(t.match_date.unique())
    matrix = np.stack([b.groupby("date").pnl.sum().reindex(days, fill_value=0).to_numpy()
                       for b in strategies.values()], axis=1)
    per_bet_sr = np.array([b[b.bet].pnl.mean() / b[b.bet].pnl.std() if b.bet.sum() > 30 else 0
                           for b in strategies.values()])
    best_key = max(strategies, key=lambda k: strategies[k][strategies[k].bet].pnl.mean()
                   if strategies[k].bet.sum() > 100 else -9)
    best = strategies[best_key]
    report = {
        "protocol": __doc__.strip(),
        "coverage": {"matches": int(len(d)), "test_matches": int(test_mask.sum()),
                     "test_years": list(TEST_YEARS)},
        "results": results,
        "multiple_testing": {
            "strategies_tested": len(strategies),
            "best_by_roi_min100": best_key,
            "best_roi": round(float(best[best.bet].pnl.mean()), 6),
            "best_bets": int(best.bet.sum()),
            "deflated_sharpe_probability": round(deflated_sharpe(best[best.bet].pnl.to_numpy(), per_bet_sr), 4),
            "pbo_cscv_10_blocks": round(pbo_cscv(matrix), 4),
        },
        "data_sha256": hashlib.sha256("".join(sorted(mk.load_odds()["source_sha256"].unique())).encode()).hexdigest(),
    }
    write_json(ROOT / "artifacts" / "market_research.json", report)
    np.savez_compressed(ROOT / "work" / "market_predictions.npz", match_id=d.match_id.to_numpy(),
                        **{k: v for k, v in preds.items()})
    for name, r in results.items():
        b = r["betting_b365"]
        print(f"{name:24s} brier {r['brier']:.6f} ll {r['log_loss']:.6f} gain {r['log_loss_gain_vs_market']:+.6f} "
              f"{r['gain_ci95_tournament']} | " + " ".join(f"{k}:{v['bets']}/{(v['roi'] or 0)*100:+.1f}%" for k, v in b.items()))
    print(json.dumps(report["multiple_testing"], indent=1))


if __name__ == "__main__":
    main()
