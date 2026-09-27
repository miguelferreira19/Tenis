"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { MatchTable } from "../../components/MatchTable";
import { Match, Overview, day, decimal, getJSON, pct } from "../../lib/api";

export default function Home() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [error, setError] = useState(false);
  useEffect(() => {
    Promise.all([getJSON<Overview>("/api/overview"), getJSON<{items: Match[]}>("/api/matches?limit=8")])
      .then(([a, b]) => { setOverview(a); setMatches(b.items); }).catch(() => setError(true));
  }, []);
  return <>
    <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/> TERMINAL / VISÃO GERAL</div><h1>Inteligência de jogo<span className="heading-dot">.</span></h1><p>Resultados históricos, probabilidades antes do torneio e qualidade do modelo.</p></div><div className="heading-stamp">01 <span>/ 05</span></div></div>
    {error && <div className="notice danger">A API não está disponível. Inicia o serviço local conforme o README do projeto.</div>}
    <div className="notice amber"><strong>Investigação · sem sinais aprovados</strong><span>Não existem odds históricas temporizadas nesta instalação. EV, CLV e ROI permanecem indisponíveis.</span><Link href="/mercados">Ver estado dos mercados ↗</Link></div>
    <section className="stats-grid" aria-label="Indicadores principais">
      <div className="metric-card primary"><span className="metric-index">01 / COBERTURA</span><strong>{overview?.counts.matches.toLocaleString("pt-PT") ?? "—"}</strong><span>jogos históricos importados</span><div className="metric-foot">ATP + WTA <b>↗</b></div></div>
      <div className="metric-card"><span className="metric-index">02 / MODELO</span><strong>{overview?.selected_family?.toUpperCase() ?? "—"}</strong><span>selecionado na validação 2023</span><div className="metric-foot">Treino até 2021 · calibração 2022</div></div>
      <div className="metric-card"><span className="metric-index">03 / TESTE FORA DA AMOSTRA</span><strong>{decimal(overview?.test_oos?.brier, 4)}</strong><span>Brier score · 2024–2026</span><div className="metric-foot">N = {overview?.test_oos?.n.toLocaleString("pt-PT") ?? "—"}</div></div>
      <div className="metric-card"><span className="metric-index">04 / PREÇO DE MERCADO</span><strong>—</strong><span>odds verificadas</span><div className="metric-foot">Dados de mercado por integrar</div></div>
    </section>
    <div className="content-grid">
      <section className="panel coverage-panel"><div className="section-top"><div><span className="overline">COBERTURA DE DADOS</span><h2>O que a plataforma sabe</h2></div><Link href="/dados" className="text-link">Auditoria de fontes ↗</Link></div>
        <div className="coverage-items"><div><span>Jogadores</span><strong>{overview?.counts.players.toLocaleString("pt-PT") ?? "—"}</strong><i className="coverage-bar"><b style={{width: "100%"}}/></i></div><div><span>Torneios</span><strong>{overview?.counts.tournaments.toLocaleString("pt-PT") ?? "—"}</strong><i className="coverage-bar"><b style={{width: "78%"}}/></i></div><div><span>Ficheiros raw</span><strong>{overview?.raw_files ?? "—"}</strong><i className="coverage-bar"><b style={{width: "64%"}}/></i></div><div><span>Odds com timestamp</span><strong>{overview?.counts.odds_snapshots ?? "—"}</strong><i className="coverage-bar"><b style={{width: "0%"}}/></i></div></div>
        <div className="panel-note">Período disponível: {day(overview?.first_event_date)} — {day(overview?.last_event_date)}. A data é a do início do torneio.</div>
      </section>
      <section className="panel model-panel"><div className="section-top"><div><span className="overline">SAÚDE DO MODELO</span><h2>Previsão, não promessa</h2></div><span className="small-lamp">● RESEARCH</span></div>
        <div className="model-metric"><span>Brier · validação</span><strong>{decimal(overview?.validation?.brier, 4)}</strong></div>
        <div className="model-metric"><span>Log loss · teste OOS</span><strong>{decimal(overview?.test_oos?.log_loss, 4)}</strong></div>
        <div className="model-metric"><span>ECE · teste OOS</span><strong>{decimal(overview?.test_oos?.ece_10, 4)}</strong></div>
        <div className="model-metric"><span>Taxa de acerto · teste OOS</span><strong>{pct(overview?.test_oos?.accuracy)}</strong></div>
        <Link href="/modelos" className="panel-action">Abrir comparação de modelos <span>↗</span></Link>
      </section>
    </div>
    <section className="table-section"><div className="section-top"><div><span className="overline">ARQUIVO / ÚLTIMOS REGISTOS</span><h2>Jogos analisados</h2></div><Link href="/jogos" className="text-link">Explorar todos ↗</Link></div><MatchTable items={matches} compact /></section>
  </>;
}

