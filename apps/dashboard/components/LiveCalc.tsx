import { useState } from "react";
import { Bucket, Plan, eur, hitRate, odd, pc, signed, spc } from "../lib/autopilot";

/** Para as apostas que o plano não vê (ao vivo): escreve as odds das pernas e vê o montante, o ganho e o custo. */
export function LiveCalc({ bank, frac, plan, curve }: { bank: number; frac: number; plan: Plan; curve: Bucket[] }) {
  const [fields, setFields] = useState<string[]>(["", "", "", ""]);
  const legs = fields.map(f => Number(f.replace(",", "."))).filter(o => o > 1);
  const total = Math.round(legs.reduce((a, o) => a * o, 1) * 100) / 100;
  const stake = Math.round(bank * frac * 100) / 100;
  const chance = legs.reduce((a, o) => a * hitRate(o, curve), 1), ev = chance * total - 1;
  const checks: [boolean, string][] = [
    [legs.every(o => o <= plan.odds_max), `Pernas seguras (odd até ${odd(plan.odds_max)})`],
    [legs.length <= plan.legs_max, `No máximo ${plan.legs_max} pernas`],
    [total >= plan.odds_lo && total <= plan.odds_hi, `Odd total entre ${odd(plan.odds_lo)} e ${odd(plan.odds_hi)}`],
  ];
  return <section className="ap-panel" aria-labelledby="h-calc">
    <h2 id="h-calc" className="ap-h2">Ao vivo ou fora do plano: calcula a tua múltipla</h2>
    <p className="ap-fine">O plano só vê preços de antes do jogo. Se vires boas pernas ao vivo, escreve as odds e confirma o montante e o custo antes de apostar.</p>
    <div className="ap-calc">{fields.map((f, i) => <label key={i}>Odd da perna {i + 1}
      <input type="text" inputMode="decimal" placeholder="1,15" value={f}
        onChange={e => setFields(fields.map((x, j) => j === i ? e.target.value : x))} /></label>)}</div>
    {legs.length > 0 ? <>
      <dl className="ap-nums ap-nums-5">
        <div><dt>Odd total</dt><dd>{odd(total)}</dd></div>
        <div><dt>Montante</dt><dd>{eur(stake)}</dd></div>
        <div><dt>Se ganhar</dt><dd>+{eur(stake * (total - 1))}</dd></div>
        <div><dt>Chance</dt><dd>{pc(chance)}</dd></div>
        <div><dt>Valor esperado</dt><dd className="neg">{spc(ev)}</dd></div>
      </dl>
      <p className="ap-fine">Em média {signed(stake * ev)} por aposta. A chance usa o que ganharam os favoritos destas odds antes do jogo (2019–2026); ao vivo não está medida.</p>
      <ul className="ap-checks">{checks.map(([ok, label]) => <li key={label} className={ok ? "ok" : "no"}><span aria-hidden>{ok ? "✓" : "✗"}</span> {label}<span className="sr-only">{ok ? ": cumpre" : ": não cumpre"}</span></li>)}</ul>
    </> : <p className="ap-fine">Escreve pelo menos uma odd (por exemplo 1,12).</p>}
  </section>;
}
