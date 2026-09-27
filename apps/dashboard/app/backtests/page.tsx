"use client";

import { useEffect, useState } from "react";
import { decimal, getJSON, pct } from "../../lib/api";

type Metrics = {n: number; brier: number; log_loss: number; ece_10: number; accuracy: number};
type Backtest = {model_version: string; overall: Metrics; by_year: Record<string, Metrics>; by_tour: Record<string, Metrics>; by_surface: Record<string, Metrics>; reliability: {from: number; to: number; n: number; forecast_mean: number | null; observed_rate: number | null}[]; challenger_vs_frozen_v3: {n: number; brier_improvement_right: number; bootstrap_95: number[]; n_tournaments: number} | null; caveat: string};

export default function Backtests() {
  const [report, setReport] = useState<Backtest | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {getJSON<Backtest>("/api/backtest/predictions").then(setReport).catch(() => setError("O relatório ainda não foi gerado ou a API está indisponível."));}, []);
  return <>
    <div className="page-heading"><div><h1>Backtests<span className="heading-dot">.</span></h1><p>Desempenho temporal das probabilidades, por ano, circuito e superfície.</p></div></div>
    <div className="notice amber"><strong>Âmbito</strong><span>Este é um backtest de previsões. Sem odds históricas pré-jogo com hora real não há backtest de apostas, ROI ou CLV.</span></div>
    {error && <div className="notice danger" role="alert">{error}</div>}
    {!report && !error && <div className="loading">A carregar o relatório…</div>}
    {report && <><div className="backtest-strip"><div><span>Jogos OOS</span><strong>{report.overall.n.toLocaleString("pt-PT")}</strong></div><div><span>Brier</span><strong>{decimal(report.overall.brier, 4)}</strong></div><div><span>Log loss</span><strong>{decimal(report.overall.log_loss, 4)}</strong></div><div><span>Calibração ECE</span><strong>{pct(report.overall.ece_10)}</strong></div></div>
      <section className="panel backtest-section"><h2>Ano a ano</h2><p className="fine-print">O modelo foi selecionado pela validação de 2023. Estes anos são apenas diagnóstico após a seleção.</p><div className="table-scroll"><table className="data-table backtest-table"><thead><tr><th>Ano</th><th>Jogos</th><th>Brier ↓</th><th>Log loss ↓</th><th>ECE ↓</th><th>Acerto</th></tr></thead><tbody>{Object.entries(report.by_year).map(([year, m]) => <tr key={year}><td>{year}</td><td>{m.n.toLocaleString("pt-PT")}</td><td>{decimal(m.brier, 4)}</td><td>{decimal(m.log_loss, 4)}</td><td>{pct(m.ece_10)}</td><td>{pct(m.accuracy)}</td></tr>)}</tbody></table></div></section>
      <div className="backtest-pair"><section className="panel backtest-section"><h2>Por circuito</h2>{Object.entries(report.by_tour).map(([name, m]) => <div className="backtest-row" key={name}><strong>{name}</strong><span>{m.n.toLocaleString("pt-PT")} jogos</span><span>Brier {decimal(m.brier, 4)}</span></div>)}<h2 className="backtest-subtitle">Por superfície</h2>{Object.entries(report.by_surface).map(([name, m]) => <div className="backtest-row" key={name}><strong>{name}</strong><span>{m.n.toLocaleString("pt-PT")} jogos</span><span>Brier {decimal(m.brier, 4)}</span></div>)}</section><section className="panel backtest-section"><h2>Calibração por intervalo</h2><p className="fine-print">A barra clara representa a frequência observada de vitórias; a marca indica a previsão média. Intervalos com pouca amostra exigem cautela.</p><div className="reliability-list">{report.reliability.map(bin => <div className="reliability-row" key={bin.from}><span>{Math.round(bin.from * 100)}–{Math.round(bin.to * 100)}%</span><div className="reliability-track"><i style={{width: `${(bin.observed_rate || 0) * 100}%`}} /><b style={{left: `${(bin.forecast_mean || 0) * 100}%`}} /></div><small>{bin.n}</small></div>)}</div></section></div>
      {report.challenger_vs_frozen_v3 && <section className="panel backtest-section"><h2>Variáveis novas face ao modelo congelado</h2><p>Diferença média de Brier a favor do candidato: <strong>{decimal(report.challenger_vs_frozen_v3.brier_improvement_right, 6)}</strong>. Intervalo bootstrap por torneio: <strong>{decimal(report.challenger_vs_frozen_v3.bootstrap_95[0], 6)} a {decimal(report.challenger_vs_frozen_v3.bootstrap_95[1], 6)}</strong> ({report.challenger_vs_frozen_v3.n_tournaments} torneios).</p><p className="fine-print">As novas variáveis foram propostas depois de consultar resultados anteriores. O teste 2024+ já não é um holdout intocado; a confirmação requer novos jogos futuros.</p></section>}
      <p className="fine-print">{report.caveat} Versão: {report.model_version}</p>
    </>}
  </>;
}
