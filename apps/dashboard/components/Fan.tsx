import { eur } from "../lib/autopilot";

export type Series = { label: string; values: number[]; color: string };

/** Leque de futuros possíveis da banca: faixa 10%–90%, mediana e, opcionalmente, outras medianas. */
export function Fan({ p10, p50, p90, start, extra = [], height = 220 }:
  { p10: number[]; p50: number[]; p90: number[]; start: number; extra?: Series[]; height?: number }) {
  const n = p50.length - 1;
  if (n < 1) return null;
  const all = [...p10, ...p90, start, ...extra.flatMap(s => s.values)];
  const lo = Math.min(...all), hi = Math.max(...all), span = hi - lo || 1;
  const w = 640, pad = 8;
  const x = (i: number) => pad + (i / n) * (w - 2 * pad);
  const y = (v: number) => pad + (1 - (v - lo) / span) * (height - 2 * pad);
  const line = (values: number[]) => values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const back = [...p10].reverse().map((v, i) => `L${x(n - i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  return <figure className="ap-fan">
    <svg viewBox={`0 0 ${w} ${height}`} role="img" preserveAspectRatio="none"
      aria-label={`Banca daqui a ${n} dias: mediana ${eur(p50[n])}, 80% dos casos entre ${eur(p10[n])} e ${eur(p90[n])}`}>
      <path d={`${line(p90)}${back}Z`} fill="var(--aqua)" opacity=".16" />
      <line x1={pad} x2={w - pad} y1={y(start)} y2={y(start)} stroke="var(--dim)" strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
      {extra.map(s => <path key={s.label} d={line(s.values)} fill="none" stroke={s.color} strokeWidth="1.5" strokeDasharray="5 3" vectorEffect="non-scaling-stroke" />)}
      <path d={line(p50)} fill="none" stroke="var(--lime)" strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
    </svg>
    <figcaption>
      <span><i className="ap-key" style={{ background: "var(--lime)" }} />mediana {eur(p50[n])}</span>
      <span><i className="ap-key" style={{ background: "var(--aqua)", opacity: .5 }} />80% dos casos: {eur(p10[n])} a {eur(p90[n])}</span>
      {extra.map(s => <span key={s.label}><i className="ap-key" style={{ background: s.color }} />{s.label} {eur(s.values[n])}</span>)}
      <span>linha tracejada: banca atual {eur(start)}</span>
    </figcaption>
  </figure>;
}
