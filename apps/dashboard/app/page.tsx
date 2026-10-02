"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Autopilot, Bet, eur, loadAutopilot, odd, pc, useLocal, when } from "../lib/autopilot";
import { BankCurve } from "../components/BankCurve";

export default function Today() {
  const [data, setData] = useState<Autopilot | null>(null);
  const [error, setError] = useState("");
  const [now, setNow] = useState(0);
  const [myBank, setMyBank] = useLocal<number>("tq.bank", 100);
  const [placed, setPlaced] = useLocal<string[]>("tq.placed", []);

  useEffect(() => {
    loadAutopilot().then(setData).catch(e => setError(e.message));
    setNow(Date.now());
    const t = setInterval(() => setNow(Date.now()), 60000);
    return () => clearInterval(t);
  }, []);

  if (error) return <div className="ap-empty"><h1>Apostas de hoje</h1><p>{error}</p></div>;
  if (!data || !now) return <p role="status" className="ap-loading">A carregar o plano de hoje…</p>;

  // Stakes follow the paper bankroll; scale them to the user's own bankroll.
  const k = myBank > 0 ? myBank / data.start_bank : 1;
  const upcoming = data.bets.filter(b => b.status === "pendente" && new Date(b.start_at).getTime() > now)
    .sort((a, b) => a.start_at.localeCompare(b.start_at));
  const live = data.bets.filter(b => b.status === "pendente" && new Date(b.start_at).getTime() <= now);
  const done = data.bets.filter(b => b.status !== "pendente");
  const toPlace = upcoming.filter(b => !placed.includes(b.match_id));
  const total = toPlace.reduce((s, b) => s + b.stake * k, 0);
  const s = data.summary;
  const toggle = (id: string) => setPlaced(placed.includes(id) ? placed.filter(x => x !== id) : [...placed, id]);
  const next = new Date(new Date(data.generated_at).getTime() + 2 * 3600e3);

  return <div className="ap">
    <header className="ap-hero">
      <div>
        <p className="ap-kicker">Piloto automático · atualizado {new Date(data.generated_at).toLocaleString("pt-PT", { timeZone: "Europe/Lisbon", hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short" })}</p>
        <h1>{toPlace.length ? <>Hoje: {toPlace.length} {toPlace.length === 1 ? "aposta" : "apostas"}, {eur(total)} no total</> : upcoming.length ? "Tudo apostado. Agora é esperar." : "Hoje não há apostas."}</h1>
        <p className="ap-sub">{toPlace.length ? "Abre cada jogo na Betclic, aposta o montante indicado e marca como feito." :
          upcoming.length ? "Os resultados entram sozinhos depois dos jogos." :
          `Nenhum jogo cumpre as regras da estratégia. Próxima verificação perto das ${next.toLocaleTimeString("pt-PT", { timeZone: "Europe/Lisbon", hour: "2-digit", minute: "2-digit" })}.`}</p>
      </div>
      <label className="ap-bank">A tua banca (demo)
        <span><input type="number" min="1" step="1" inputMode="decimal" value={myBank}
          onChange={e => setMyBank(Number(e.target.value))} aria-describedby="bank-help" /> €</span>
        <small id="bank-help">Os montantes ajustam-se a este valor.</small>
      </label>
    </header>

    {!data.betclic_ok && <p className="ap-warn" role="alert">As odds da Betclic têm mais de 6 horas (o PC que as recolhe pode estar desligado). Confirma a odd na Betclic antes de apostar.</p>}

    {upcoming.length > 0 && <section aria-labelledby="h-now">
      <h2 id="h-now" className="ap-h2">Para apostar</h2>
      <ol className="ap-cards">{upcoming.map(b => <BetCard key={b.match_id} bet={b} k={k} now={now}
        done={placed.includes(b.match_id)} onToggle={() => toggle(b.match_id)} />)}</ol>
    </section>}

    {live.length > 0 && <section aria-labelledby="h-live">
      <h2 id="h-live" className="ap-h2">À espera do resultado</h2>
      <ul className="ap-list">{live.map(b => <li key={b.match_id}><span>{b.pick} <small>vs {b.side === "a" ? b.player_b : b.player_a}</small></span><span>{odd(b.odds)} · {eur(b.stake * k)}</span></li>)}</ul>
    </section>}

    <section className="ap-stats" aria-label="Resultado acumulado">
      <div><span>Banca do piloto</span><strong>{eur(data.bank.bank * k)}</strong><small>começou em {eur(data.start_bank * k)}</small></div>
      <div><span>Lucro / prejuízo</span><strong className={s.pnl >= 0 ? "pos" : "neg"}>{s.pnl >= 0 ? "+" : ""}{eur(s.pnl * k)}</strong><small>{s.bets ? `${pc(s.roi, 1)} do apostado` : "ainda sem apostas fechadas"}</small></div>
      <div><span>Acertos</span><strong>{s.bets ? `${s.won}/${s.bets}` : "—"}</strong><small>{s.bets ? pc(s.won / s.bets) : `esperado ≈ ${pc(data.backtest.test_flat?.betclic_proxy?.hit_rate)}`}</small></div>
    </section>

    {data.bank.curve.length > 1 && <section className="ap-panel"><h2 className="ap-h2">Evolução da banca</h2><BankCurve points={data.bank.curve.map(([d, v]) => [d, v * k])} /></section>}

    {done.length > 0 && <section aria-labelledby="h-hist">
      <h2 id="h-hist" className="ap-h2">Histórico</h2>
      <div className="ap-table"><table><thead><tr><th>Jogo</th><th>Aposta</th><th>Odd</th><th>Montante</th><th>Resultado</th></tr></thead>
        <tbody>{done.map(b => <tr key={b.match_id}>
          <td>{new Date(b.start_at).toLocaleDateString("pt-PT", { timeZone: "Europe/Lisbon", day: "2-digit", month: "short" })}<small>{b.competition}</small></td>
          <td>{b.pick}<small>vs {b.side === "a" ? b.player_b : b.player_a}{b.score ? ` · ${b.score}` : ""}</small></td>
          <td>{odd(b.odds)}</td><td>{eur(b.stake * k)}</td>
          <td className={b.status === "ganha" ? "pos" : b.status === "perdida" ? "neg" : ""}>{b.status === "anulada" ? "anulada" : `${(b.pnl ?? 0) >= 0 ? "+" : ""}${eur((b.pnl ?? 0) * k)}`}</td>
        </tr>)}</tbody></table></div>
    </section>}

    <p className="ap-foot">Probabilidades a partir das próprias odds da Betclic, corrigidas pelo viés dos favoritos. Regras, riscos e o que esperar: <Link href="/estrategia">ver a estratégia →</Link></p>
  </div>;
}

function BetCard({ bet: b, k, now, done, onToggle }: { bet: Bet; k: number; now: number; done: boolean; onToggle: () => void }) {
  const moved = b.last_odds && Math.abs(b.last_odds - b.odds) >= 0.02;
  return <li className={`ap-card${done ? " is-done" : ""}`}>
    <div className="ap-card-top"><span>{when(b.start_at, now)}</span><span>{b.competition}</span></div>
    <p className="ap-pick">Apostar em <strong>{b.pick}</strong></p>
    <p className="ap-vs">contra {b.side === "a" ? b.player_b : b.player_a}</p>
    <dl className="ap-nums">
      <div><dt>Montante</dt><dd>{eur(b.stake * k)}</dd></div>
      <div><dt>Odd mínima</dt><dd>{odd(b.odds)}</dd></div>
      <div><dt>Chance estimada</dt><dd>{pc(b.p)}</dd></div>
    </dl>
    {moved && <p className="ap-note">A odd mudou para {odd(b.last_odds!)}{b.last_odds! < b.odds ? " (abaixo da mínima: podes saltar esta)" : " (melhor para ti)"}.</p>}
    <div className="ap-actions">
      <a className="ap-btn" href={b.url} target="_blank" rel="noreferrer">Abrir na Betclic ↗</a>
      <label className="ap-check"><input type="checkbox" checked={done} onChange={onToggle} /> Já apostei</label>
    </div>
  </li>;
}
