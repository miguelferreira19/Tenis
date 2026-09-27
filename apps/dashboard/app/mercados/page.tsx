import Link from "next/link";

export default function Markets() {
  return <><div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/> PREÇO / VALOR ESPERADO</div><h1>Mercados<span className="heading-dot">.</span></h1><p>A comparação com o mercado exige odds históricas com hora, seleção e bookmaker verificáveis.</p></div><div className="heading-stamp">03 <span>/ 05</span></div></div>
    <div className="notice amber"><strong>Scanner sem dados de mercado</strong><span>Não há feed de odds ligado. Nenhum EV, CLV, ROI ou sinal foi inferido a partir de preços inventados.</span></div>
    <div className="blocked-grid"><section className="panel blocked-card"><span className="blocked-number">01</span><h2>Odds com timestamp</h2><p>Recolher snapshots por jogo, mercado, seleção, casa e instante. Guardar a trajetória sem sobrescrever observações.</p><span className="state-pill">POR INTEGRAR</span></section><section className="panel blocked-card"><span className="blocked-number">02</span><h2>Hora real do jogo</h2><p>O arquivo atual indica apenas o começo do torneio. Uma odd só pode entrar num backtest depois de se conhecer a hora do jogo.</p><span className="state-pill">POR INTEGRAR</span></section><section className="panel blocked-card"><span className="blocked-number">03</span><h2>Backtest de execução</h2><p>Com histórico point-in-time, medir EV, CLV, custos, limites e estabilidade fora da amostra antes de qualquer sinal.</p><span className="state-pill">BLOQUEADO</span></section></div>
    <div className="panel market-note"><div><span className="overline">FERRAMENTA DE INVESTIGAÇÃO</span><h2>Testar uma cotação manual</h2><p>Em qualquer análise de jogo podes introduzir uma odd e obter a comparação matemática com a fair odd do modelo. O resultado é identificado como cenário hipotético.</p></div><Link href="/jogos" className="button-primary">Abrir arquivo de jogos ↗</Link></div>
  </>;
}

