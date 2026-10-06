import type { Series } from "./Fan";

/** Linhas simples (uma por série) para comparar trajetórias; o eixo vertical vai do mínimo ao máximo. */
export function Lines({ series, height = 170, caption }: { series: Series[]; height?: number; caption: string }) {
  const n = Math.max(...series.map(s => s.values.length)) - 1;
  if (n < 1) return null;
  const all = series.flatMap(s => s.values);
  const lo = Math.min(...all), hi = Math.max(...all), span = hi - lo || 1;
  const w = 640, pad = 8;
  const path = (values: number[]) => values.map((v, i) =>
    `${i ? "L" : "M"}${(pad + (i / n) * (w - 2 * pad)).toFixed(1)},${(pad + (1 - (v - lo) / span) * (height - 2 * pad)).toFixed(1)}`).join("");
  return <figure className="ap-fan">
    <svg viewBox={`0 0 ${w} ${height}`} role="img" aria-label={caption} preserveAspectRatio="none">
      {series.map(s => <path key={s.label} d={path(s.values)} fill="none" stroke={s.color} strokeWidth="2.2" vectorEffect="non-scaling-stroke" />)}
    </svg>
    <figcaption>{series.map(s => <span key={s.label}><i className="ap-key" style={{ background: s.color }} />{s.label}: {s.values.at(-1)!.toLocaleString("pt-PT", { maximumFractionDigits: 0 })}</span>)}</figcaption>
  </figure>;
}
