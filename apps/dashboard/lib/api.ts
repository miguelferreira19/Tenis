// Browser requests stay on the dashboard origin; Next proxies /api to Python.
// This also works when the dashboard is opened from another device on the LAN.
export const API = "";

// Published site (GitHub Pages): no Python server, the same answers are JSON files
// written by scripts/export_snapshot.py. Archive search and price scenarios stay local-only.
export const STATIC = process.env.NEXT_PUBLIC_STATIC === "1";
export const BASE = process.env.NEXT_PUBLIC_BASE_PATH || "";
const SNAPSHOT: Record<string, string> = {
  "/api/upcoming": "upcoming", "/api/recent": "recent", "/api/overview": "overview",
  "/api/models": "models", "/api/backtest/predictions": "backtest", "/api/data-sources": "data-sources",
};

export function apiUrl(path: string): string {
  if (!STATIC) return `${API}${path}`;
  const url = new URL(path, "http://snapshot");
  const day = url.searchParams.get("day");
  const file = url.pathname === "/api/daily" ? (day ? `daily/${day}` : "meta") : SNAPSHOT[url.pathname];
  if (!file) throw new Error("Indisponível no site publicado");
  return `${BASE}/data/${file}.json`;
}

export type Match = {
  id: string;
  tour: string;
  tournament: string;
  event_date: string;
  date_precision: string;
  round: string | null;
  surface: string | null;
  player_a: string;
  player_b: string;
  player_a_id: string;
  player_b_id: string;
  winner: string;
  score: string | null;
  rank_a: number | null;
  rank_b: number | null;
  probability_a: number | null;
  fair_odds_a: number | null;
  fair_odds_b: number | null;
  split: string | null;
  as_of: string | null;
  model_version: string | null;
  features: {vector: Record<string, number>; players: Record<string, number | null>} | null;
  quality: Record<string, number | string> | null;
  source_url: string;
  odds_history?: Array<{bookmaker: string; decimal_odds: number; observed_at: string; market: string; selection_id: string; source_ref: string}>;
  time_note?: string;
};

export type Metrics = {n: number; brier?: number; log_loss?: number; ece_10?: number; accuracy?: number};
export type Overview = {
  counts: {players: number; tournaments: number; matches: number; odds_snapshots: number; predictions: number};
  first_event_date: string | null;
  last_event_date: string | null;
  raw_files: number;
  selected_family: string | null;
  selected_version: string | null;
  validation: Metrics | null;
  test_oos: Metrics | null;
  betting_backtest: string;
  status: string;
};

export async function getJSON<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path), { cache: "no-store" });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json() as Promise<T>;
}

export function pct(value: number | null | undefined, digits = 1): string {
  return value == null ? "—" : `${(value * 100).toFixed(digits)}%`;
}

export function decimal(value: number | null | undefined, digits = 2): string {
  return value == null ? "—" : value.toFixed(digits);
}

export function day(value: string | null | undefined): string {
  return value ? new Intl.DateTimeFormat("pt-PT", {day: "2-digit", month: "short", year: "numeric", timeZone: "UTC"}).format(new Date(`${value.slice(0, 10)}T12:00:00Z`)) : "—";
}

