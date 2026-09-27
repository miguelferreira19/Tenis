# Metodologia v0.1

## Unidade temporal

Os ficheiros Sackmann incluem `tourney_date`, a data de início do torneio. Não incluem hora exata de cada partida. Para impedir fuga de informação, o estado de todos os jogadores de um grupo com a mesma data é capturado antes de se atualizarem os resultados desse grupo. `as_of` é 23:59:59 UTC do dia anterior ao início do torneio. Isto desperdiça informação de rondas anteriores, mas não usa informação posterior.

O ranking que aparece no CSV do próprio torneio é guardado como metadado, mas **não entra** na estimativa desse torneio: não existe uma hora de publicação independente. O modelo usa apenas o último ranking observado num torneio anterior, que pode estar desatualizado. O painel distingue "ranking no ficheiro" de "ranking anterior".

## Variáveis

O vetor simétrico A−B contém Elo global, Elo de superfície com shrinkage `n/(n+20)`, logaritmo da razão dos últimos rankings **anteriores**, forma dos últimos 10 jogos, pontos ganhos no serviço e na resposta dos últimos 20 encontros com estatísticas, descanso entre datas de torneios limitado a 14 dias e logaritmo da experiência. Valores de serviço/resposta em falta recebem priors neutros de 0,62/0,38. O descanso não pretende medir recuperação entre rondas.

O Elo começa em 1500. K global 32 e K de superfície 24. A probabilidade base combina 55% da diferença Elo global e 45% da diferença Elo de superfície. Estes parâmetros estão fixados no código; não foram otimizados no período de teste.

Walkovers, abandonos e partidas interrompidas (`W/O`, `RET`, `DEF`, `ABN`, `UNP`) ficam na base raw, mas não entram no treino, no teste nem na atualização de Elo. A definição de liquidação varia entre casas de apostas e estes registos não representam uma partida concluída.

## Divisão e seleção

| Período | Uso |
|---|---|
| 2015–2021 | Ajuste dos modelos |
| 2022 | Calibração sigmoid |
| 2023 | Comparação das três famílias pelo Brier |
| 2024–data disponível | Teste cronológico fora da amostra |

Cada observação de treino entra nas duas orientações A/B para evitar uma vantagem artificial da ordenação por identificador. A calibração também impõe simetria. O modelo selecionado é o que apresenta menor Brier em 2023. O teste OOS não escolhe o vencedor. Não houve pesquisa de hiperparâmetros; foram comparadas três famílias pré-definidas.

As métricas publicadas são Brier, log loss, ECE de 10 bins e taxa de acerto, global e por ATP/WTA/superfície. ECE deve ser lido com cautela em subgrupos pequenos. A arquitetura guarda versões e previsões imutáveis por `match_id` e versão.

## Limitações que impedem sinais

O arquivo não traz uma trajetória de odds com hora nem a hora de cada jogo. A instalação não tem fornecedor de jogos futuros ou de odds atuais. Logo, o scanner de mercado fica vazio e o backtest de apostas está bloqueado. O formulário de odds manual calcula apenas `p × odd − 1`; não valida disponibilidade, custos, limites ou qualidade da estimativa. Não existem gates DSR/PBO/CPCV, testes nulos ou paper tracking para aprovar estratégias.

Não se calcula confiança estatística para cada probabilidade, nem simulação de sets/games. O painel mostra apenas o mercado vencedor. A comparação de variáveis não é uma explicação causal nem SHAP.

