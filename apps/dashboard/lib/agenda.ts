type Match = {probability_a: number | null; start_at: string};

export function favoriteProbability(item: Match): number | null {
  const p = item.probability_a;
  return p !== null && Number.isFinite(p) && p >= 0 && p <= 1 ? Math.max(p, 1-p) : null;
}

export function compareFavorites(a: Match, b: Match): number {
  return (favoriteProbability(b) ?? -1) - (favoriteProbability(a) ?? -1)
    || Date.parse(a.start_at) - Date.parse(b.start_at);
}
