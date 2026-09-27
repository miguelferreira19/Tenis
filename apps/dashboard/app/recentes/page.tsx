"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getJSON } from "../../lib/api";

type Result = {id: string; tour: string; tournament: string; start_at: string; player_a: string; player_b: string; score: string | null; winner: string | null; round: string | null; source_url: string};

export default function RecentResults() {
  const [data, setData] = useState<{items: Result[]; count: number} | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => { getJSON<{items: Result[]; count: number}>("/api/recent?days=3").then(setData).catch(() => setError(true)); }, []);
  return <>
    <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/> MARCADOR ATUAL</div><h1>Resultados recentes<span className="heading-dot">.</span></h1><p>Últimos três dias, do mais recente para o mais antigo.</p></div><Link href="/hoje" className="button-primary">Próximos jogos ↗</Link></div>
    <div className="notice amber"><strong>Fonte separada</strong><span>Estes resultados vêm do marcador ESPN e não entram automaticamente no arquivo auditado nem no treino dos modelos.</span></div>
    {error && <div className="notice danger">O marcador não respondeu. Tenta novamente mais tarde.</div>}
    {!data && !error && <div className="loading">A consultar resultados recentes…</div>}
    {data && <section className="daily-section"><div className="section-top"><div><h2>{data.count} jogos concluídos</h2><p className="fine-print">Horários de Lisboa. O resultado apresentado corresponde à fonte no momento da consulta.</p></div></div>
      {data.items.length ? <div className="fixture-list">{data.items.map(item => <article className="fixture-row" key={item.id}><div className="fixture-head"><div><small>{new Intl.DateTimeFormat("pt-PT", {day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Lisbon"}).format(new Date(item.start_at))} · {item.tour} · {item.tournament}</small><h3>{item.player_a} <em>vs</em> {item.player_b}</h3><p className="fine-print">{item.round || "Ronda por confirmar"}</p></div><strong className="recent-score">{item.score || "Concluído"}</strong></div><p className="fine-print">Vencedor: <strong>{item.winner || "por confirmar"}</strong></p><a className="text-link fixture-source" href={item.source_url} target="_blank" rel="noreferrer">Ver marcador de origem ↗</a></article>)}</div> : <div className="empty-state"><strong>Sem resultados concluídos nestes três dias</strong><p>A fonte pode ainda não ter publicado jogos ou estar temporariamente indisponível.</p></div>}
    </section>}
  </>;
}
