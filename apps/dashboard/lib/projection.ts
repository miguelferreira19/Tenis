// Simulação da banca com múltiplas curtas. Corre no browser sobre as múltiplas que o plano teria feito
// em cada dia de 2019–2026 (artifacts/parlay_strategy.json, odds de fecho com a margem real da Betclic).
// Sem imports: o Node corre os testes diretamente (node lib/projection.test.mjs).

export type DayParlay = [odds: number, p: number, won: number]; // won: 1 = a múltipla ganhou nesse dia
export type Model = {
  plan: { unit: number; day_cap: number; stop_day: number; max_picks_day: number; odds_lo: number; odds_hi: number };
  calendar: [string, string][]; // intervalos de dias cobertos (os dias sem múltiplas também contam)
  days: Record<string, DayParlay[]>;
};
export type Scenario = "base" | "justo" | "otimista";
// ev = valor esperado por euro apostado; null = repetir os resultados reais dos dias do histórico.
export const SCENARIOS: Record<Scenario, { label: string; ev: number | null }> = {
  base: { label: "Histórico real", ev: null },
  justo: { label: "Odds justas", ev: 0 },
  otimista: { label: "Vantagem de +3%", ev: 0.03 },
};
export type Options = {
  bank: number; frac: number; horizon: number; perDay: number; scenario: Scenario;
  start?: Date; paths?: number; seed?: number; dayCap?: number; stopDay?: number;
};
export type Fan = {
  p10: number[]; p50: number[]; p90: number[]; mean: number;
  profit: number; lose30: number; double: number; parlaysPerDay: number; stakedPerDay: number;
};

const DAY_MS = 86_400_000;
const MIN_STAKE = 0.1;

export function rng(seed: number): () => number { // mulberry32
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function doy(date: Date): number {
  return Math.floor((Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()) - Date.UTC(date.getUTCFullYear(), 0, 0)) / DAY_MS);
}

/** Days of the same time of year in the backtest (±window days), so October draws from past Octobers. */
export function seasonalPool(model: Model, window = 3): DayParlay[][][] {
  const byDoy: DayParlay[][][] = Array.from({ length: 367 }, () => []);
  for (const [from, to] of model.calendar) {
    for (let t = Date.parse(`${from}T00:00:00Z`); t <= Date.parse(`${to}T00:00:00Z`); t += DAY_MS) {
      const d = new Date(t);
      byDoy[doy(d)].push(model.days[d.toISOString().slice(0, 10)] ?? []);
    }
  }
  return byDoy.map((_, i) => {
    const out: DayParlay[][] = [];
    for (let k = -window; k <= window; k++) out.push(...byDoy[((i - 1 + k + 366 * 2) % 366) + 1]);
    return out;
  });
}

/** Simulates `paths` futures of the bankroll; stakes follow the plan: a fixed fraction, day cap, stop-loss. */
export function project(model: Model, o: Options): Fan {
  const paths = o.paths ?? 2000, rand = rng(o.seed ?? 20261006), start = o.start ?? new Date();
  const dayCap = o.dayCap ?? model.plan.day_cap, stopDay = o.stopDay ?? model.plan.stop_day;
  const pool = seasonalPool(model), ev = SCENARIOS[o.scenario].ev;
  const grid = Array.from({ length: o.horizon + 1 }, () => new Float64Array(paths));
  let parlays = 0, staked = 0;
  for (let i = 0; i < paths; i++) {
    let bank = o.bank;
    grid[0][i] = bank;
    for (let t = 1; t <= o.horizon; t++) {
      const days = pool[doy(new Date(start.getTime() + t * DAY_MS))];
      const today = days.length ? days[Math.floor(rand() * days.length)].slice(0, o.perDay) : [];
      const dayBank = bank;
      let lost = 0, spent = 0;
      for (const [odds, , won] of today) {
        if (lost >= stopDay * dayBank) break;
        const stake = Math.round(Math.min(o.frac * dayBank, dayCap * dayBank - spent) * 100) / 100;
        if (stake < MIN_STAKE) break;
        const win = ev === null ? won === 1 : rand() < Math.min(0.995, (1 + ev) / odds);
        bank += win ? stake * (Math.round(odds * 100) / 100 - 1) : -stake;
        if (!win) lost += stake;
        spent += stake; parlays++; staked += stake;
      }
      grid[t][i] = bank;
    }
  }
  const q = (sorted: Float64Array, f: number) => sorted[Math.min(paths - 1, Math.floor(f * paths))];
  const p10: number[] = [], p50: number[] = [], p90: number[] = [];
  for (const column of grid) {
    const sorted = Float64Array.from(column).sort();
    p10.push(q(sorted, 0.1)); p50.push(q(sorted, 0.5)); p90.push(q(sorted, 0.9));
  }
  const last = grid[o.horizon];
  const share = (test: (v: number) => boolean) => last.reduce((n, v) => n + (test(v) ? 1 : 0), 0) / paths;
  return {
    p10, p50, p90, mean: last.reduce((s, v) => s + v, 0) / paths,
    profit: share(v => v > o.bank), lose30: share(v => v < 0.7 * o.bank), double: share(v => v >= 2 * o.bank),
    parlaysPerDay: parlays / paths / o.horizon, stakedPerDay: staked / paths / o.horizon,
  };
}

/** P(at least k wins) for independent bets with win chances ps (Poisson-binomial). */
export function atLeast(ps: number[], k: number): number {
  let dist = [1];
  for (const p of ps) {
    const next = new Array(dist.length + 1).fill(0);
    dist.forEach((q, wins) => { next[wins] += q * (1 - p); next[wins + 1] += q * p; });
    dist = next;
  }
  return dist.slice(Math.max(k, 0)).reduce((s, q) => s + q, 0);
}

export const runProb = (ps: number[]): number => ps.reduce((a, p) => a * p, 1);

/** Number of bets to tell an edge `delta` (per euro staked) from zero: one-sided 5%, 80% power. */
export function betsToConfirm(delta: number, odds: number, p: number): number {
  const sd = odds * Math.sqrt(p * (1 - p));
  return Math.ceil(((1.6449 + 0.8416) * sd / Math.abs(delta)) ** 2);
}

/** Same results replayed with a fixed fraction of the bankroll per bet (index, start = 100). */
export function replay(bets: { odds: number | null; result: string }[], frac: number): number[] {
  const out = [100];
  for (const b of bets) out.push(out[out.length - 1] * (b.result === "ganha" && b.odds ? 1 + frac * (b.odds - 1) : 1 - frac));
  return out;
}
