// node lib/projection.test.mjs — a simulação da banca e as contas de acaso do site
import assert from "node:assert/strict";
import { atLeast, betsToConfirm, project, replay, rng, runProb } from "./projection.ts";

const plan = { unit: 0.05, day_cap: 0.15, stop_day: 0.1, max_picks_day: 3, odds_lo: 1.4, odds_hi: 1.9 };
const iso = t => new Date(t).toISOString().slice(0, 10);
const range = (from, to) => { const out = []; for (let t = Date.parse(from); t <= Date.parse(to); t += 86400000) out.push(iso(t)); return out; };
const model = (dates, parlays) => ({ plan, calendar: [[dates[0], dates.at(-1)]], days: Object.fromEntries(dates.map(d => [d, parlays])) });
const all = range("2024-01-01T00:00:00Z", "2025-12-31T00:00:00Z");
const start = new Date("2026-03-01T00:00:00Z");
const run = (m, o) => project(m, { bank: 100, frac: 0.05, horizon: 30, perDay: 1, start, paths: 4000, ...o });

// Determinismo: mesma semente, mesmo futuro.
assert.equal(rng(7)(), rng(7)());
assert.deepEqual(run(model(all, [[2, 0.5, 1]]), { scenario: "justo" }).p50, run(model(all, [[2, 0.5, 1]]), { scenario: "justo" }).p50);

// Odds justas: martingala, a média fica na banca inicial.
const fair = run(model(all, [[2, 0.4, 0]]), { scenario: "justo" });
assert.ok(Math.abs(fair.mean / 100 - 1) < 0.02, `justo ${fair.mean}`);
// Histórico real: se a múltipla ganhou sempre, cada dia multiplica a banca por 1,05; se perdeu sempre, por 0,95.
const wins = run(model(all, [[2, 0.4, 1]]), { scenario: "base" });
assert.ok(Math.abs(wins.p50[30] / 100 - 1.05 ** 30) < 0.01 && wins.profit === 1, `base ${wins.p50[30]}`);
const losses = run(model(all, [[2, 0.4, 0]]), { scenario: "base" });
assert.ok(Math.abs(losses.p50[30] / 100 - 0.95 ** 30) < 0.01 && losses.profit === 0);
// Metade dos dias a ganhar e metade a perder: martingala (+5% / -5%), a média fica perto da banca.
const mixed = { plan, calendar: [[all[0], all.at(-1)]], days: Object.fromEntries(all.map((d, i) => [d, [[2, 0.5, i % 2]]])) };
assert.ok(Math.abs(run(mixed, { scenario: "base" }).mean / 100 - 1) < 0.02);
// Vantagem de +3%: 1,0015^30.
const good = run(model(all, [[2, 0.4, 0]]), { scenario: "otimista" });
assert.ok(Math.abs(good.mean / 100 - 1.0015 ** 30) < 0.02, `otimista ${good.mean}`);
assert.ok(good.p10[30] <= good.p50[30] && good.p50[30] <= good.p90[30]);

// Máximo de múltiplas por dia e teto diário: 3 por dia a 5% = 15%, e a paragem após perder 10%.
const three = run(model(all, [[1.5, 0.6, 1], [1.5, 0.6, 0], [1.5, 0.6, 0]]), { scenario: "justo", perDay: 3 });
assert.ok(three.parlaysPerDay > 2.3 && three.parlaysPerDay <= 3, `${three.parlaysPerDay}`);
assert.ok(three.stakedPerDay <= 0.15 * 100 * 1.6); // banca pode crescer, nunca passa muito de 15%/dia
assert.ok(Math.abs(run(model(all, [[1.5, 0.6, 1], [1.5, 0.6, 1]]), { scenario: "base", perDay: 1 }).parlaysPerDay - 1) < 1e-9);

// Sazonalidade: sem jogos fora de outubro, fevereiro não aposta e outubro sim.
const october = range("2024-10-01T00:00:00Z", "2024-10-31T00:00:00Z");
const octModel = { plan, calendar: [["2024-01-01", "2024-12-31"], ["2025-01-01", "2025-12-31"]], days: Object.fromEntries(october.concat(october.map(d => d.replace("2024", "2025"))).map(d => [d, [[1.5, 0.6, 1]]])) };
const feb = run(octModel, { scenario: "base", horizon: 20 });
assert.equal(feb.parlaysPerDay, 0);
assert.deepEqual([feb.p10[20], feb.p90[20]], [100, 100]);
assert.ok(run(octModel, { scenario: "base", horizon: 20, start: new Date("2026-10-01T00:00:00Z") }).parlaysPerDay > 0.8);

// Acaso: probabilidade de pelo menos k vitórias e de uma série.
assert.ok(Math.abs(atLeast([0.5, 0.5], 2) - 0.25) < 1e-12);
assert.ok(Math.abs(atLeast([0.3, 0.6, 0.9], 0) - 1) < 1e-12);
assert.ok(Math.abs(atLeast([0.3, 0.6, 0.9], 3) - 0.162) < 1e-12);
assert.ok(Math.abs(runProb([0.5, 0.5, 0.5]) - 0.125) < 1e-12);
assert.ok(Math.abs(atLeast([0.9, 0.9, 0.9], 2) - (3 * 0.81 * 0.1 + 0.729)) < 1e-12);

// Quantas apostas para distinguir -4,4% de 0 (cerca de 1500) e menos para efeitos maiores.
const n = betsToConfirm(0.044, 1.45, 0.65);
assert.ok(n > 1400 && n < 1700, `${n}`);
assert.ok(betsToConfirm(0.1, 1.45, 0.65) < n);

// As mesmas apostas com 10% fixo: +100% × 10% e -10%.
assert.deepEqual(replay([{ odds: 2, result: "ganha" }, { odds: null, result: "perdida" }], 0.1).map(v => Math.round(v * 100) / 100), [100, 110, 99]);
console.log("projection ok");
