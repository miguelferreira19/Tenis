"use client";

import Link from "next/link";
import { loadAutopilot, loadStrategy, odd, pc, spc, useData } from "../../lib/autopilot";

export default function Strategy() {
  const ap = useData(loadAutopilot), st = useData(loadStrategy);
  const error = ap.error || st.error;
  if (error) return <p className="ap-warn">{error}</p>;
  if (!ap.data || !st.data) return <p role="status" className="ap-loading">A carregar…</p>;
  const p = st.data.plan, all = st.data.policy.all, test = st.data.policy.test, fit = st.data.policy.fit;
  const samples = st.data.margin_measured.reduce((n, m) => n + m.matches, 0);

  return <div className="ap ap-doc">
    <header className="ap-hero"><div>
      <p className="ap-kicker">Como o plano decide</p>
      <h1>Múltiplas curtas de favoritos seguros, montantes pequenos, regras fixas</h1>
      <p className="ap-sub">De 2 em 2 horas o plano lê as odds da Betclic, escolhe as múltiplas e calcula o montante. O clique final é sempre teu.</p>
    </div></header>

    <section className="ap-panel">
      <h2 className="ap-h2">As regras</h2>
      <ol className="ap-rules">
        <li><strong>Pernas seguras.</strong> Só favoritos com chance estimada de pelo menos {pc(p.p_min)} e odd até {odd(p.odds_max)}: a zona mais barata do mercado, e a que já escolhes.</li>
        <li><strong>Poucas pernas.</strong> De 1 a {p.legs_max} pernas, de jogos diferentes, com odd total entre {odd(p.odds_lo)} e {odd(p.odds_hi)} (lucro de {pc(p.odds_lo - 1)} a {pc(p.odds_hi - 1)} quando ganha). Entre as combinações possíveis, escolhe a mais barata, a de maior valor esperado.</li>
        <li><strong>Montante fixo.</strong> {pc(p.unit)} da banca por múltipla (podes mudar na página inicial), no máximo {p.max_picks_day} por dia e {pc(p.day_cap)} da banca em risco por dia. Depois de perder {pc(p.stop_day)} num dia, para até ao dia seguinte.</li>
        <li><strong>Travão nas perdas.</strong> Se a banca cair mais de {pc(p.dd_soft)} desde o máximo, os montantes começam a baixar; a {pc(p.dd_hard)} de queda ficam em {pc(p.dd_floor)} do normal. (Aplica-se ao plano em papel; na tua conta, baixa tu a percentagem.)</li>
        <li><strong>Nunca a banca toda.</strong> Nada de reinvestir tudo na aposta seguinte nem de repor dinheiro para recuperar uma perda: é assim que uma única derrota apaga semanas.</li>
      </ol>
    </section>

    <section className="ap-panel">
      <h2 className="ap-h2">De onde vem a «chance estimada»</h2>
      <p>Das próprias odds da Betclic. Tira-se a margem da casa (método de Shin) e corrige-se um viés conhecido: os grandes favoritos ganham um pouco mais vezes do que as odds dizem. O modelo estatístico do projeto não acrescentou informação às odds, por isso não é usado. Nas pernas até 1,15 as chances ficam ligeiramente abaixo do que aconteceu no histórico (o que é conservador).</p>
    </section>

    <section className="ap-panel">
      <h2 className="ap-h2">O que o histórico diz, sem ilusões</h2>
      <p>Repetimos estas regras em {all.parlays.toLocaleString("pt-PT")} múltiplas de ATP e WTA entre 2019 e 2026 (ajuste {fit.parlays.toLocaleString("pt-PT")} em 2019–2022, teste {test.parlays.toLocaleString("pt-PT")} em 2023–2026), com a margem real da Betclic: {pc(st.data.betclic_overround - 1, 1)}, medida em {samples} jogos de duas datas.</p>
      <div className="ap-stats">
        <div><span>Múltiplas ganhas</span><strong>{pc(all.hit_rate)}</strong><small>odd média {odd(all.avg_odds)}</small></div>
        <div><span>Retorno por euro apostado</span><strong className="neg">{spc(all.roi)}</strong><small>margem de erro ± {pc(all.roi_se * 2, 1)} · ajuste {spc(fit.roi)} · teste {spc(test.roi)}</small></div>
        <div><span>Pernas por múltipla</span><strong>{Object.entries(all.legs_mix).filter(([, v]) => v > 0).map(([k, v]) => `${k}: ${pc(v)}`).join(" · ")}</strong><small>quase sempre 2 ou 3</small></div>
      </div>
      <div className="ap-table"><table><thead><tr><th>Ano</th><th>Múltiplas</th><th>Ganhas</th><th>Retorno</th></tr></thead><tbody>
        {Object.entries(st.data.policy.by_year).filter(([, r]) => r.parlays > 0).map(([y, r]) => <tr key={y}><td>{y}</td><td>{r.parlays}</td><td>{pc(r.hit_rate)}</td><td className={r.roi >= 0 ? "pos" : "neg"}>{spc(r.roi)}</td></tr>)}
      </tbody></table></div>
      <p><strong>Leitura honesta:</strong> acerta-se em cerca de dois terços das vezes, mas as odds pagam menos do que o risco e a margem da casa come a diferença: {pc(-all.roi, 1)} de cada euro apostado, em média. O que se controla é quanto se aposta e quantas pernas se juntam (cada perna extra custa 1 a 3 pontos). <Link href="/previsoes">Ver as previsões e o custo por perna →</Link></p>
      <p className="ap-fine">O backtest das apostas simples que existia antes assumia uma margem de 7,5% sem a ter medido; a medida é {pc(st.data.betclic_overround - 1, 1)}. O resultado dessa versão (−2,0% por euro) era, por isso, otimista.</p>
    </section>

    <section className="ap-panel">
      <h2 className="ap-h2">O que não está provado</h2>
      <ul className="ap-rules">
        <li><strong>O ao vivo.</strong> Os dados são preços de fecho antes do jogo. O plano não lê preços ao vivo e não há histórico para saber se apostar com o favorito já a ganhar é mais barato. Os preços ao vivo que li tinham margem de 11% a 15%.</li>
        <li><strong>Outros desportos.</strong> Futebol e basquetebol não estão no plano, mas aparecem no <Link href="/registo">registo</Link> porque os fizeste.</li>
        <li><strong>A tua série de vitórias.</strong> É boa, e com poucas apostas não se distingue de sorte. Cada aposta registada torna a resposta mais firme.</li>
      </ul>
    </section>

    <section className="ap-panel">
      <h2 className="ap-h2">Porque não há um bot que aposta sozinho</h2>
      <p>As casas licenciadas, como a Betclic, costumam proibir nos seus termos apostas feitas por programas automáticos; o risco é a conta ser fechada e o saldo retido. Além disso, com retorno esperado negativo, um bot só perderia de forma mais eficiente. O plano faz tudo menos o clique final: escolhe, calcula o montante, dá-te o link direto para cada jogo e fecha os resultados sozinho.</p>
    </section>

    <p className="ap-foot"><Link href="/">← Voltar ao plano de hoje</Link></p>
  </div>;
}
