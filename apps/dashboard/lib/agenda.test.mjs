import assert from "node:assert/strict";
import {compareFavorites, favoriteProbability} from "./agenda.ts";
const matches = [null, .55, .1, .8, NaN, 1.1].map((probability_a, i) => ({id:i, probability_a, start_at:`2026-10-0${i+1}T12:00:00Z`}));
assert.deepEqual([...matches].sort(compareFavorites).map(item => item.id), [2,3,1,0,4,5]);
assert.equal(favoriteProbability(matches[2]), .9);
assert.equal(favoriteProbability(matches[4]), null);
assert.ok(compareFavorites({...matches[1], start_at:"2026-10-01T12:00:00Z"}, matches[1]) < 0);
assert.deepEqual(matches.map(item => item.id), [0,1,2,3,4,5]);
console.log("agenda ok");
