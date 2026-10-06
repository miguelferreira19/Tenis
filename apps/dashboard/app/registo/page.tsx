"use client";

import Link from "next/link";
import { RealBet, RealLeg, hitRate, loadReal, loadStrategy, median, odd, pc, useData, useLocal } from "../../lib/autopilot";
import { atLeast, replay, runProb } from "../../lib/projection";
import { Lines } from "../../components/Lines";

const when = (iso: string) => new Date(iso).toLocaleString("pt-PT", { timeZone: "Europe/Lisbon", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const inPlay = (bet: RealBet, leg: RealLeg) => Date.parse(bet.placed_at) > Date.parse(leg.start_at);

export default function Record() {
  const real = useData(loadReal), strategy = useData(loadStrategy).data;
  const [frac] = useLocal<number>("tq.frac", 0.05);
  if (real.error) return <p className="ap-warn">{real.error}</p>;
  if (!real.data || !strategy) return <p role="status" className="ap-loading">A carregar…</p>;

  const { bets, before } = real.data, curve = strategy.leg_curve;
  const wins = bets.filter(b => b.result === "ganha").length;
  const legs = bets.flatMap(b => b.legs.map(l => ({ bet: b, leg: l })));
  const legOdds = legs.map(x => x.leg.odds);
  const chance = bets.map(b => b.legs.length ? b.legs.reduce((p, l) => p * hitRate(l.odds, curve), 1) : b.odds ? Math.min(0.99, 0.93 / b.odds) : NaN);
  const filled = chance.map(p => Number.isFinite(p) ? p : median(chance.filter(Number.isFinite)));
  const expected = filled.reduce((a, b) => a + b, 0), luck = atLeast(filled, wins);
  let first = bets.length;
  while (first > 0 && bets[first - 1].result === "ganha") first--;
  const streak = bets.length - first, streakChance = runProb(filled.slice(first));
  const live = legs.filter(x => inPlay(x.bet, x.leg)).length;
  const real100 = [100, ...bets.map(b => b.index)], mine = replay(bets, frac);

  return <div className="ap ap-doc">
    <header className="ap-hero"><div>
      <p className="ap-kicker">Registo · as tuas apostas reais</p>
      <h1>{wins} de {bets.length} ganhas desde {new Date(real.data.start).toLocaleDateString("pt-PT", { day: "numeric", month: "long" })}</h1>
      <p className="ap-sub">Lido na tua conta Betclic. O site é público, por isso só mostra percentagens e índices: nunca montantes, saldos ou referências.</p>
    </div></header>

    <section className="ap-stats" aria-label="Resumo">
      <div><span>Banca</span><strong className="pos">×{(real100.at(-1)! / 100).toLocaleString("pt-PT", { maximumFractionDigits: 1 })}</strong><small>índice 100 → {Math.round(real100.at(-1)!)} em {bets.length} apostas</small></div>
      <div><span>Por aposta, mediana</span><strong>{pc(median(bets.map(b => b.stake_pct)))}</strong><small>da banca; máximo {pc(Math.max(...bets.map(b => b.stake_pct)))}</small></div>
      <div><span>Pernas escolhidas</span><strong>{odd(median(legOdds))}</strong><small>odd mediana; {pc(legOdds.filter(o => o <= 1.25).length / legOdds.length)} com odd até 1,25</small></div>
      <div><span>Já com o jogo a decorrer</span><strong>{pc(live / legs.length)}</strong><small>{live} de {legs.length} pernas apostadas depois do início</small></div>
    </section>

    <section className="ap-panel ap-callout" aria-labelledby="h-luck">
      <h2 id="h-luck" className="ap-h2">Sorte ou vantagem?</h2>
      <p className="ap-big">Esperado: <strong>{expected.toLocaleString("pt-PT", { maximumFractionDigits: 1 })}</strong> vitórias em {bets.length} · tiveste <strong>{wins}</strong></p>
      <p>Com as chances que o histórico dá a favoritos destas odds, a probabilidade de teres {wins} ou mais vitórias só por acaso é <strong>{pc(luck, 1)}</strong>
        {luck < 0.05 ? ": pouco provável por acaso, mas" : ": plausível por acaso, e"} {bets.length} apostas é uma amostra pequena para tirar conclusões.
        {streak > 2 && ` A série de ${streak} vitórias seguidas tinha cerca de ${pc(streakChance, 1)} de probabilidade.`}
        {" "}Para confirmar uma vantagem real são precisas centenas de apostas. <Link href="/previsoes">Ver quantas →</Link></p>
      <p className="ap-fine">Aproximação: usa as chances do ténis pré-jogo para todas as pernas (inclui futebol e basquetebol) e assume {pc(median(chance.filter(Number.isFinite)))} para a aposta sem odd conhecida.</p>
    </section>

    <section className="ap-panel" aria-labelledby="h-replay">
      <h2 id="h-replay" className="ap-h2">As mesmas {bets.length} apostas com {pc(frac)} fixo da banca</h2>
      <Lines caption={`Banca em índice: real ${Math.round(real100.at(-1)!)}, com ${pc(frac)} fixo ${Math.round(mine.at(-1)!)}`} series={[
        { label: "o que fizeste", values: real100, color: "var(--lime)" }, { label: `com ${pc(frac)} fixo`, values: mine, color: "var(--aqua)" }]} />
      <p>Com os mesmos resultados, apostar {pc(frac)} em cada uma dava {Math.round(mine.at(-1)!)} em vez de {Math.round(real100.at(-1)!)}: menos lucro, mas o pior que podia acontecer numa derrota era perder {pc(frac)}, não {pc(Math.max(...bets.map(b => b.stake_pct)))}.
        O ganho de {Math.round(real100.at(-1)! - 100)}% veio de reinvestir tudo; é também o que torna uma única derrota tão cara.</p>
    </section>

    <section aria-labelledby="h-bets">
      <h2 id="h-bets" className="ap-h2">Todas as apostas</h2>
      <div className="ap-table"><table><thead><tr><th>Feita em</th><th>Pernas</th><th>Odd</th><th>% da banca</th><th>Resultado</th><th>Índice</th></tr></thead>
        <tbody>{[...bets].reverse().map(b => <tr key={b.placed_at}>
          <td>{when(b.placed_at)}</td>
          <td>{b.legs.length ? b.legs.map(l => <div key={l.pick}>{l.pick} <b>{odd(l.odds)}</b>{l.sport !== "ténis" && <em className="ap-tag">{l.sport}</em>}{inPlay(b, l) && <em className="ap-tag">em jogo</em>}</div>)
            : <small>{b.note ?? "sem detalhe"}</small>}</td>
          <td>{b.odds ? odd(b.odds) : "—"}</td><td>{pc(b.stake_pct)}</td>
          <td className={b.result === "ganha" ? "pos" : "neg"}>{b.result}</td><td>{b.index.toLocaleString("pt-PT", { maximumFractionDigits: 0 })}</td></tr>)}</tbody></table></div>
      <p className="ap-fine">Antes ({new Date(before.from).toLocaleDateString("pt-PT", { day: "numeric", month: "short" })} a {new Date(before.to).toLocaleDateString("pt-PT", { day: "numeric", month: "short" })}): {before.bets} apostas pequenas, {before.wins} ganha. {before.note}</p>
    </section>

    <p className="ap-foot">O plano acompanha só ténis ATP/WTA. Futebol e basquetebol aparecem aqui porque os fizeste, mas o site não os sugere nem os valida. <Link href="/estrategia">Ver a estratégia →</Link></p>
  </div>;
}
