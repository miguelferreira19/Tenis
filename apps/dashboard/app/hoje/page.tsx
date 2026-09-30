"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API, STATIC, apiUrl } from "../../lib/api";
import { readSlip, SlipLeg, writeSlip } from "../../lib/betslip";
import {Fixture, Offer, GameCard} from "../../components/GameCard";
import {compareFavorites} from "../../lib/agenda";

type Board = {date: string; items: Fixture[]; count: number; feed_configured: boolean; last_refresh: string | null; status: string; quote_max_age_hours: number; generated_at?: string};

// A snapshot pode ter horas: jogos que já começaram saem da lista.
function liveOnly(board: Board): Board {
  const items = board.items.filter(item => Date.parse(item.start_at) > Date.now());
  return {...board, items, count: items.length};
}

function localDay(offset = 0) {
  const date = new Date(Date.now() + offset * 86400000);
  return new Intl.DateTimeFormat("en-CA", {timeZone: "Europe/Lisbon", year: "numeric", month: "2-digit", day: "2-digit"}).format(date);
}

export default function Today() {
  const [day, setDay] = useState("upcoming");
  const [tour, setTour] = useState("all");
  const [query, setQuery] = useState("");
  const [onlyModel, setOnlyModel] = useState(false);
  const [order, setOrder] = useState("time");
  const requestId = useRef(0);
  const [board, setBoard] = useState<Board | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [slipCount, setSlipCount] = useState(0);
  useEffect(() => { setSlipCount(readSlip().length); }, []);
  const load = useCallback(async (value: string) => {
    if (!value) return;
    const id = ++requestId.current;
    setBusy(true); setError("");
    try {
      const path = value === "upcoming" ? "/api/upcoming?days=3" : `/api/daily?day=${encodeURIComponent(value)}`;
      let response: Response | undefined;
      for (let attempt = 0; attempt < 3; attempt++) {
        try { response = await fetch(apiUrl(path), {cache: "no-store"}); } catch { response = undefined; }
        if (response?.ok) break;
        if (attempt < 2) await new Promise(resolve => setTimeout(resolve, 700 * (attempt + 1)));
      }
      if (!response?.ok) throw new Error(`A agenda não respondeu (${response?.status || "sem ligação"}).`);
      const data: Board = await response.json();
      if (id === requestId.current) setBoard(liveOnly(data));
    } catch (err) { if (id === requestId.current) setError(err instanceof Error ? err.message : "Não foi possível carregar a agenda."); }
    finally { if (id === requestId.current) setBusy(false); }
  }, []);
  useEffect(() => { void load(day); }, [day, load]);
  useEffect(() => {const timer = setInterval(() => setBoard(current => current ? liveOnly(current) : current),60000); return () => clearInterval(timer);},[]);

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
  const visible = useMemo(() => (board?.items || []).filter(item =>
    (tour === "all" || item.tour === tour) && (!onlyModel || item.probability_a !== null) &&
    `${item.player_a} ${item.player_b} ${item.tournament}`.toLocaleLowerCase("pt-PT").includes(query.toLocaleLowerCase("pt-PT"))), [board,tour,onlyModel,query]);
  const groups = useMemo(() => {
    if (order === "favorite") return visible.length ? [["favorite", [...visible].sort(compareFavorites)] as [string, Fixture[]]] : [];
    const result = new Map<string, Fixture[]>();
    for (const item of visible) {
      const key = new Intl.DateTimeFormat("en-CA", {timeZone:"Europe/Lisbon",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(item.start_at));
      result.set(key,[...(result.get(key) || []),item]);
    }
    return [...result.entries()];
  },[visible,order]);
  return <>
    <div className="page-heading agenda-heading"><div><h1>O próximo encontro<span className="heading-dot">.</span></h1><p>Descobre quem joga, quando começa e a probabilidade de cada jogador.</p></div><Link href="/plano" className="button-secondary">Plano e cotações{slipCount ? ` · ${slipCount}` : ""}</Link></div>
    <div className="agenda-toolbar"><div className="day-tabs" aria-label="Dias da agenda"><button aria-pressed={day===localDay()} className={day===localDay() ? "selected" : ""} onClick={() => setDay(localDay())}>Hoje</button><button aria-pressed={day===localDay(1)} className={day===localDay(1) ? "selected" : ""} onClick={() => setDay(localDay(1))}>Amanhã</button><button aria-pressed={day==="upcoming"} className={day==="upcoming" ? "selected" : ""} onClick={() => setDay("upcoming")}>Próximos 3 dias</button></div><label>Escolher data<input type="date" value={day==="upcoming" ? "" : day} min={localDay()} max={localDay(STATIC ? 6 : 30)} onChange={e => e.target.value && setDay(e.target.value)}/></label><button className="quiet-button" disabled={busy} onClick={() => void load(day)} aria-label="Atualizar calendário">{busy ? "A atualizar…" : "↻ Atualizar"}</button></div>
    <div className="agenda-filters"><label className="agenda-search">Procurar jogador ou torneio<input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Ex.: Alcaraz, Pequim…"/></label><label>Circuito<select value={tour} onChange={e => setTour(e.target.value)}><option value="all">Todos os circuitos</option><option value="ATP">ATP</option><option value="WTA">WTA</option><option value="Masculino">Outros · masculino</option><option value="Feminino">Outros · feminino</option></select></label><label>Ordenar por<select value={order} onChange={e => setOrder(e.target.value)}><option value="time">Hora do encontro</option><option value="favorite">Maior probabilidade do favorito</option></select></label><label className="agenda-checkbox"><input type="checkbox" checked={onlyModel} onChange={e => setOnlyModel(e.target.checked)}/>Só jogos com probabilidade</label></div>
    {error && <div className="notice danger" role="alert"><span>{error}</span><button className="button-secondary" onClick={() => void load(day)} disabled={busy}>Tentar novamente</button></div>}
    {busy && !board && <div className="agenda-loading" role="status" aria-live="polite"><span/><span/><p>A procurar os próximos encontros…</p></div>}
    {board && <>
      <div className="agenda-summary" aria-live="polite"><p><strong>{visible.length} {visible.length===1 ? "encontro" : "encontros"}</strong>{query || tour!=="all" || onlyModel ? ` de ${board.count} no calendário` : " no calendário"} · {visible.filter(item => item.probability_a !== null).length} com estimativa</p><Link className="text-link" href="/recentes">Ver resultados recentes →</Link></div>
      <div className="agenda-note"><span aria-hidden="true">ⓘ</span><p>As duas probabilidades somam 100%. São estimativas exploratórias com histórico até maio de 2026, não garantias nem recomendações de aposta. <Link href="/modelos">Como são avaliadas →</Link></p></div>
      <div aria-busy={busy} className={`agenda-content ${busy ? "agenda-updating" : ""}`}>{groups.length ? groups.map(([date,items]) => <section className="agenda-day" key={date}><header><h2>{date==="favorite" ? "Favoritos com maior probabilidade" : date===localDay() ? "Hoje" : date===localDay(1) ? "Amanhã" : new Intl.DateTimeFormat("pt-PT",{weekday:"long",day:"numeric",month:"long",timeZone:"Europe/Lisbon"}).format(new Date(`${date}T12:00:00Z`))}</h2><span>{items.length} {items.length===1 ? "jogo" : "jogos"} · {order==="favorite" ? "probabilidade decrescente · sem estimativa no fim" : "horário de Lisboa"}</span></header><div className="game-grid">{items.map(item => <GameCard item={item} onAdd={add} key={item.id}/>)}</div></section>) : <div className="empty-state"><strong>{board.count ? "Nenhum encontro corresponde aos filtros" : "Sem próximos encontros neste intervalo"}</strong><p>{board.count ? "Tenta outro jogador ou mostra todos os circuitos." : "Os jogos podem já ter começado ou o calendário ainda não estar publicado. Experimenta amanhã ou os próximos três dias."}</p>{board.count ? <button className="button-secondary" onClick={() => {setQuery("");setTour("all");setOnlyModel(false);}}>Limpar filtros</button> : <button className="button-secondary" onClick={() => setDay(day==="upcoming" ? localDay(1) : "upcoming")}>{day==="upcoming" ? "Ver amanhã" : "Ver próximos 3 dias"}</button>}</div>}</div>
      <details className="research-details agenda-data"><summary>Atualização do calendário e cotações</summary><p>Calendário ESPN; horários sujeitos a confirmação. {board.generated_at ? `Snapshot de ${new Date(board.generated_at).toLocaleString("pt-PT",{timeZone:"Europe/Lisbon"})}.` : "O calendário é atualizado na consulta."}</p><p>{board.feed_configured ? "As cotações com mais de seis horas são excluídas." : "Sem cotações verificadas. Podes usar a calculadora com preços que introduzas."}</p>{!STATIC && board.feed_configured && <button className="button-secondary" disabled={busy} onClick={refresh}>Atualizar cotações</button>}<Link className="text-link" href="/dados">Consultar fontes →</Link></details>
    </>}
  </>;
}
