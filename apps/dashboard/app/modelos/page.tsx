"use client";
import {useEffect, useState} from "react";
import {Metrics, decimal, getJSON} from "../../lib/api";
import {Analysis, ResearchDashboard} from "../../components/ResearchDashboard";

type Report = Record<string, unknown> & {research_analysis?: Analysis};

export default function Models() {
  const [report,setReport]=useState<Report | null>(null);
  const [error,setError]=useState(false);
  const [busy,setBusy]=useState(true);
  async function load() {setBusy(true); setError(false); try {setReport(await getJSON<Report>("/api/models"));} catch {setError(true);} finally {setBusy(false);}}
  useEffect(() => {void load();},[]);
  return <><div className="page-heading research-heading"><div><h1>Modelos e evidência<span className="heading-dot">.</span></h1><p>Compara hipóteses, mede o erro e acompanha o que ainda precisa de confirmação.</p></div></div>
    {error && <div className="notice danger" role="alert"><span>Não foi possível carregar os resultados.</span><button className="button-secondary" onClick={() => void load()} disabled={busy}>Tentar novamente</button></div>}
    {busy && !report && <div className="research-loading" role="status" aria-live="polite"><span/>A carregar a comparação e a proveniência…</div>}
    {report?.research_analysis && <ResearchDashboard analysis={report.research_analysis}/>}
    {!busy && !error && !report?.research_analysis && <div className="empty-state"><strong>A análise de investigação ainda não está disponível</strong><p>Os modelos anteriores podem ser consultados abaixo. A próxima atualização incluirá as experiências completas.</p></div>}
    <details className="research-details research-legacy"><summary>Comparação original: Elo, logística e XGBoost</summary><p>Seleção original em 2023; treino 2015–2021 e calibração em 2022. Este protocolo difere das origens móveis acima.</p><div className="table-scroll"><table className="data-table research-table"><thead><tr><th scope="col">Família</th><th scope="col">Brier · seleção 2023</th><th scope="col">Brier · diagnóstico</th></tr></thead><tbody>{["elo","logistic","xgboost"].map(name => {const model=report?.[name] as {validation?: Metrics; test_oos?: Metrics} | undefined; return <tr key={name}><th scope="row">{name==="elo" ? "Elo" : name==="logistic" ? "Logística" : "XGBoost"}</th><td>{decimal(model?.validation?.brier,6)}</td><td>{decimal(model?.test_oos?.brier,6)}</td></tr>;})}</tbody></table></div></details>
  </>;
}
