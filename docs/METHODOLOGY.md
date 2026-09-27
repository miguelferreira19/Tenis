# Metodologia v0.2

## Unidade temporal

Os ficheiros Sackmann incluem `tourney_date`, a data de início do torneio. Não incluem hora exata de cada partida. Para impedir fuga de informação, o estado de todos os jogadores de um grupo com a mesma data é capturado antes de se atualizarem os resultados desse grupo. `as_of` é 23:59:59 UTC do dia anterior ao início do torneio. Isto desperdiça informação de rondas anteriores, mas não usa informação posterior.

O ranking que aparece no CSV do próprio torneio é guardado como metadado, mas **não entra** na estimativa desse torneio: não existe uma hora de publicação independente. O modelo usa apenas o último ranking observado num torneio anterior, que pode estar desatualizado. O painel distingue "ranking no ficheiro" de "ranking anterior".

## Variáveis

O vetor simétrico A−B contém Elo global, Elo de superfície com shrinkage `n/(n+20)`, logaritmo da razão dos últimos rankings **anteriores**, forma dos últimos 10 jogos, pontos ganhos no serviço e na resposta dos últimos 20 encontros com estatísticas, descanso entre datas de torneios limitado a 14 dias e logaritmo da experiência. Valores de serviço/resposta em falta recebem priors neutros de 0,62/0,38. O descanso não pretende medir recuperação entre rondas.

O candidato `prematch-v4` acrescenta serviço e resposta por superfície, cada um regularizado por 10 jogos equivalentes em direção à taxa recente global do jogador, e diferença de carga de jogos nos 30 dias anteriores. As datas são **inícios de torneio**; a carga não mede dias reais entre rondas. Todas estas estatísticas são calculadas antes de incorporar o grupo atual. A comparação v4 vs v3 está em `RESULTS.md` e é diagnóstica, porque o período 2024+ já tinha sido consultado.

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

O backtest de probabilidades acrescenta séries anuais, intervalos de calibração e bootstrap pareado por torneio. A unidade de reamostragem é o torneio, para preservar dependência local entre jogos. A versão operacional usa a família escolhida em 2023, refaz o treino até 2024 e calibra em 2025. O diagnóstico de 2026 desse refit foi consultado; não é holdout intocado. Nenhuma destas métricas equivale a ROI.

## Limitações que impedem sinais

O arquivo não traz uma trajetória de odds com hora nem a hora de cada jogo. Há um adaptador de calendário e odds atuais, mas **a chave ainda não está configurada** nesta instalação. Portanto, a agenda de hoje fica vazia e o backtest de apostas está bloqueado. O formulário manual calcula apenas `p × odd − 1`; não valida disponibilidade, custos, limites ou qualidade da estimativa. Não existem gates DSR/PBO/CPCV, testes nulos ou paper tracking para aprovar estratégias.

Fixtures de uma fonte atual mantêm `start_at` exato e `observed_at` por cotação, em tabelas separadas dos resultados históricos. A associação de jogadores exige nome normalizado exatamente igual e único por circuito. Só odds anteriores ao início, observadas há menos de 6 horas, entram na agenda; superfícies não identificadas ficam `Unknown` e não geram candidatos. A palavra «candidato» significa apenas `p × odd − 1 > 0`, com superfície conhecida, **sem aprovação para aposta**.

O construtor de bilhetes suporta simples, acumulador, sistema k/N e round robin. A multiplicação das odds produz preço indicativo, não cotação aceite. Não estima probabilidade conjunta nem EV da combinada, pois dependências, restrições e regras de settlement da casa ainda não foram validadas. Duas seleções do mesmo jogo são rejeitadas na ausência de preço conjunto da casa.

Não se calcula confiança estatística para cada probabilidade, nem simulação de sets/games. O painel mostra apenas o mercado vencedor. A comparação de variáveis não é uma explicação causal nem SHAP.

