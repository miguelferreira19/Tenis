"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getJSON } from "../../lib/api";

type Status = {feed_configured: boolean; last_refresh: string | null; quote_max_age_hours: number};

export default function Markets() {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {getJSON<Status>("/api/daily").then(setStatus).catch(() => setError(true));}, []);
  return <><div className="page-heading"><div><h1>Mercados e odds<span className="heading-dot">.</span></h1><p>Estado da fonte atual, regras de qualidade e limites do backtest de apostas.</p></div></div>
    {error && <div className="notice danger">A API não está disponível.</div>}
    <div className="market-status-row"><div><span>FONTE ATUAL</span><strong>{status?.feed_configured ? "The Odds API ligada" : "Por configurar"}</strong></div><div><span>ÚLTIMA COTAÇÃO</span><strong>{status?.last_refresh ? new Date(status.last_refresh).toLocaleString("pt-PT", {timeZone: "Europe/Lisbon"}) : "Sem observações"}</strong></div><div><span>JANELA DE FRESCURA</span><strong>Até {status?.quote_max_age_hours || 6} horas</strong></div></div>
    <div className="notice amber"><strong>Limite dos dados</strong><span>As odds atuais permitem construir cenários diários. O arquivo de resultados não contém hora real de cada jogo, logo não valida ROI, CLV nem a execução histórica das apostas.</span></div>
    <div className="market-columns"><section className="panel"><h2>Como ligar a fonte</h2><p>Obtém uma chave na fonte, define <code>ODDS_API_KEY</code> no ambiente do servidor Python e reinicia a API. Depois, em <Link href="/hoje">Próximos jogos</Link>, escolhe «Atualizar odds».</p><p>Por omissão, a integração consulta até 12 competições ATP/WTA ativas, mercado vencedor e região europeia. A recolha é manual para limitar o consumo de créditos; a resposta da API informa quando a lista foi truncada.</p><a href="https://the-odds-api.com/sports/tennis-odds.html" target="_blank" rel="noreferrer">Cobertura oficial da fonte ↗</a></section><section className="panel"><h2>Regras de leitura</h2><ul><li>Cada preço mantém casa, seleção, hora observada e referência da fonte.</li><li>Só entram na agenda preços observados antes do início do jogo e há menos de 6 horas.</li><li>Um jogador só é associado ao arquivo quando o nome coincide sem ambiguidade.</li><li>As odds de uma combinada são indicativas até a casa aceitar o bilhete; a mesma casa deve cotar todas as pernas.</li></ul><Link href="/combinadas" className="text-link">Abrir construtor de combinadas →</Link></section></div>
    <section className="panel market-research"><h2>Fontes e investigação</h2><p>A comparação por casa segue a interação observada em ferramentas de comparação de odds e bilhetes. As regras de validação quantitativa e a análise das fontes estão documentadas no projeto.</p><a href="https://the-odds-api.com/liveapi/guides/v4/" target="_blank" rel="noreferrer">Documentação da API ↗</a><a href="https://www.actionnetwork.com/betting-calculators/parlay-calculator" target="_blank" rel="noreferrer">Calculadora de combinadas ↗</a></section>
  </>;
}

