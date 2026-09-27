# Roadmap de implementação

Estado em 27-09-2026. O plano completo do utilizador está preservado em `tennis_quant_betting_platform.md`.

| Ordem do plano | Componente | Estado | Critério para avançar |
|---|---|---|---|
| 1–5 | Arquitetura de dados, resultados, validação, BD e framework temporal | Implementado no v0.1; PostgreSQL não testado nesta máquina | Obter horas reais de jogos e testar PostgreSQL |
| 6–8 | Features, Elo e modelo logístico | Candidato v4 com serviço/resposta por superfície e carga 30 dias; sem holdout novo | Confirmar prospectivamente e avaliar ajuste ao adversário |
| 9–10 | XGBoost e calibração | Backtest anual, por circuito e superfície; refit operacional em investigação | Acompanhar deriva e calibração com dados novos |
| 11 | Simulação ponto → jogo → set → encontro | Pendente | Dados de pontos/serviço adequados e validação OOS |
| 12–14 | Odds, fair odds e EV | Adaptador atual e agenda implementados; chave não configurada | Ligar chave e recolher quotes prospetivos |
| 15–16 | Backtest de apostas e CLV | Bloqueado por ausência de odds temporizadas | Dados de mercado point-in-time, custos e regras de execução |
| 17 | Strategy Lab | Pendente | Backtest de apostas validado e proteção contra seleção múltipla |
| 18 | Dashboard | Navegação diária, backtests e combinadas; fixtures atuais dependem de chave | QA com feed real e cobertura de torneios |
| 19–24 | Notícias, lesões, meteorologia, PBP, shot data e live | Pendente | Fontes licenciadas e avaliação de ganho OOS |

**Regra de promoção:** nenhuma estratégia sai de investigação sem amostra OOS intocada, custos, sensibilidade, bootstrap, testes nulos, CPCV/PBO/DSR e paper tracking. O ganho v4 em 2024–2026 é diagnóstico porque o período já tinha sido visto; falta confirmação futura.

