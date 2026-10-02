"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Autopilot, loadAutopilot, odd, pc } from "../../lib/autopilot";
import { BankCurve } from "../../components/BankCurve";

export default function Strategy() {
  const [data, setData] = useState<Autopilot | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { loadAutopilot().then(setData).catch(e => setError(e.message)); }, []);
  if (error) return <p className="ap-warn">{error}</p>;
  if (!data) return <p role="status" className="ap-loading">A carregar…</p>;
  const p = data.plan, bt = data.backtest;
  const test = bt.test_flat?.betclic_proxy, sim = bt.simulation_betclic, base = bt.baseline_all_favourites_betclic;
  const years = bt.test_years?.length ? `${bt.test_years[0]}–${bt.test_years[bt.test_years.length - 1]}` : "";

  return <div className="ap ap-doc">
    <header className="ap-hero"><div>
      <p className="ap-kicker">Como o piloto decide</p>
      <h1>Favoritos fortes, apostas pequenas, regras fixas</h1>
      <p className="ap-sub">De 2 em 2 horas o piloto lê as odds da Betclic, escolhe as apostas e calcula os montantes. Tu só copias.</p>
    </div></header>

    <section className="ap-panel">
      <h2 className="ap-h2">As regras</h2>
      <ol className="ap-rules">
        <li><strong>Só favoritos claros.</strong> Chance estimada de pelo menos {pc(p.p_min)} e odd entre {odd(p.odds_min)} e {odd(p.odds_max)}. Só apostas simples, uma por jogo; nada de combinadas, que multiplicam a margem da casa.</li>
        <li><strong>Montante fixo.</strong> Cada aposta vale {pc(p.unit)} da banca atual. Se a banca cresce, as apostas crescem; se encolhe, encolhem.</li>
        <li><strong>Limite diário.</strong> No máximo {p.max_picks_day} apostas e {pc(p.day_cap)} da banca por dia. Depois de perder {pc(p.stop_day)} num dia, para até ao dia seguinte.</li>
        <li><strong>Travão nas perdas.</strong> Se a banca cair mais de {pc(p.dd_soft)} desde o máximo, os montantes começam a baixar; a {pc(p.dd_hard)} de queda ficam em {pc(p.dd_floor)} do normal.</li>
        <li><strong>Nunca repor dinheiro.</strong> O plano nunca pede depósitos e nunca aumenta a aposta para recuperar uma perda.</li>
      </ol>
    </section>

    <section className="ap-panel">
      <h2 className="ap-h2">De onde vem a «chance estimada»</h2>
      <p>Das próprias odds da Betclic. Primeiro tira-se a margem da casa (método de Shin), depois corrige-se um viés conhecido: as casas pagam os favoritos fortes um pouco abaixo do que valem e os azarões muito acima. Testámos se o nosso modelo estatístico acrescentava informação às odds e a resposta foi não: com o modelo misturado as previsões ficavam piores. Por isso o piloto usa só as odds.</p>
    </section>

    {test && <section className="ap-panel">
      <h2 className="ap-h2">O que esperar, sem ilusões</h2>
      <p>Testámos estas regras em {test.bets} jogos ATP/WTA de {years}, que não foram usados para as escolher, com a margem típica da Betclic (~{pc((bt.betclic_overround ?? 1.075) - 1, 1)}).</p>
      <div className="ap-stats">
        <div><span>Apostas ganhas</span><strong>{pc(test.hit_rate)}</strong><small>mais de 4 em cada 5</small></div>
        <div><span>Retorno por euro apostado</span><strong className={(test.roi ?? 0) >= 0 ? "pos" : "neg"}>{pc(test.roi, 1)}</strong><small>margem de erro ± {pc((test.roi_se ?? 0) * 2, 1)}</small></div>
        {sim && <div><span>Banca de 100 € a {pc(p.unit)} por aposta</span><strong>{sim.end.toLocaleString("pt-PT", { maximumFractionDigits: 0 })} €</strong><small>{sim.bets} apostas · pior queda {pc(sim.max_drawdown)}</small></div>}
      </div>
      {sim && <BankCurve points={sim.curve_weekly} />}
      <p><strong>Leitura honesta:</strong> acerta-se muito, mas com odds de 1,10 a 1,50 cada derrota apaga o lucro de 2 a 10 vitórias, e a margem da casa come a diferença. No histórico, a estratégia perdeu dinheiro devagar e de forma controlada. Apostar em todos os favoritos dava {base ? pc(base.roi, 1) : "pior"} por euro; os filtros e as regras reduzem o custo, mas não o transformam em lucro garantido. Usa a conta demo para confirmar isto com apostas reais antes de pôr dinheiro.</p>
      {bt.test_flat_by_year && <div className="ap-table"><table><thead><tr><th>Ano</th><th>Apostas</th><th>Ganhas</th><th>Retorno</th></tr></thead><tbody>
        {Object.entries(bt.test_flat_by_year).map(([y, r]) => <tr key={y}><td>{y}</td><td>{r.bets}</td><td>{pc(r.hit_rate)}</td><td className={(r.roi ?? 0) >= 0 ? "pos" : "neg"}>{pc(r.roi, 1)}</td></tr>)}
      </tbody></table></div>}
    </section>}

    <section className="ap-panel">
      <h2 className="ap-h2">Porque não há um bot que aposta sozinho</h2>
      <p>As casas licenciadas, como a Betclic, costumam proibir nos seus termos apostas feitas por programas automáticos; o risco é a conta ser fechada e o saldo retido. Além disso, com retorno esperado negativo, um bot só perderia de forma mais eficiente. O piloto faz tudo menos o clique final: escolhe, calcula o montante, dá-te o link direto para o jogo e fecha os resultados sozinho.</p>
    </section>

    <p className="ap-foot"><Link href="/">← Voltar às apostas de hoje</Link></p>
  </div>;
}
