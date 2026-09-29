// node lib/parlay.test.mjs — valores conferidos com apps/api/tennis_quant/parlay.py
import assert from "node:assert/strict";
import { calculateTicket } from "./parlay.ts";

const legs = [0, 1, 2].map(i => ({fixture_id: String(i), decimal_odds: 2, bookmaker: "book", source: "provider"}));
const system = calculateTicket(legs, "system", 12, 2);
assert.equal(system.line_count, 3);
assert.equal(system.max_gross_return, 48);
assert.ok(system.same_bookmaker);
assert.equal(calculateTicket(legs, "round_robin", 12).line_count, 4);
assert.throws(() => calculateTicket([legs[0], legs[0]], "accumulator"), /mesmo jogo/);

const manual = [1.85, 2.4, 3.1, 1.5].map((odds, i) => ({fixture_id: String(i), decimal_odds: odds, bookmaker: "b", source: "manual"}));
const cases = [["accumulator", null, 10, [1, 206.46, 196.46, 20.646, 20.646, 10]],
  ["round_robin", null, 33, [11, 268.42, 235.42, 4.44, 20.646, 3]],
  ["system", 3, 20, [4, 200.93, 180.93, 13.764, 11.16, 5]]];
for (const [kind, size, stake, [count, gross, net, first, last, perLine]] of cases) {
  const t = calculateTicket(manual, kind, stake, size);
  assert.deepEqual([t.line_count, t.max_gross_return, t.max_net_profit, t.lines[0].decimal_odds, t.lines.at(-1).decimal_odds, t.lines[0].stake], [count, gross, net, first, last, perLine], kind);
  assert.equal(t.provider_prices, false);
}
console.log("parlay ok");
