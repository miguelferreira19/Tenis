"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getJSON } from "../../lib/api";

type Result = {id: string; tour: string; tournament: string; start_at: string; player_a: string; player_b: string; score: string | null; winner: string | null; round: string | null; source_url: string};

export default function RecentResults() {
  const [data, setData] = useState<{items: Result[]; count: number} | null>(null);
  const [error, setError] = useState(false);
  const [query,setQuery]=useState("");
  const [tour,setTour]=useState("all");
  async function load(){setError(false);try{setData(await getJSON<{items:Result[];count:number}>("/api/recent?days=3"));}catch{setError(true);}}
  const visible=(data?.items || []).filter(item=>(tour==="all" || item.tour===tour) && `${item.player_a} ${item.player_b} ${item.tournament}`.toLocaleLowerCase("pt-PT").includes(query.toLocaleLowerCase("pt-PT")));
  useEffect(() => {void load();}, []);
  return <>
    <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/> MARCADOR ATUAL</div><h1>Resultados recentes<span className="heading-dot">.</span></h1><p>Últimos três dias, do mais recente para o mais antigo.</p></div><Link href="/hoje" className="button-primary">Próximos jogos ↗</Link></div>
    <div className="notice amber"><strong>Fonte separada</strong><span>Estes resultados vêm do marcador ESPN e não entram automaticamente no arquivo auditado nem no treino dos modelos.</span></div>
    {error && <div className="notice danger">O marcador não respondeu. <button className="button-secondary" onClick={() => void load()}>Tentar novamente</button></div>}
    {!data && !error && <div className="loading">A consultar resultados recentes…</div>}
    <div className="agenda-filters"><label className="agenda-search">Procurar jogador ou torneio<input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Ex.: Borges, Pequim…"/></label><label>Circuito<select value={tour} onChange={e=>setTour(e.target.value)}><option value="all">Todos os circuitos</option><option value="ATP">ATP</option><option value="WTA">WTA</option><option value="Masculino">Outros · masculino</option><option value="Feminino">Outros · feminino</option></select></label></div>
    {data && <section className="daily-section"><div className="section-top"><div><h2>{visible.length} jogos concluídos</h2><p className="fine-print">Horários de Lisboa. O resultado apresentado corresponde à fonte no momento da consulta.</p></div></div>
      {visible.length ? <div className="fixture-list">{visible.map(item => <article className="fixture-row" key={item.id}><div className="fixture-head"><div><small>{new Intl.DateTimeFormat("pt-PT", {day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Lisbon"}).format(new Date(item.start_at))} · {item.tour} · {item.tournament}</small><h3>{item.player_a} <em>vs</em> {item.player_b}</h3><p className="fine-print">{item.round || "Ronda por confirmar"}</p></div><strong className="recent-score">{item.score || "Concluído"}</strong></div><p className="fine-print">Vencedor: <strong>{item.winner || "por confirmar"}</strong></p><a className="text-link fixture-source" href={item.source_url} target="_blank" rel="noreferrer">Ver marcador de origem ↗</a></article>)}</div> : <div className="empty-state"><strong>Sem resultados para este intervalo e filtros</strong><p>Experimenta outro jogador ou circuito. A fonte pode ainda não ter publicado o resultado.</p></div>}
    </section>}
  </>;
}
