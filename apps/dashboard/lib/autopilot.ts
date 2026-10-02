import { useEffect, useState } from "react";
import { BASE } from "./api";

export type Bet = {
  match_id: string; created_at: string; start_at: string; tour: string; competition: string;
  player_a: string; player_b: string; side: "a" | "b"; pick: string; odds: number; p: number; ev: number;
  stake: number; stake_pct: number; bank_at_pick: number; url: string;
  status: "pendente" | "ganha" | "perdida" | "anulada"; pnl?: number; score?: string;
  settled_at?: string; last_odds?: number; last_seen?: string;
};
export type BoardRow = {
  id: string; tour: string; competition: string; start_at: string; player_a: string; player_b: string;
  odds_a: number; odds_b: number; p_a: number; picked: boolean; url: string;
};
export type FlatResult = { bets: number; hit_rate: number | null; roi: number | null; roi_se: number | null; avg_prob: number | null };
export type Autopilot = {
  generated_at: string; observed_at: string; betclic_ok: boolean; start_bank: number;
  plan: Record<string, number>;
  bank: { bank: number; peak: number; curve: [string, number][] };
  summary: { bets: number; won: number; staked: number; pnl: number; roi: number | null; pending: number; avg_clv: number | null };
  bets: Bet[]; board: BoardRow[];
  backtest: {
    test_flat?: Record<string, FlatResult>; test_flat_by_year?: Record<string, FlatResult>;
    simulation_betclic?: { start: number; end: number; bets: number; max_drawdown: number; return: number; curve_weekly: [string, number][] };
    baseline_all_favourites_betclic?: FlatResult; betclic_overround?: number; test_years?: number[]; fit_years?: number[];
  };
};

export async function loadAutopilot(): Promise<Autopilot> {
  const response = await fetch(`${BASE}/data/autopilot.json`, { cache: "no-store" });
  if (!response.ok) throw new Error("O piloto automático ainda não publicou dados.");
  return response.json();
}

export const eur = (v: number | null | undefined) =>
  v == null || !Number.isFinite(v) ? "—" : `${v.toLocaleString("pt-PT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
export const pc = (v: number | null | undefined, d = 0) =>
  v == null || !Number.isFinite(v) ? "—" : `${(v * 100).toLocaleString("pt-PT", { minimumFractionDigits: d, maximumFractionDigits: d })}%`;
export const odd = (v: number) => v.toLocaleString("pt-PT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function when(iso: string, now: number): string {
  const t = new Date(iso).getTime();
  const time = new Date(iso).toLocaleString("pt-PT", { timeZone: "Europe/Lisbon", weekday: "short", hour: "2-digit", minute: "2-digit" });
  const mins = Math.round((t - now) / 60000);
  if (mins < 0) return time;
  return mins < 60 ? `${time} · daqui a ${mins} min` : `${time} · daqui a ${Math.round(mins / 60)} h`;
}

/** Local per-device state: user's bankroll and which bets they already placed. */
export function useLocal<T>(key: string, initial: T): [T, (v: T) => void] {
  // localStorage may throw in private mode: the page still works without it.
  const [value, setValue] = useState<T>(initial);
  useEffect(() => {
    try { const raw = localStorage.getItem(key); if (raw) setValue(JSON.parse(raw)); } catch { /* sem armazenamento */ }
  }, [key]);
  const set = (v: T) => { setValue(v); try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* idem */ } };
  return [value, set];
}
