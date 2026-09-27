import Link from "next/link";
import { Match, day, decimal, pct } from "../lib/api";

export function MatchTable({ items, compact = false }: {items: Match[]; compact?: boolean}) {
  if (!items.length) return <div className="empty-state"><span>∅</span><strong>Sem jogos para estes filtros</strong><p>Altera os filtros ou importa dados históricos.</p></div>;
  return <div className="table-scroll"><table className="data-table">
    <thead><tr><th>JOGO / TORNEIO</th><th>CIRCUITO</th><th>SUPERFÍCIE</th><th>INÍCIO</th><th>PROB. A</th><th>FAIR A</th><th>ESTADO</th><th></th></tr></thead>
    <tbody>{items.map(match => <tr key={match.id}>
      <td className="match-cell"><Link href={`/jogos/${encodeURIComponent(match.id)}`}><strong>{match.player_a} <em>vs</em> {match.player_b}</strong></Link><span>{match.tournament} · {match.round || "—"}</span></td>
      <td><span className="mini-tag">{match.tour}</span></td>
      <td>{match.surface || "—"}</td>
      <td>{day(match.event_date)}</td>
      <td className="number-cell">{pct(match.probability_a)}</td>
      <td className="number-cell">{decimal(match.fair_odds_a)}</td>
      <td><span className={`state-pill ${match.split === "test_oos" ? "test" : ""}`}>{match.split === "test_oos" ? "TESTE OOS" : match.split === "validation" ? "VALIDAÇÃO" : match.split === "calibration" ? "CALIBRAÇÃO" : "SEM MODELO"}</span></td>
      <td><Link className="row-link" href={`/jogos/${encodeURIComponent(match.id)}`} aria-label={`Abrir análise de ${match.player_a} contra ${match.player_b}`}>↗</Link></td>
    </tr>)}</tbody>
  </table></div>;
}

