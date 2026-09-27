"use client";

import { useEffect, useState } from "react";
import { day, getJSON, Overview } from "../../lib/api";

type Source = {id: string; source_url: string; sha256: string; row_count: number; quality: {accepted: number; invalid: number; future_excluded: number}; ingested_at: string};

export default function Data() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  useEffect(() => {getJSON<Overview>("/api/overview").then(setOverview).catch(() => {}); getJSON<{sources: Source[]}>("/api/data-sources").then(d => setSources(d.sources)).catch(() => {});}, []);
  const invalid = sources.reduce((sum, x) => sum + x.quality.invalid, 0);
  return <><div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/> PROVENIÊNCIA / QUALIDADE</div><h1>Dados e fontes<span className="heading-dot">.</span></h1><p>Cada ficheiro raw tem origem, checksum e contagem de registos. Os originais são preservados.</p></div><div className="heading-stamp">05 <span>/ 05</span></div></div>
    <div className="stats-grid data-stats"><div className="metric-card primary"><span className="metric-index">FICHEIROS</span><strong>{sources.length}</strong><span>arquivos raw fixados</span></div><div className="metric-card"><span className="metric-index">JOGOS</span><strong>{overview?.counts.matches.toLocaleString("pt-PT") ?? "—"}</strong><span>registos aceites</span></div><div className="metric-card"><span className="metric-index">EXCLUÍDOS</span><strong>{invalid}</strong><span>linhas inválidas</span></div><div className="metric-card"><span className="metric-index">ÚLTIMO EVENTO</span><strong className="date-value">{day(overview?.last_event_date)}</strong><span>início do torneio</span></div></div>
    <div className="notice amber"><strong>Licença e uso</strong><span>Dados de Jeff Sackmann / Tennis Abstract, espelhados por Aneeshers, licença CC BY-NC-SA 4.0. Esta instalação é para investigação não comercial. Verifica direitos adicionais antes de qualquer uso comercial.</span></div>
    <section className="panel"><div className="section-top"><div><span className="overline">MANIFESTO DE IMPORTAÇÃO</span><h2>Ficheiros e verificações</h2></div></div><div className="table-scroll"><table className="data-table source-table"><thead><tr><th>FONTE</th><th>REGISTOS</th><th>INVÁLIDOS</th><th>SHA-256</th><th></th></tr></thead><tbody>{sources.map(s => <tr key={s.id}><td>{s.source_url.match(/(atp|wta)_matches_\d{4}/)?.[0] || "arquivo"}</td><td className="number-cell">{s.row_count.toLocaleString("pt-PT")}</td><td className="number-cell">{s.quality.invalid}</td><td className="hash">{s.sha256.slice(0, 16)}…</td><td><a href={s.source_url} target="_blank" rel="noreferrer" aria-label="Abrir fonte original">↗</a></td></tr>)}</tbody></table></div></section>
    <section className="panel methodology"><div className="section-top"><div><span className="overline">LIMITAÇÕES ATUAIS</span><h2>O que falta para validar apostas</h2></div></div><div className="method-grid"><div><strong>Hora do encontro</strong><p>O ficheiro de resultados usa a data de início do torneio. A hora real de cada jogo deve vir de uma fonte própria.</p></div><div><strong>Odds e movimento</strong><p>Não há snapshots temporizados. Não é possível reconstruir o preço disponível no momento da decisão.</p></div><div><strong>Mercados além de vencedor</strong><p>O modelo v0.1 estima apenas o vencedor. Totais, handicaps e sets requerem simulação validada.</p></div><div><strong>Gates quantitativos</strong><p>Não há DSR, PBO, CPCV, testes nulos, custos ou paper tracking de estratégia porque ainda não existe série de apostas verificável.</p></div></div></section>
  </>;
}

