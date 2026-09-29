"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { API, Match, day, decimal, getJSON, pct } from "../../../lib/api";

type Scenario = {probability: number; fair_odds: number; market_implied_probability: number; market_no_vig_probability: number | null; probability_edge: number | null; expected_value: number; note: string};

export default function GameDetail() {
  const params = useParams<{id: string}>();
  const [match, setMatch] = useState<Match | null>(null);
  const [error, setError] = useState(false);
  const [selection, setSelection] = useState("a");
  const [odds, setOdds] = useState("");
  const [opposing, setOpposing] = useState("");
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [scenarioError, setScenarioError] = useState("");
  useEffect(() => {getJSON<Match>(`/api/matches/${encodeURIComponent(decodeURIComponent(params.id))}`).then(setMatch).catch(() => setError(true));}, [params.id]);
  async function calculate(event: React.FormEvent) {
    event.preventDefault();
    if (!match) return;
    setScenarioError("");
    try {
      const response = await fetch(`${API}/api/price-scenario`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({match_id: match.id, selection, decimal_odds: Number(odds), opposing_odds: opposing ? Number(opposing) : null})});
      if (!response.ok) throw new Error("Introduz odds decimais superiores a 1.");
      setScenario(await response.json());
    } catch (err) {setScenario(null); setScenarioError(err instanceof Error ? err.message : "Erro no cálculo.");}
  }
  if (error) return <div className="empty-state"><strong>Jogo indisponível</strong><Link href="/jogos">Voltar aos jogos ↗</Link></div>;
  if (!match) return <div className="loading">A carregar análise…</div>;
  const player = match.features?.players || {};
  const rows: Array<[string, keyof typeof player, keyof typeof player, string]> = [
    ["Ranking anterior", "rank_a", "rank_b", ""], ["Elo global", "elo_a", "elo_b", ""], ["Elo na superfície", "surface_elo_a", "surface_elo_b", ""],
    ["Forma · últimos 10", "form_a", "form_b", "%"], ["Pontos ganhos no serviço", "serve_a", "serve_b", "%"],
    ["Pontos ganhos na resposta", "return_a", "return_b", "%"], ["Descanso entre torneios", "rest_a", "rest_b", " d"],
    ["Jogos anteriores", "matches_a", "matches_b", ""],
  ];
  const format = (value: number | string | null | undefined, unit: string) => typeof value !== "number" ? "—" : unit === "%" ? pct(value) : unit === " d" ? `${value} d` : decimal(value, Number.isInteger(value) ? 0 : 1);
  return <>
    <div className="breadcrumb"><Link href="/jogos">← JOGOS</Link><span>/</span>{match.tour}<span>/</span>{match.tournament}</div>
    <div className="match-hero"><div className="hero-meta"><span className="mini-tag accent">{match.tour}</span><span>{match.tournament}</span><span>·</span><span>{match.round || "—"}</span><span>·</span><span>{match.surface}</span></div><div className="hero-players"><div><small>JOGADOR A</small><h1>{match.player_a}</h1><span>Ranking no ficheiro {match.rank_a ?? "—"}</span></div><strong>VS</strong><div><small>JOGADOR B</small><h1>{match.player_b}</h1><span>Ranking no ficheiro {match.rank_b ?? "—"}</span></div></div><div className="hero-foot"><span>Início do torneio: {day(match.event_date)}</span><span>Resultado observado: <b>{match.winner}</b> · {match.score || "—"}</span></div></div>
    <div className="notice amber"><strong>Previsão reconstruída para investigação</strong><span>As variáveis usam apenas torneios anteriores a {day(match.event_date)}. O arquivo não contém a hora exata deste encontro. Sem odds históricas verificadas, não existe sinal ou EV real.</span></div>
    <section className="probability-section"><div className="section-top"><div><span className="overline">01 / PREVISÃO E PREÇO JUSTO</span><h2>Distribuição do modelo</h2></div><span className="state-pill test">{match.split === "test_oos" ? "TESTE OOS" : match.split?.toUpperCase() || "SEM PREVISÃO"}</span></div>
      {match.probability_a == null ? <div className="empty-state">Sem previsão para este período.</div> : <><div className="probability-bar"><div style={{width: `${match.probability_a * 100}%`}} /></div><div className="probability-grid"><div><span>{match.player_a}</span><strong>{pct(match.probability_a)}</strong><small>FAIR ODD {decimal(match.fair_odds_a)}</small></div><div><span>{match.player_b}</span><strong>{pct(1 - match.probability_a)}</strong><small>FAIR ODD {decimal(match.fair_odds_b)}</small></div></div><div className="model-id">MODELO {match.model_version} · AS-OF {match.as_of?.slice(0, 10) ?? "—"} UTC</div></>}
    </section>
    <div className="detail-grid"><section className="panel"><div className="section-top"><div><span className="overline">02 / ESTADO PRÉ-TORNEIO</span><h2>Comparação dos jogadores</h2></div></div><div className="comparison-head"><span>VARIÁVEL</span><span>{match.player_a}</span><span>{match.player_b}</span></div>{rows.map(([label, a, b, unit]) => <div className="comparison-row" key={label}><span>{label}</span><strong>{format(player[a], unit)}</strong><strong>{format(player[b], unit)}</strong></div>)}<p className="panel-note">Estas são variáveis de entrada observáveis. A tabela não atribui contribuições causais nem pontos percentuais a cada fator.</p></section>
      <section className="panel"><div className="section-top"><div><span className="overline">03 / CENÁRIO DE PREÇO</span><h2>Comparar uma odd</h2></div></div><p className="panel-copy">Introduz um preço decimal para estudar a diferença matemática entre modelo e mercado. Não é uma cotação observada.</p><form onSubmit={calculate} className="price-form"><label>Seleção<select value={selection} onChange={e => {setSelection(e.target.value); setScenario(null);}}><option value="a">{match.player_a}</option><option value="b">{match.player_b}</option></select></label><label>Odd decimal<input type="number" min="1.01" max="1000" step="0.01" required placeholder="ex. 1,90" value={odds} onChange={e => setOdds(e.target.value)} /></label><label>Odd oposta <small>(para no-vig)</small><input type="number" min="1.01" max="1000" step="0.01" placeholder="opcional" value={opposing} onChange={e => setOpposing(e.target.value)} /></label><button type="submit" className="button-primary" disabled={match.probability_a == null}>Calcular cenário ↗</button></form>{scenarioError && <p className="form-error">{scenarioError}</p>}{scenario && <div className="scenario-result"><div><span>Probabilidade modelo</span><strong>{pct(scenario.probability)}</strong></div><div><span>Fair odd</span><strong>{decimal(scenario.fair_odds)}</strong></div><div><span>Probabilidade implícita</span><strong>{pct(scenario.market_implied_probability)}</strong></div><div><span>Probabilidade no-vig</span><strong>{pct(scenario.market_no_vig_probability)}</strong></div><div className="scenario-ev"><span>EV matemático</span><strong>{pct(scenario.expected_value)}</strong></div><p>{scenario.note}</p></div>}</section></div>
    {!!match.odds_history?.length && <section className="panel audit-panel"><div className="section-top"><div><span className="overline">04 / ODDS IMPORTADAS</span><h2>Snapshots sem elegibilidade temporal</h2></div></div><p className="panel-copy">Existem cotações importadas, mas falta a hora real deste jogo. Não são usadas para EV histórico, CLV ou backtest.</p><div className="table-scroll"><table className="data-table"><thead><tr><th>BOOKMAKER</th><th>SELEÇÃO</th><th>ODD</th><th>OBSERVADO EM UTC</th><th>REFERÊNCIA</th></tr></thead><tbody>{match.odds_history.map((item, i) => <tr key={i}><td>{item.bookmaker}</td><td>{item.selection_id === match.player_a_id ? match.player_a : match.player_b}</td><td className="number-cell">{decimal(item.decimal_odds)}</td><td>{item.observed_at}</td><td>{item.source_ref}</td></tr>)}</tbody></table></div></section>}
    <section className="panel audit-panel"><div className="section-top"><div><span className="overline">05 / RASTREABILIDADE</span><h2>Dados e limitações</h2></div></div><div className="audit-grid"><div><span>Fonte</span><a href={match.source_url} target="_blank" rel="noreferrer">Arquivo original ↗</a></div><div><span>Precisão da data</span><strong>Início do torneio</strong></div><div><span>Amostra de serviço A / B</span><strong>{match.quality?.serve_sample_a ?? "—"} / {match.quality?.serve_sample_b ?? "—"} jogos</strong></div><div><span>Odds históricas</span><strong>{match.odds_history?.length ? `${match.odds_history.length} snapshots não elegíveis` : "Não disponíveis"}</strong></div><div><span>Estado do modelo</span><strong>Investigação</strong></div><div><span>Mercados simulados</span><strong>Não disponíveis</strong></div></div></section>
  </>;
}

