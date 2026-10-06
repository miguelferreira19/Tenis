import { Parlay, eur, odd, pc, signed, spc, when } from "../lib/autopilot";

/** Uma múltipla para fazer: as pernas, o montante e o que está em jogo. */
export function ParlayCard({ bet, stake, now, done, onToggle }:
  { bet: Parlay; stake: number; now: number; done: boolean; onToggle: () => void }) {
  const live = Math.round(bet.legs.reduce((o, l) => o * (l.last_odds ?? l.odds), 1) * 100) / 100;
  const moved = Math.abs(live - bet.odds) >= 0.02;
  return <li className={`ap-card${done ? " is-done" : ""}`}>
    <div className="ap-card-top">
      <span>{bet.legs.length === 1 ? "Simples" : `Múltipla de ${bet.legs.length}`} · odd {odd(bet.odds)}</span>
      <span>{when(bet.start_at, now)}</span>
    </div>
    <ul className="ap-legs">{bet.legs.map(l => <li key={l.match_id}>
      <div>
        <strong>{l.pick}</strong>
        <small>vs {l.side === "a" ? l.player_b : l.player_a}</small>
        <small>{l.competition} · {when(l.start_at, now)}</small>
        <a className="ap-link" href={l.url} target="_blank" rel="noreferrer" aria-label={`Abrir ${l.pick} na Betclic`}>Abrir na Betclic ↗</a>
      </div>
      <div className="ap-leg-odds"><b>{odd(l.odds)}</b><small>chance {pc(l.p)}</small><small>precisa {pc(1 / l.odds)}</small></div>
    </li>)}</ul>
    <dl className="ap-nums">
      <div><dt>Montante</dt><dd>{eur(stake)}</dd></div>
      <div><dt>Se ganhar</dt><dd>+{eur(stake * (bet.odds - 1))}</dd></div>
      <div><dt>Chance</dt><dd>{pc(bet.p)}</dd></div>
    </dl>
    <p className="ap-fine">Valor esperado {spc(bet.ev)}: em média {signed(stake * bet.ev)} por aposta. É a margem da casa.</p>
    {moved && <p className="ap-note">A odd total mudou para {odd(live)} (registada {odd(bet.odds)}){live < bet.odds ? ": está abaixo, confirma se ainda compensa." : ": melhor para ti."}</p>}
    <div className="ap-actions">
      <span className="ap-fine">Odd total mínima {odd(bet.odds)}</span>
      <label className="ap-check"><input type="checkbox" checked={done} onChange={onToggle} /> Já apostei</label>
    </div>
  </li>;
}
