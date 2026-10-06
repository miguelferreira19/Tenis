"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Parlay, eur, loadAutopilot, loadReal, loadStrategy, median, odd, pc, signed, spc, useData, useLocal } from "../lib/autopilot";
import { project } from "../lib/projection";
import { Fan } from "../components/Fan";
import { LiveCalc } from "../components/LiveCalc";
import { ParlayCard } from "../components/ParlayCard";

const HORIZON = 30;
const clock = (iso: string, opts: Intl.DateTimeFormatOptions) => new Date(iso).toLocaleString("pt-PT", { timeZone: "Europe/Lisbon", ...opts });

export default function Today() {
  const { data, error } = useData(loadAutopilot);
  const strategy = useData(loadStrategy).data;
  const real = useData(loadReal).data;
  const [now, setNow] = useState(0);
  const [bank, setBank] = useLocal<number>("tq.bankroll", 50);
  const [frac, setFrac] = useLocal<number>("tq.frac", 0.05);
  const [placed, setPlaced] = useLocal<string[]>("tq.placed", []);

  useEffect(() => {
    setNow(Date.now());
    const t = setInterval(() => setNow(Date.now()), 60000);
    return () => clearInterval(t);
  }, []);
  const today = now ? new Date(now).toISOString().slice(0, 10) : "";
  const perDay = data?.plan.max_picks_day ?? 3;
  const fan = useMemo(() => strategy && today && bank > 0 && frac > 0
    ? project(strategy, { bank, frac, horizon: HORIZON, perDay, scenario: "base", start: new Date(`${today}T00:00:00Z`), paths: 1500 })
    : null, [strategy, today, bank, frac, perDay]);

  if (error) return <div className="ap-empty"><h1>Plano de hoje</h1><p>{error}</p></div>;
  if (!data || !now) return <p role="status" className="ap-loading">A carregar o plano de hoje…</p>;

  const plan = data.plan, stake = Math.round(bank * frac * 100) / 100;
  const current = data.bets.filter(b => b.status === "pendente" && !b.id.startsWith("s:")); // "s:" = apostas simples do plano antigo
  const upcoming = current.filter(b => new Date(b.start_at).getTime() > now).sort((a, b) => a.start_at.localeCompare(b.start_at));
  const underway = current.filter(b => new Date(b.start_at).getTime() <= now);
  const done = data.bets.filter(b => b.status !== "pendente");
  const toPlace = upcoming.filter(b => !placed.includes(b.id));
  const total = stake * toPlace.length, profit = toPlace.reduce((s, b) => s + stake * (b.odds - 1), 0);
  const overCap = bank > 0 && total > plan.day_cap * bank + 0.005;
  const toggle = (id: string) => setPlaced(placed.includes(id) ? placed.filter(x => x !== id) : [...placed, id]);
  const next = new Date(new Date(data.generated_at).getTime() + 2 * 3600e3);
  const s = data.summary, paperChange = data.bank.bank / data.start_bank - 1;
  const roi = strategy?.policy.all.roi;

  return <div className="ap">
    <header className="ap-hero">
      <div>
        <p className="ap-kicker">Múltiplas curtas · preços da Betclic às {clock(data.observed_at, { hour: "2-digit", minute: "2-digit" })}</p>
        <h1>{toPlace.length ? `${toPlace.length} ${toPlace.length === 1 ? "múltipla" : "múltiplas"} para fazer · ${eur(total)}`
          : upcoming.length ? "Tudo apostado. Agora é esperar." : "Hoje não há múltiplas que cumpram o plano."}</h1>
        <p className="ap-sub">{toPlace.length
          ? `Se ganhares todas: ${signed(profit)}. Se falharem todas: ${signed(-total)} (${pc(bank > 0 ? total / bank : 0, 1)} da banca).`
          : upcoming.length ? "Os resultados entram sozinhos depois dos jogos."
            : `O plano só usa pernas seguras (odd até ${odd(plan.odds_max)}) que juntas dêem entre ${odd(plan.odds_lo)} e ${odd(plan.odds_hi)}. Próxima leitura perto das ${clock(next.toISOString(), { hour: "2-digit", minute: "2-digit" })}.`}</p>
      </div>
      <div className="ap-controls">
        <label className="ap-bank">A tua banca
          <span><input type="number" min="0" step="1" inputMode="decimal" value={bank}
            onChange={e => setBank(Math.max(0, Number(e.target.value) || 0))} /> €</span>
          <small>o saldo que tens na Betclic</small>
        </label>
        <label className="ap-bank">Por múltipla
          <span><input type="number" min="1" max="20" step="1" inputMode="decimal" value={Math.round(frac * 100)}
            onChange={e => setFrac(Math.min(0.2, Math.max(0.01, (Number(e.target.value) || 1) / 100)))} /> %</span>
          <small>= {eur(stake)} · nunca a banca toda</small>
        </label>
      </div>
    </header>

    {!data.betclic_ok && <p className="ap-warn" role="alert">As odds da Betclic têm mais de 6 horas (o PC que as recolhe pode estar desligado). Confirma as odds na Betclic antes de apostar.</p>}
    {overCap && <p className="ap-warn" role="status">Com {pc(frac)} por múltipla passas o teto diário do plano ({pc(plan.day_cap)} da banca). Baixa a percentagem ou faz só as primeiras.</p>}

    {upcoming.length > 0 && <section aria-labelledby="h-now">
      <h2 id="h-now" className="ap-h2">Para apostar</h2>
      <ol className="ap-cards">{upcoming.map(b => <ParlayCard key={b.id} bet={b} stake={stake} now={now}
        done={placed.includes(b.id)} onToggle={() => toggle(b.id)} />)}</ol>
    </section>}

    {underway.length > 0 && <section aria-labelledby="h-live">
      <h2 id="h-live" className="ap-h2">À espera do resultado</h2>
      <ul className="ap-list">{underway.map(b => <li key={b.id}><span>{legsLabel(b)}</span><span>{odd(b.odds)} · {eur(stake)}</span></li>)}</ul>
    </section>}

    {strategy && <LiveCalc bank={bank} frac={frac} plan={plan} curve={strategy.leg_curve} />}

    <section className="ap-panel" aria-labelledby="h-fan">
      <h2 id="h-fan" className="ap-h2">Perspetiva a {HORIZON} dias · com o que o histórico mostrou</h2>
      {fan ? <>
        <p className="ap-big">{eur(bank)} → <strong className={fan.p50[HORIZON] >= bank ? "pos" : "neg"}>{eur(fan.p50[HORIZON])}</strong> <span>(mediana)</span></p>
        <p>Em 80% dos casos acabas entre {eur(fan.p10[HORIZON])} e {eur(fan.p90[HORIZON])}; a probabilidade de estares acima de hoje é {pc(fan.profit)}.
          {roi != null && ` Cada euro apostado nestas múltiplas custou em média ${pc(-roi, 1)} entre 2019 e 2026 (margem real da Betclic incluída).`}</p>
        <Fan p10={fan.p10} p50={fan.p50} p90={fan.p90} start={bank} />
        <p className="ap-foot"><Link href="/previsoes">Cenários, montante e quantas apostas são precisas para confirmar uma vantagem →</Link></p>
      </> : <p className="ap-fine">Indica a tua banca e a percentagem por múltipla para ver a perspetiva.</p>}
    </section>

    {real && <section className="ap-panel" aria-labelledby="h-real">
      <h2 id="h-real" className="ap-h2">As tuas apostas reais desde {new Date(real.start).toLocaleDateString("pt-PT", { day: "numeric", month: "long" })}</h2>
      <p className="ap-big"><strong>{real.bets.filter(b => b.result === "ganha").length}</strong> de {real.bets.length} ganhas · banca ×{(real.bets.at(-1)!.index / 100).toLocaleString("pt-PT", { maximumFractionDigits: 1 })}</p>
      <p>Em metade das apostas arriscaste {pc(median(real.bets.map(b => b.stake_pct)))} da banca ou mais (máximo {pc(Math.max(...real.bets.map(b => b.stake_pct)))}): uma derrota apaga a maior parte; com {pc(frac)} apagaria {pc(frac)}.
        {" "}<Link href="/registo">Ver as apostas, o acaso e o que mudava com {pc(frac)} →</Link></p>
    </section>}

    <section className="ap-stats" aria-label="Plano em papel">
      <div><span>Plano em papel (100 €)</span><strong className={paperChange >= 0 ? "pos" : "neg"}>{spc(paperChange)}</strong><small>{s.bets ? `${eur(data.bank.bank)} · ${s.won} de ${s.bets} ganhas` : "ainda sem apostas fechadas"}</small></div>
      <div><span>Por liquidar</span><strong>{data.bets.filter(b => b.status === "pendente").length}</strong><small>no plano em papel, incluindo as simples do plano antigo</small></div>
    </section>

    {done.length > 0 && <section aria-labelledby="h-hist">
      <h2 id="h-hist" className="ap-h2">Histórico do plano em papel</h2>
      <div className="ap-table"><table><thead><tr><th>Dia</th><th>Pernas</th><th>Odd</th><th>Resultado</th></tr></thead>
        <tbody>{done.map(b => <tr key={b.id}>
          <td>{clock(b.start_at, { day: "2-digit", month: "short" })}</td>
          <td>{legsLabel(b)}<small>{b.legs.map(l => l.score).filter(Boolean).join(" · ")}</small></td>
          <td>{odd(b.odds)}</td>
          <td className={b.status === "ganha" ? "pos" : b.status === "perdida" ? "neg" : ""}>{b.status === "anulada" ? "anulada" : signed(b.pnl ?? 0)}</td>
        </tr>)}</tbody></table></div>
    </section>}

    <p className="ap-foot">As chances vêm das próprias odds da Betclic, sem a margem e corrigidas pelo viés dos favoritos. O plano não vê o ao vivo. Regras e riscos: <Link href="/estrategia">ver a estratégia →</Link></p>
  </div>;
}

function legsLabel(b: Parlay): string { return b.legs.map(l => `${l.pick} ${odd(l.odds)}`).join(" + "); }
