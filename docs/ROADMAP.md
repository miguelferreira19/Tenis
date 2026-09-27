# Roadmap de implementação

Estado em 27-09-2026. O plano completo do utilizador está preservado em `tennis_quant_betting_platform.md`.

| Ordem do plano | Componente | Estado | Critério para avançar |
|---|---|---|---|
| 1–5 | Arquitetura de dados, resultados, validação, BD e framework temporal | Implementado no v0.1; PostgreSQL não testado nesta máquina | Obter horas reais de jogos e testar PostgreSQL |
| 6–8 | Features, Elo e modelo logístico | Implementado para o mercado vencedor | Alargar dados de treino e validar cobertura |
| 9–10 | XGBoost e calibração | Implementado em investigação | Confirmar estabilidade futura e incerteza |
| 11 | Simulação ponto → jogo → set → encontro | Pendente | Dados de pontos/serviço adequados e validação OOS |
| 12–14 | Odds, fair odds e EV | Importador e cenário manual implementados; feed real pendente | Feed licenciado com timestamp e hora do jogo |
| 15–16 | Backtest de apostas e CLV | Bloqueado por ausência de odds temporizadas | Dados de mercado point-in-time, custos e regras de execução |
| 17 | Strategy Lab | Pendente | Backtest de apostas validado e proteção contra seleção múltipla |
| 18 | Dashboard | Implementado para análise histórica | Ligar fixtures e mercados atuais |
| 19–24 | Notícias, lesões, meteorologia, PBP, shot data e live | Pendente | Fontes licenciadas e avaliação de ganho OOS |

**Regra de promoção:** nenhuma estratégia sai de investigação sem amostra OOS, custos, sensibilidade, bootstrap, testes nulos e paper tracking. Novas features entram apenas com disponibilidade point-in-time e ganho robusto fora da amostra.

