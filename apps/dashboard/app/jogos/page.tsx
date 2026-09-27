"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { MatchTable } from "../../components/MatchTable";
import { Match, getJSON } from "../../lib/api";

export default function Games() {
  const [tour, setTour] = useState("");
  const [surface, setSurface] = useState("");
  const [year, setYear] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{items: Match[]; total: number} | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => { const timer = setTimeout(() => { setQuery(search); setOffset(0); }, 280); return () => clearTimeout(timer); }, [search]);
  useEffect(() => {
    const params = new URLSearchParams({limit: "40", offset: String(offset)});
    if (tour) params.set("tour", tour);
    if (surface) params.set("surface", surface);
    if (year) params.set("year", year);
    if (query) params.set("search", query);
    getJSON<{items: Match[]; total: number}>(`/api/matches?${params}`).then(d => {setData(d); setError(false);}).catch(() => setError(true));
  }, [tour, surface, year, query, offset]);
  return <>
    <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/> BASE HISTÓRICA / ATP + WTA</div><h1>Arquivo histórico<span className="heading-dot">.</span></h1><p>Resultados usados na investigação dos modelos, por data decrescente.</p></div></div>
    <div className="notice amber"><strong>Dados históricos</strong><span>Este arquivo termina em maio de 2026. Para jogos ainda por disputar e resultados desta semana, usa as áreas atuais.</span><Link href="/hoje">Próximos jogos ↗</Link></div>
    <div className="filters"><label className="search-field"><span>⌕</span><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Jogador ou torneio" aria-label="Pesquisar jogador ou torneio" /></label><select value={tour} onChange={e => {setTour(e.target.value); setOffset(0);}} aria-label="Circuito"><option value="">Todos os circuitos</option><option>ATP</option><option>WTA</option></select><select value={surface} onChange={e => {setSurface(e.target.value); setOffset(0);}} aria-label="Superfície"><option value="">Todas as superfícies</option><option>Hard</option><option>Clay</option><option>Grass</option></select><select value={year} onChange={e => {setYear(e.target.value); setOffset(0);}} aria-label="Ano"><option value="">Todos os anos</option>{Array.from({length: 12}, (_, i) => 2026 - i).map(y => <option key={y}>{y}</option>)}</select></div>
    <div className="table-section"><div className="section-top"><div><span className="overline">RESULTADOS HISTÓRICOS</span><h2>{data?.total.toLocaleString("pt-PT") ?? "—"} jogos</h2></div><span className="muted-label">Probabilidade A = primeira jogadora / primeiro jogador</span></div>{error ? <div className="empty-state">API indisponível.</div> : <MatchTable items={data?.items ?? []} />}</div>
    <div className="pagination"><span>{data ? `${offset + 1}–${Math.min(offset + 40, data.total)} de ${data.total.toLocaleString("pt-PT")}` : "—"}</span><div><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 40))}>← Anterior</button><button disabled={!data || offset + 40 >= data.total} onClick={() => setOffset(offset + 40)}>Seguinte →</button></div></div>
    <p className="fine-print">Os resultados são observados. As probabilidades foram reconstruídas com informação de torneios anteriores e estão classificadas por divisão temporal.</p>
  </>;
}

