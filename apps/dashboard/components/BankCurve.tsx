/** Minimal SVG line of the bankroll; no chart library needed for one series. */
export function BankCurve({ points, height = 140 }: { points: [string, number][]; height?: number }) {
  if (points.length < 2) return null;
  const values = points.map(p => p[1]);
  const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  const w = 600, pad = 6;
  const xy = points.map(([, v], i) => [pad + (i / (points.length - 1)) * (w - 2 * pad),
    pad + (1 - (v - lo) / span) * (height - 2 * pad)]);
  const path = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("");
  const first = values[0], last = values[values.length - 1];
  const fmt = (v: number) => v.toLocaleString("pt-PT", { maximumFractionDigits: 0 });
  return <figure className="ap-curve">
    <svg viewBox={`0 0 ${w} ${height}`} role="img" aria-label={`Banca de ${fmt(first)} € para ${fmt(last)} €`} preserveAspectRatio="none">
      <path d={path} fill="none" stroke={last >= first ? "var(--lime)" : "var(--orange)"} strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
    <figcaption><span>{points[0][0]} · {fmt(first)} €</span><span>mín. {fmt(lo)} € · máx. {fmt(hi)} €</span><span>{points[points.length - 1][0]} · {fmt(last)} €</span></figcaption>
  </figure>;
}
