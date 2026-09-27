"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { API, decimal } from "../../lib/api";
import { readSlip, SlipLeg, writeSlip } from "../../lib/betslip";

type Ticket = {kind: string; line_count: number; lines: {indices: number[]; decimal_odds: number; stake: number}[]; total_stake: number; max_gross_return: number; max_net_profit: number; same_bookmaker: boolean; provider_prices: boolean; note: string};
const types = [{id: "accumulator", title: "Combinada", copy: "Todas as seleções têm de ganhar."}, {id: "system", title: "Sistema k/N", copy: "Cobre todas as combinações com k seleções."}, {id: "round_robin", title: "Round robin", copy: "Duplas, triplas e restantes subconjuntos."}, {id: "single", title: "Simples", copy: "Uma seleção para comparação."}];

export default function Parlays() {
  const [legs, setLegs] = useState<SlipLeg[]>([]);
  const [kind, setKind] = useState("accumulator");
  const [systemSize, setSystemSize] = useState(2);
  const [stake, setStake] = useState("10");
  const [match, setMatch] = useState("");
  const [selection, setSelection] = useState("");
  const [odd, setOdd] = useState("");
  const [bookmaker, setBookmaker] = useState("");
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [error, setError] = useState("");
  const commonBooks = useMemo(() => {
    if (legs.length < 2 || legs.some(leg => leg.source !== "provider" || !leg.alternatives?.length)) return [];
    const now = Date.now();
    const books = new Set(legs[0].alternatives?.map(q => q.bookmaker) || []);
    return [...books].flatMap(book => {
      const choices = legs.map(leg => leg.alternatives?.find(q => q.bookmaker === book && now - new Date(q.observed_at).getTime() <= 6 * 3600000 && new Date(leg.start_at || "").getTime() > now));
      if (choices.some(q => !q)) return [];
      return [{book, odds: choices.reduce((value, q) => value * (q?.decimal_odds || 1), 1), choices}];
    }).sort((a, b) => b.odds - a.odds);
  }, [legs]);
  useEffect(() => { setLegs(readSlip()); }, []);
  useEffect(() => {
    setTicket(null); setError("");
    if (!legs.length || !Number.isFinite(Number(stake)) || Number(stake) <= 0) return;
    const controller = new AbortController();
    fetch(`${API}/api/parlay/calculate`, {method: "POST", headers: {"Content-Type": "application/json"}, signal: controller.signal,
      body: JSON.stringify({legs, kind, system_size: systemSize, total_stake: Number(stake)})})
      .then(async response => {const body = await response.json(); if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Bilhete inválido"); return body;})
      .then(setTicket).catch(err => {if (err.name !== "AbortError") setError(err.message || "Erro de cálculo");});
    return () => controller.abort();
  }, [legs, kind, stake, systemSize]);
  function update(next: SlipLeg[]) { setLegs(next); writeSlip(next); }
  function chooseBook(book: string) {
    update(legs.map(leg => {
      const quote = leg.alternatives?.find(q => q.bookmaker === book);
      return quote ? {...leg, id: quote.id, bookmaker: book, decimal_odds: quote.decimal_odds, observed_at: quote.observed_at} : leg;
    }));
  }
  function addManual(event: React.FormEvent) {
    event.preventDefault();
    const price = Number(odd);
    if (!match.trim() || !selection.trim() || !Number.isFinite(price) || price <= 1 || price > 1000) {setError("Indica jogo, seleção e odd decimal superior a 1."); return;}
    const key = `manual:${match.trim().toLowerCase()}`;
    if (legs.some(leg => leg.fixture_id === key || leg.match.trim().toLowerCase() === match.trim().toLowerCase())) {setError("Já existe uma seleção deste jogo no bilhete."); return;}
    if (legs.length >= 8) {setError("O máximo é oito seleções."); return;}
    update([...legs, {id: crypto.randomUUID(), fixture_id: key, match: match.trim(), selection: selection.trim(), decimal_odds: price, bookmaker: bookmaker.trim() || undefined, source: "manual"}]);
    setMatch(""); setSelection(""); setOdd(""); setBookmaker(""); setError("");
  }
  return <>
    <div className="page-heading"><div><h1>Combinadas<span className="heading-dot">.</span></h1><p>Constrói e compara bilhetes com até oito seleções. Resultado indicativo, sem envio para casas.</p></div><Link href="/hoje" className="button-primary">Escolher jogos +</Link></div>
    <div className="notice amber"><strong>Preço indicativo</strong><span>O produto das odds só estima o preço de uma combinada aceite. Preços de casas diferentes não formam uma oferta conjunta. Seleções do mesmo jogo exigem cotação específica da casa.</span></div>
    <div className="builder-layout"><div className="builder-main">
      <section className="panel"><div className="section-top"><div><h2>Tipo de bilhete</h2><p className="fine-print">Seleciona a estrutura antes de comparar o retorno máximo.</p></div></div><div className="bet-type-grid">{types.map(type => <button key={type.id} type="button" className={`bet-type ${kind === type.id ? "selected" : ""}`} onClick={() => setKind(type.id)}><strong>{type.title}</strong><span>{type.copy}</span></button>)}</div>{kind === "system" && <label className="inline-field">Tamanho de cada linha <select value={systemSize} onChange={e => setSystemSize(Number(e.target.value))}>{Array.from({length: Math.max(0, legs.length - 1)}, (_, i) => i + 2).map(size => <option key={size} value={size}>{size} de {legs.length}</option>)}</select></label>}</section>
      <section className="panel"><div className="section-top"><div><h2>Seleções <span className="count-badge">{legs.length}/8</span></h2><p className="fine-print">Cotações importadas aparecem com casa e hora. As entradas manuais são cenários.</p></div>{legs.length > 0 && <button className="quiet-button" onClick={() => update([])}>Limpar</button>}</div>
        {legs.length ? <div className="slip-leg-list">{legs.map((leg, index) => <div className="slip-leg" key={leg.id}><span className="leg-index">{index + 1}</span><div><strong>{leg.selection}</strong><span>{leg.match}</span><small>{leg.source === "provider" ? `${leg.bookmaker} · ${leg.observed_at ? new Date(leg.observed_at).toLocaleString("pt-PT", {timeZone: "Europe/Lisbon"}) : "hora desconhecida"}` : "Odd manual · cenário"}</small></div><strong className="leg-odd">{decimal(leg.decimal_odds)}</strong><button type="button" className="remove-leg" onClick={() => update(legs.filter(x => x.id !== leg.id))} aria-label={`Remover ${leg.selection}`}>×</button></div>)}</div> : <div className="slip-empty"><strong>Bilhete vazio</strong><p>Adiciona odds na agenda ou introduz um cenário manual abaixo.</p></div>}
      </section>
      {commonBooks.length > 0 && <section className="panel"><div className="section-top"><div><h2>Comparar por casa</h2><p className="fine-print">Odds observadas há menos de 6 horas para todas as seleções. O valor combinado continua sujeito à aceitação e regras da casa.</p></div></div><div className="book-list">{commonBooks.map(row => <div key={row.book}><strong>{row.book}</strong><span>Odd combinada {decimal(row.odds, 3)}</span><button className="button-secondary" onClick={() => chooseBook(row.book)}>Usar esta casa</button></div>)}</div></section>}
      <section className="panel"><div className="section-top"><div><h2>Adicionar cenário manual</h2><p className="fine-print">Útil para comparar estruturas. A odd não é validada nem fica ligada ao mercado.</p></div></div><form className="manual-form" onSubmit={addManual}><label>Jogo<input value={match} onChange={e => setMatch(e.target.value)} placeholder="Jogador A vs Jogador B" maxLength={140} /></label><label>Seleção<input value={selection} onChange={e => setSelection(e.target.value)} placeholder="Jogador A" maxLength={140} /></label><label>Odd decimal<input type="number" min="1.01" max="1000" step="0.01" value={odd} onChange={e => setOdd(e.target.value)} placeholder="1,85" /></label><label>Casa (opcional)<input value={bookmaker} onChange={e => setBookmaker(e.target.value)} placeholder="Nome da casa" maxLength={80} /></label><button className="button-secondary" type="submit">Adicionar cenário +</button></form></section>
    </div><aside className="ticket-panel panel"><h2>Resumo do bilhete</h2><label className="stake-field">Montante total (€)<input type="number" min="0.01" max="100000" step="0.01" value={stake} onChange={e => setStake(e.target.value)} /></label>{error && <p className="form-error" role="alert">{error}</p>}{ticket ? <><div className="ticket-line"><span>Linhas</span><strong>{ticket.line_count}</strong></div><div className="ticket-line"><span>Montante por linha</span><strong>{decimal(Number(stake) / ticket.line_count)} €</strong></div>{ticket.kind === "accumulator" && <div className="ticket-hero"><span>Odd combinada</span><strong>{decimal(ticket.lines[0]?.decimal_odds, 3)}</strong></div>}<div className="ticket-line"><span>Retorno máximo bruto</span><strong>{decimal(ticket.max_gross_return)} €</strong></div><div className="ticket-line"><span>Lucro máximo líquido</span><strong>{decimal(ticket.max_net_profit)} €</strong></div><p className="ticket-warning">{ticket.note}</p><p className="fine-print">Retorno máximo pressupõe que todas as linhas ganham. Um sistema pode pagar com apenas parte das seleções certas.</p>{ticket.line_count <= 28 && <details className="ticket-details"><summary>Ver {ticket.line_count} linhas</summary><div>{ticket.lines.map((line, i) => <div key={i}><span>{line.indices.map(index => index + 1).join(" + ")}</span><strong>{decimal(line.decimal_odds, 3)}</strong></div>)}</div></details>}</> : <p className="ticket-placeholder">Escolhe uma estrutura e adiciona as seleções necessárias para calcular o bilhete.</p>}<Link href="/hoje" className="text-link">Voltar à agenda →</Link></aside></div>
  </>;
}
