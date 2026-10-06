"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { eur, loadStrategy, odd, pc, signed, spc, useData, useLocal } from "../../lib/autopilot";
import { SCENARIOS, Scenario, betsToConfirm, project } from "../../lib/projection";
import { Fan } from "../../components/Fan";

const ORDER: Scenario[] = ["base", "justo", "otimista"];
const NOTES: Record<Scenario, string> = {
  base: "Repete os dias reais de 2019–2026: as múltiplas que o plano teria feito, com os resultados que tiveram e a margem da Betclic nos preços. É a única que tem dados atrás.",
  justo: "Como se a Betclic cobrasse margem zero: ganhas tanto quanto as odds pagam. Serve de linha de referência, não existe na prática.",
  otimista: "Ganhares 3 cêntimos por euro apostado. Precisaria de uma vantagem real sobre a Betclic (por exemplo, no ao vivo) que ainda ninguém mediu.",
};
const FRACTIONS = [0.01, 0.02, 0.05, 0.1];

export default function Forecast() {
  const { data: strategy, error } = useData(loadStrategy);
  const [bank, setBank] = useLocal<number>("tq.bankroll", 50);
  const [frac, setFrac] = useLocal<number>("tq.frac", 0.05);
  const [horizon, setHorizon] = useState(90);
  const [perDay, setPerDay] = useState(3);
  const start = useMemo(() => new Date(`${new Date().toISOString().slice(0, 10)}T00:00:00Z`), []);

  const fans = useMemo(() => strategy && bank > 0 && frac > 0 ? Object.fromEntries(ORDER.map(sc =>
    [sc, project(strategy, { bank, frac, horizon, perDay, scenario: sc, start, paths: 2000 })])) as Record<Scenario, ReturnType<typeof project>> : null,
  [strategy, bank, frac, horizon, perDay, start]);
  const sens = useMemo(() => strategy && bank > 0 ? FRACTIONS.map(f => ({ f, fan: project(strategy, { bank, frac: f, horizon, perDay, scenario: "base", start, paths: 1500 }) })) : [],
  [strategy, bank, horizon, perDay, start]);

  if (error) return <p className="ap-warn">{error}</p>;
  if (!strategy) return <p role="status" className="ap-loading">A carregar…</p>;
  const all = strategy.policy.all, base = fans?.base;
  const cost = -all.roi;
  const evOf = (sc: Scenario) => SCENARIOS[sc].ev ?? all.roi;
  const confirmCost = betsToConfirm(Math.abs(all.roi), all.avg_odds, all.hit_rate), confirmEdge = betsToConfirm(0.03, all.avg_odds, all.hit_rate);

  return <div className="ap ap-doc">
    <header className="ap-hero">
      <div>
        <p className="ap-kicker">Previsões sustentadas</p>
        <h1>Quanto podes ganhar, e perder, com este plano</h1>
        <p className="ap-sub">Simulado sobre {all.parlays.toLocaleString("pt-PT")} múltiplas que o plano teria feito entre 2019 e 2026, na mesma época do ano de hoje, com a margem real da Betclic. Sem promessas: um intervalo e as hipóteses por trás.</p>
      </div>
      <div className="ap-controls">
        <label className="ap-bank">A tua banca<span><input type="number" min="0" step="1" inputMode="decimal" value={bank} onChange={e => setBank(Math.max(0, Number(e.target.value) || 0))} /> €</span></label>
        <label className="ap-bank">Por múltipla<span><input type="number" min="1" max="20" step="1" inputMode="decimal" value={Math.round(frac * 100)}
          onChange={e => setFrac(Math.min(0.2, Math.max(0.01, (Number(e.target.value) || 1) / 100)))} /> %</span></label>
        <label className="ap-bank">Horizonte<select value={horizon} onChange={e => setHorizon(Number(e.target.value))}>{[30, 90, 180].map(h => <option key={h} value={h}>{h} dias</option>)}</select></label>
        <label className="ap-bank">Máx. por dia<select value={perDay} onChange={e => setPerDay(Number(e.target.value))}>{[1, 2, 3].map(n => <option key={n} value={n}>{n} {n === 1 ? "múltipla" : "múltiplas"}</option>)}</select></label>
      </div>
    </header>

    {fans && base && <>
      <section className="ap-panel ap-callout" aria-labelledby="h-concl">
        <h2 id="h-concl" className="ap-h2">A conclusão, sem rodeios</h2>
        <p className="ap-big">Esperado: <strong className="neg">{signed(base.stakedPerDay * all.roi)}</strong> por dia</p>
        <p>Com {pc(frac)} por múltipla ({eur(bank * frac)}) farias em média {base.parlaysPerDay.toLocaleString("pt-PT", { maximumFractionDigits: 1 })} múltiplas por dia e apostarias {eur(base.stakedPerDay)}.
          Cada euro apostado custou em média {pc(cost, 1)} (± {pc(all.roi_se * 2, 1)}): é a margem da Betclic, que é de {pc(strategy.betclic_overround - 1, 0)} nos jogos de ténis. Ganhas {pc(all.hit_rate)} das vezes a uma odd média de {odd(all.avg_odds)}, e isso não chega para pagar a margem.
          O que se pode mudar é quanto se aposta: a perda esperada é proporcional ao montante apostado.</p>
      </section>

      <section className="ap-panel" aria-labelledby="h-fan">
        <h2 id="h-fan" className="ap-h2">A tua banca daqui a {horizon} dias · {SCENARIOS.base.label.toLowerCase()}</h2>
        <Fan p10={base.p10} p50={base.p50} p90={base.p90} start={bank} extra={[
          { label: "odds justas", values: fans.justo.p50, color: "var(--dim)" }, { label: "+3%", values: fans.otimista.p50, color: "var(--orange)" }]} />
        <div className="ap-table"><table><thead><tr><th>Cenário</th><th>Valor esperado</th><th>Mediana</th><th>80% dos casos</th><th>Acima de hoje</th><th>Perder 30%+</th><th>Dobrar</th></tr></thead>
          <tbody>{ORDER.map(sc => { const f = fans[sc]; return <tr key={sc}>
            <td>{SCENARIOS[sc].label}<small>{NOTES[sc]}</small></td>
            <td className={evOf(sc) >= 0 ? "pos" : "neg"}>{spc(evOf(sc))}</td>
            <td>{eur(f.p50[horizon])}</td><td>{eur(f.p10[horizon])} a {eur(f.p90[horizon])}</td>
            <td>{pc(f.profit)}</td><td>{pc(f.lose30)}</td><td>{pc(f.double)}</td></tr>; })}</tbody></table></div>
      </section>

      <section className="ap-panel" aria-labelledby="h-sens">
        <h2 id="h-sens" className="ap-h2">E se apostares mais, ou menos?</h2>
        <p>Cenário histórico, {horizon} dias, {perDay} {perDay === 1 ? "múltipla" : "múltiplas"} por dia no máximo. Apostar mais aumenta o intervalo nos dois sentidos e a perda esperada; apostar menos encolhe os dois.</p>
        <div className="ap-table"><table><thead><tr><th>Por múltipla</th><th>Montante</th><th>Mediana</th><th>80% dos casos</th><th>Acima de hoje</th></tr></thead>
          <tbody>{sens.map(({ f, fan }) => <tr key={f}><td>{pc(f)}</td><td>{eur(bank * f)}</td><td>{eur(fan.p50[horizon])}</td><td>{eur(fan.p10[horizon])} a {eur(fan.p90[horizon])}</td><td>{pc(fan.profit)}</td></tr>)}</tbody></table></div>
      </section>
    </>}
    {!fans && <p className="ap-warn">Indica a tua banca e a percentagem por múltipla (acima de zero) para ver as previsões.</p>}

    <section className="ap-panel" aria-labelledby="h-legs">
      <h2 id="h-legs" className="ap-h2">Porque poucas pernas e pernas seguras</h2>
      <p>Cada perna paga a margem da casa. Para o mesmo lucro por aposta, uma só perna custa muito menos do que quatro. E as pernas mais seguras são as mais baratas: os grandes favoritos ganham um pouco mais vezes do que as odds dizem.</p>
      <div className="ap-table"><table><thead><tr><th>Pernas</th><th>Odd média</th><th>Ganhas</th><th>Retorno por € (histórico)</th><th>Retorno previsto</th></tr></thead>
        <tbody>{strategy.by_legs.map(r => <tr key={r.legs}><td>{r.legs}</td><td>{odd(r.all.avg_odds)}</td><td>{pc(r.all.hit_rate)}</td>
          <td className="neg">{spc(r.all.roi)} ± {pc(r.all.roi_se * 2, 1)}</td><td>{spc(r.all.ev_model)}</td></tr>)}</tbody></table></div>
      <p className="ap-fine">Uma múltipla por dia, odd total entre {odd(strategy.by_legs_band[0])} e {odd(strategy.by_legs_band[1])}, ATP e WTA, 2019–2026. «Retorno previsto» usa as chances do plano; a diferença para o histórico é erro de amostra.</p>
      <div className="ap-table"><table><thead><tr><th>Odd da perna</th><th>Jogos</th><th>Favorito ganhou</th><th>Retorno por € numa simples</th></tr></thead>
        <tbody>{strategy.leg_curve.map(b => <tr key={b.odds_lo}><td>{odd(b.odds_lo)} a {odd(b.odds_hi)}</td><td>{b.bets.toLocaleString("pt-PT")}</td><td>{pc(b.hit_rate, 1)}</td>
          <td className={b.roi >= -0.015 ? "" : "neg"}>{spc(b.roi)} ± {pc(b.roi_se * 2, 1)}</td></tr>)}</tbody></table></div>
      <p className="ap-fine">Até à odd 1,15 o custo é de cerca de 1% por perna, estatisticamente perto de zero; a partir de 1,15 passa para cerca de 4% ou mais. É por isso que o plano só usa pernas seguras. Mas para chegar a 1,40 com pernas assim precisas de várias, e o custo volta a somar.</p>
    </section>

    <section className="ap-panel" aria-labelledby="h-proof">
      <h2 id="h-proof" className="ap-h2">O que falta para a previsão ser mais firme</h2>
      <p>Para poder dizer que o custo é mesmo diferente de zero são precisas cerca de <strong>{confirmCost.toLocaleString("pt-PT")} múltiplas</strong>; para confirmar uma vantagem de +3%, cerca de <strong>{confirmEdge.toLocaleString("pt-PT")}</strong>. Com poucas dezenas de apostas, uma boa série tanto pode ser vantagem como sorte.</p>
      <ul className="ap-rules">
        <li><strong>Ao vivo não está medido.</strong> Os dados históricos são preços de fecho antes do jogo. Nos preços ao vivo que li hoje a margem foi de 11% a 15% (só os favoritos a 1,02 tinham margem baixa). Não há razão, para já, para achar que o ao vivo é mais barato.</li>
        <li><strong>Outras fontes de vantagem</strong> (preços melhores noutras casas, promoções) mudam a conta, mas ainda não estão medidas aqui.</li>
        <li><Link href="/registo">O registo das tuas apostas</Link> é o que vai tornar isto mais firme com o tempo.</li>
      </ul>
    </section>
  </div>;
}
