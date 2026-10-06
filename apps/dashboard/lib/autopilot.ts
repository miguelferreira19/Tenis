import { useEffect, useState } from "react";
import { BASE } from "./api";
import type { Model } from "./projection";

export type Status = "pendente" | "ganha" | "perdida" | "anulada";
export type Leg = {
  match_id: string; tour: string; competition: string; player_a: string; player_b: string; side: "a" | "b";
  pick: string; odds: number; p: number; start_at: string; url: string; status: Status;
  score?: string; last_odds?: number; last_seen?: string;
};
// Uma aposta simples é uma múltipla de uma perna.
export type Parlay = {
  id: string; created_at: string; start_at: string; legs: Leg[]; odds: number; p: number; ev: number;
  stake: number; stake_pct: number; bank_at_pick: number; status: Status; pnl?: number; settled_at?: string;
};
export type BoardRow = {
  id: string; tour: string; competition: string; start_at: string; player_a: string; player_b: string;
  odds_a: number; odds_b: number; p_a: number; picked: boolean; url: string;
};
export type Plan = {
  unit: number; day_cap: number; stop_day: number; max_picks_day: number; legs_max: number; odds_lo: number; odds_hi: number;
  odds_max: number; p_min: number; dd_soft: number; dd_hard: number; dd_floor: number;
};
export type Autopilot = {
  generated_at: string; observed_at: string; betclic_ok: boolean; start_bank: number; plan: Plan;
  bank: { bank: number; peak: number; curve: [string, number][] };
  summary: { bets: number; won: number; staked: number; pnl: number; roi: number | null; pending: number; avg_clv: number | null };
  bets: Parlay[]; board: BoardRow[];
};

export type Bucket = { odds_lo: number; odds_hi: number; bets: number; hit_rate: number; avg_p: number; roi: number; roi_se: number };
export type Summary = {
  parlays: number; hit_rate: number; avg_odds: number; avg_p: number; roi: number; roi_se: number; ev_model: number;
  legs_mix: Record<string, number>;
};
export type Strategy = Model & {
  betclic_overround: number; margin_measured: { date: string; matches: number; overround: number }[];
  plan: Plan; fit_years: number[]; test_years: number[];
  policy: { fit: Summary; test: Summary; all: Summary; by_year: Record<string, Summary> };
  by_legs: { legs: number; fit: Summary; test: Summary; all: Summary }[]; by_legs_band: [number, number];
  leg_curve: Bucket[];
};

export type RealLeg = { pick: string; vs: string | null; sport: string; odds: number; start_at: string; outcome: "ganha" | "perdida" };
export type RealBet = {
  placed_at: string; legs: RealLeg[]; odds: number | null; stake_pct: number; result: "ganha" | "perdida"; index: number; note?: string;
};
export type Real = {
  source: string; note: string; start: string;
  before: { from: string; to: string; bets: number; wins: number; note: string }; bets: RealBet[];
};

async function load<T>(name: string, missing: string): Promise<T> {
  const response = await fetch(`${BASE}/data/${name}.json`, { cache: "no-store" });
  if (!response.ok) throw new Error(missing);
  return response.json();
}
export const loadAutopilot = () => load<Autopilot>("autopilot", "O piloto automático ainda não publicou dados.");
export const loadStrategy = () => load<Strategy>("parlay_strategy", "O backtest das múltiplas ainda não foi publicado.");
export const loadReal = () => load<Real>("real_bets", "O registo das apostas reais ainda não foi publicado.");

export function useData<T>(loader: () => Promise<T>): { data: T | null; error: string } {
  const [state, setState] = useState<{ data: T | null; error: string }>({ data: null, error: "" });
  useEffect(() => {
    loader().then(data => setState({ data, error: "" })).catch(e => setState({ data: null, error: e instanceof Error ? e.message : "Erro ao carregar." }));
  }, [loader]);
  return state;
}

export const eur = (v: number | null | undefined) =>
  v == null || !Number.isFinite(v) ? "—" : `${v.toLocaleString("pt-PT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
export const signed = (v: number) => `${v >= 0 ? "+" : "−"}${eur(Math.abs(v))}`;
export const pc = (v: number | null | undefined, d = 0) =>
  v == null || !Number.isFinite(v) ? "—" : `${(v * 100).toLocaleString("pt-PT", { minimumFractionDigits: d, maximumFractionDigits: d })}%`;
export const spc = (v: number, d = 1) => `${v >= 0 ? "+" : "−"}${pc(Math.abs(v), d)}`;
export const odd = (v: number) => v.toLocaleString("pt-PT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function when(iso: string, now: number): string {
  const t = new Date(iso).getTime();
  const time = new Date(iso).toLocaleString("pt-PT", { timeZone: "Europe/Lisbon", weekday: "short", hour: "2-digit", minute: "2-digit" });
  const mins = Math.round((t - now) / 60000);
  if (mins < 0) return time;
  return mins < 60 ? `${time} · daqui a ${mins} min` : `${time} · daqui a ${Math.round(mins / 60)} h`;
}

export const median = (values: number[]): number => {
  const v = [...values].sort((a, b) => a - b), h = v.length / 2;
  return v.length ? (v.length % 2 ? v[Math.floor(h)] : (v[h - 1] + v[h]) / 2) : NaN;
};

/** How often favourites at these odds won in 2019–2026 (outside the table: the price less a 7% margin). */
export function hitRate(odds: number, curve: Bucket[]): number {
  const bucket = curve.find(b => odds >= b.odds_lo && odds < b.odds_hi);
  return bucket ? bucket.hit_rate : Math.min(0.99, 0.93 / odds);
}

/** Local per-device state: the user's bankroll, stake fraction and which bets they already placed. */
export function useLocal<T>(key: string, initial: T): [T, (v: T) => void] {
  // localStorage may throw in private mode: the page still works without it.
  const [value, setValue] = useState<T>(initial);
  useEffect(() => {
    try { const raw = localStorage.getItem(key); if (raw) setValue(JSON.parse(raw)); } catch { /* sem armazenamento */ }
  }, [key]);
  const set = (v: T) => { setValue(v); try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* idem */ } };
  return [value, set];
}
