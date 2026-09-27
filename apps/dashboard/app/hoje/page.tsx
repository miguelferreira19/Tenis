"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { API, decimal, pct } from "../../lib/api";
import { readSlip, SlipLeg, writeSlip } from "../../lib/betslip";

type Offer = {id: string; bookmaker: string; selection: string; decimal_odds: number; observed_at: string; source_ref: string; probability: number | null; fair_odds: number | null; model_price_edge: number | null; no_vig_market_probability: number | null};
type Fixture = {id: string; tour: string; tournament: string; start_at: string; player_a: string; player_b: string; probability_a: number | null; quality: {surface?: string; surface_known?: boolean; exact_player_match?: boolean; reason?: string; rank_a?: string; rank_b?: string; round?: string}; analysis?: Record<string, number | null>; source_url: string; offers: Offer[]; status: string};
type Board = {date: string; items: Fixture[]; count: number; feed_configured: boolean; last_refresh: string | null; status: string; quote_max_age_hours: number};

function localDay(offset = 0) {
  const date = new Date(Date.now() + offset * 86400000);
  return new Intl.DateTimeFormat("en-CA", {timeZone: "Europe/Lisbon", year: "numeric", month: "2-digit", day: "2-digit"}).format(date);
}

function clock(value: string) { return new Intl.DateTimeFormat("pt-PT", {weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Lisbon"}).format(new Date(value)); }

export default function Today() {
  const [day, setDay] = useState("upcoming");
  const [board, setBoard] = useState<Board | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [slipCount, setSlipCount] = useState(0);
  useEffect(() => { setSlipCount(readSlip().length); }, []);
  const load = useCallback(async (value: string) => {
    if (!value) return;
    setBusy(true); setError("");
    try {
      const path = value === "upcoming" ? "/api/upcoming?days=3" : `/api/daily?day=${encodeURIComponent(value)}`;
      let response: Response | undefined;
      for (let attempt = 0; attempt < 3; attempt++) {
        try { response = await fetch(`${API}${path}`, {cache: "no-store"}); } catch { response = undefined; }
        if (response?.ok) break;
        if (attempt < 2) await new Promise(resolve => setTimeout(resolve, 700 * (attempt + 1)));
      }
      if (!response?.ok) throw new Error(`A agenda não respondeu (${response?.status || "sem ligação"}).`);
      setBoard(await response.json());
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível carregar a agenda."); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { void load(day); }, [day, load]);
  const modelCount = useMemo(() => board?.items.filter(item => item.probability_a !== null).length || 0, [board]);

  async function refresh() {
    setBusy(true); setError("");
    try {
      const response = await fetch(`${API}/api/odds/refresh`, {method: "POST"});
      if (!response.ok) { const body = await response.json(); throw new Error(body.detail || "Erro ao atualizar odds."); }
      await load(day);
    } catch (err) { setError(err instanceof Error ? err.message : "Erro ao atualizar odds."); }
    finally { setBusy(false); }
  }
  function add(item: Fixture, offer: Offer) {
    const current = readSlip();
    if (current.some(leg => leg.fixture_id === item.id)) { setError("Já existe uma seleção deste jogo no bilhete."); return; }
    if (current.length >= 8) { setError("O bilhete aceita até oito seleções."); return; }
    const leg: SlipLeg = {id: offer.id, fixture_id: item.id, match: `${item.player_a} · ${item.player_b}`,
      selection: offer.selection, decimal_odds: offer.decimal_odds, bookmaker: offer.bookmaker,
      observed_at: offer.observed_at, start_at: item.start_at, source: "provider",
      alternatives: item.offers.filter(q => q.selection === offer.selection).map(q => ({id: q.id, bookmaker: q.bookmaker, decimal_odds: q.decimal_odds, observed_at: q.observed_at}))};
    writeSlip([...current, leg]); setSlipCount(current.length + 1); setError("");
  }
  return <>
    <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/> AGENDA ATUAL / ATP + WTA</div><h1>Próximos jogos<span className="heading-dot">.</span></h1><p>Calendário, contexto estatístico e preços observados para a tua análise.</p></div><Link href="/combinadas" className="button-primary">Calculadora · {slipCount}</Link></div>
    <div className="notice amber"><strong>Leitura crítica</strong><span>Calendário ESPN. Estimativas exploratórias com arquivo até maio de 2026; provas de outros níveis podem estar fora do domínio do modelo. Nenhum sinal de aposta aprovado.</span></div>
    <div className="daily-toolbar"><div className="day-tabs"><button type="button" className={day === localDay() ? "selected" : ""} onClick={() => setDay(localDay())}>Jogos de hoje</button><button type="button" className={day === "upcoming" ? "selected" : ""} onClick={() => setDay("upcoming")}>Próximos 3 dias</button><button type="button" className={day === localDay(1) ? "selected" : ""} onClick={() => setDay(localDay(1))}>Amanhã</button></div><label>Outra data <input type="date" value={day === "upcoming" ? "" : day} min={localDay()} max={localDay(30)} onChange={e => setDay(e.target.value)} /></label><button type="button" className="button-secondary" disabled={busy || !board?.feed_configured} onClick={refresh}>Atualizar odds</button></div>
    {error && <div className="notice danger" role="alert">{error}</div>}
    {busy && <div className="loading" role="status">A carregar jogos e cotações…</div>}
    {!busy && board && <>
      <div className="daily-summary"><div><strong>{board.count}</strong><span>jogos futuros</span></div><div><strong>{modelCount}</strong><span>com estimativa exploratória</span></div><div><strong>{board.items.reduce((n, item) => n + item.offers.length, 0)}</strong><span>odds recentes · até {board.quote_max_age_hours} h</span></div></div>
      {(day === localDay() || day === "upcoming") && <section className="daily-section"><div className="section-top"><div><h2>{day === localDay() ? "Leitura rápida · hoje" : "Leitura rápida · próximos encontros"}</h2><p className="fine-print">Jogador estatisticamente mais provável em cada confronto. Isto não é uma recomendação de aposta.</p></div></div>{board.items.length ? <div className="quick-list">{(day === "upcoming" ? board.items.filter(item => item.probability_a !== null).slice(0, 10) : board.items).map(item => { const p = item.probability_a; const likely = p == null ? null : p >= 0.5 ? item.player_a : item.player_b; return <div className="quick-row" key={item.id}><span>{clock(item.start_at)}<small>{item.tour} · {item.tournament}</small></span><strong>{item.player_a} <em>vs</em> {item.player_b}</strong><span className="quick-likely">{likely ? <>Mais provável: <b>{likely}</b></> : "Modelo indisponível"}</span><strong className="quick-percent">{p == null ? "—" : pct(Math.max(p, 1 - p))}</strong></div>; })}</div> : <div className="empty-state"><strong>Sem jogos futuros hoje</strong><p>Consulta «Próximos 3 dias» para ver encontros ainda disponíveis no calendário.</p></div>}</section>}
      {!board.feed_configured && <section className="panel setup-panel"><div><h2>Odds ainda não ligadas</h2><p>O calendário atualiza automaticamente. Para comparar preços reais, configura <code>ODDS_API_KEY</code> na API. Também podes usar a <Link href="/combinadas">calculadora</Link> com odds introduzidas por ti.</p><Link href="/mercados" className="text-link">Ver proveniência e limites →</Link></div></section>}
      {board.feed_configured && board.last_refresh && <p className="fine-print">Última observação na base: {new Date(board.last_refresh).toLocaleString("pt-PT", {timeZone: "Europe/Lisbon"})}. Cotações com mais de 6 horas não entram na agenda.</p>}
      <section className="daily-section"><div className="section-top"><div><h2>Jogos por ordem de início</h2><p className="fine-print">Horários de Lisboa. A superfície é assinalada quando a associação ao arquivo é clara.</p></div><Link href="/recentes" className="text-link">Resultados recentes ↗</Link></div>
        {board.items.length ? <div className="fixture-list">{board.items.map(item => <article className="fixture-row" key={item.id}><div className="fixture-head"><div><small>{clock(item.start_at)} Lisboa · {item.tour} · {item.tournament}</small><h3>{item.player_a} <em>vs</em> {item.player_b}</h3><p className="fine-print">{item.quality.round || "Ronda por confirmar"} · Cabeça de série {item.quality.rank_a || "—"} / {item.quality.rank_b || "—"}</p></div><span className="state-pill">{item.quality.surface && item.quality.surface !== "Unknown" ? item.quality.surface : "superfície por verificar"}</span></div>{item.probability_a !== null && <div className="fixture-prob"><span>Estimativa exploratória A / B</span><strong>{pct(item.probability_a)} / {pct(1 - item.probability_a)}</strong><div className="probability-bar"><div style={{width: `${Math.round(item.probability_a * 100)}%`}} /></div></div>}{item.analysis && <details className="fixture-analysis"><summary>Ver variáveis da análise</summary><div className="fixture-analysis-grid"><div><span>Elo geral</span><strong>{item.analysis.elo_a?.toFixed(0) || "—"} / {item.analysis.elo_b?.toFixed(0) || "—"}</strong></div><div><span>Elo na superfície</span><strong>{item.analysis.surface_elo_a?.toFixed(0) || "—"} / {item.analysis.surface_elo_b?.toFixed(0) || "—"}</strong></div><div><span>Forma recente</span><strong>{pct(item.analysis.form_a)} / {pct(item.analysis.form_b)}</strong></div><div><span>Serviço recente</span><strong>{pct(item.analysis.serve_a)} / {pct(item.analysis.serve_b)}</strong></div><div><span>Descanso, dias</span><strong>{item.analysis.rest_a ?? "—"} / {item.analysis.rest_b ?? "—"}</strong></div><div><span>Jogos em 30 dias</span><strong>{item.analysis.load_30d_a ?? "—"} / {item.analysis.load_30d_b ?? "—"}</strong></div></div></details>}{item.probability_a === null && <p className="fine-print">Sem estimativa: {item.quality.reason || "identificação dos jogadores por confirmar"}.</p>}{item.offers.length ? <div className="offer-list">{item.offers.map(offer => <div className="offer-row" key={offer.id}><span>{offer.selection}<small>{offer.bookmaker} · {new Date(offer.observed_at).toLocaleTimeString("pt-PT", {hour: "2-digit", minute: "2-digit", timeZone: "Europe/Lisbon"})}</small></span><strong>{decimal(offer.decimal_odds)}</strong><span>{offer.probability == null ? "sem modelo" : `${pct(offer.probability)} modelo`}</span><button className="button-secondary" onClick={() => add(item, offer)} aria-label={`Adicionar ${offer.selection} a ${decimal(offer.decimal_odds)}`}>Usar na calculadora</button></div>)}</div> : <p className="fine-print">Sem odds recentes verificadas para este jogo.</p>}<a className="text-link fixture-source" href={item.source_url} target="_blank" rel="noreferrer">Ver calendário de origem ↗</a></article>)}</div> : <div className="empty-state"><span>◷</span><strong>Sem jogos futuros disponíveis neste intervalo</strong><p>O calendário pode ainda não estar publicado ou a fonte pode estar temporariamente indisponível. Experimenta outra data.</p><Link href="/recentes">Ver resultados recentes →</Link></div>}
      </section>
    </>}
  </>;
}
