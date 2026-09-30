# Resultados de investigação v0.3

Nova investigação em 30-09-2026: [resultados e registo completo](docs/RESULTS_2026-09-30.md). O candidato novo reduziu Brier de diagnóstico em origens móveis de **0,213292 para 0,211292** nos mesmos 13 734 jogos. A confirmação prospectiva continua pendente; ver o relatório para seleção múltipla, limitações, métodos rejeitados e previsões congeladas.

Execução local em 27-09-2026. Arquivo ATP/WTA até ao torneio iniciado em **25-05-2026**. Os artefactos JSON em `artifacts/` guardam todos os valores e versões; os ficheiros raw não são redistribuídos.

## Cobertura e protocolo

- 24 ficheiros raw; 62 056 registos normalizados; 59 895 partidas concluídas elegíveis.
- Treino 2015–2021: 35 257 jogos. Calibração 2022: 5 306. Seleção por Brier em 2023: 5 598. Diagnóstico 2024–maio de 2026: 13 734.
- Três famílias: Elo, logística, XGBoost. O candidato v4 acrescenta **3 variáveis** pré-torneio: serviço e resposta por superfície regularizados e carga de partidas nos 30 dias anteriores. Sem sweep de thresholds de aposta.

| Modelo v4 | Brier seleção 2023 ↓ | Brier diagnóstico 2024–2026 ↓ | Log loss ↓ | Acerto |
|---|---:|---:|---:|---:|
| Elo | 0,217146 | 0,216209 | 0,620048 | 64,5% |
| Logística | 0,214265 | 0,214014 | 0,615195 | 65,3% |
| XGBoost | **0,213539** | **0,213376** | **0,613705** | **65,3%** |

XGBoost é a família selecionada pela validação 2023. No diagnóstico v4, a melhoria de Brier face à logística é **0,000638**; bootstrap pareado por 519 torneios e 2 000 reamostragens: **[0,000244; 0,001059]**. Face ao Elo: **0,002834**, intervalo **[0,001680; 0,003982]**. Estes intervalos medem previsão, não lucro.

## Comparação da alteração v4

O XGBoost v3 congelado tinha Brier **0,214493** no mesmo conjunto 2024–2026. O v4 obteve **0,213376**, melhoria **0,001117**; bootstrap pareado por torneio **[0,000597; 0,001623]**. O v4 foi desenhado após já se terem visto diagnósticos do v3 nesse período. **Por isso 2024–2026 deixou de ser um holdout totalmente novo para a alteração v4.** Não se reivindica confirmação externa; é necessária uma avaliação prospectiva.

| Ano do diagnóstico v4 | Jogos | Brier | ECE 10 bins |
|---|---:|---:|---:|
| 2024 | 5 736 | 0,212894 | 0,020435 |
| 2025 | 5 343 | 0,215623 | 0,026544 |
| 2026 até maio | 2 655 | 0,209896 | 0,032352 |

O painel **Backtests** mostra ainda ATP/WTA, superfície, log loss e curvas de calibração por intervalo de probabilidade. A calibração piora de 2024 para a amostra parcial de 2026 em ECE; monitorizar deriva é trabalho pendente.

## Modelo para jogos futuros

Foi feito um refit da família XGBoost v4 para uso **exploratório**: treino até 2024, calibração 2025, diagnóstico 2026 (2 655 jogos) com Brier **0,209893** e log loss **0,605768**. O último resultado raw é de 25-05-2026; não se afirma atualidade posterior. O modelo é exibido como investigação e não está aprovado para sinais.

## Pesquisa de modelos e candidato de inatividade

Foram testadas **15 configurações** (incluindo o modelo atual) em cinco janelas anuais de origem móvel, 2019–2023. Para prever o ano `Y`, o treino usa até `Y−2`, a calibração sigmoid usa `Y−1` e o resultado é medido em `Y`. A média abaixo dá o mesmo peso a cada ano; o teste pareado subsequente usa cada jogo. Mais **3 controlos** baralharam a variável vencedora. Não se procuraram thresholds de apostas.

| Família / hipótese | Melhor configuração | Brier médio anual 2019–2023 ↓ | Decisão |
|---|---|---:|---|
| Elo global + superfície | Elo atual | 0,216860 | Inferior |
| Logística | C=1 atual | 0,213913 | Inferior; C=0,3 escalado: 0,213993 |
| XGBoost atual | 200 árvores, profundidade 3 | 0,213058 | Referência |
| XGBoost mais raso / regularizado | Regularizado | 0,213253 | Inferior; raso: 0,213485 |
| HistGradientBoosting | 180 iterações, 7 folhas | 0,213224 | Inferior |
| Mistura XGBoost + Elo | 80% + 20% | 0,212941 | Ganho pequeno e inconsistente; misturas com logística piores |
| Forma recente com decaimento | 180/365 dias | 0,213202 | Inferior |
| Elo atenuado por inatividade | Uma variável | 0,213062 | Sem ganho |
| Pausa + Elo atenuado | Duas variáveis | 0,212528 | Inferior à pausa isolada |
| Todas as variáveis temporais | Quatro variáveis | 0,212564 | Inferior à pausa isolada |
| **Pausa desde o último torneio** | `log(1+dias_A)−log(1+dias_B)`, limite 365 dias | **0,212473** | Desafiante de investigação |

A nova variável de pausa foi calculada exclusivamente com o **início do torneio anterior** de cada jogador; ausência de histórico equivale a 365 dias. Não se alteraram os parâmetros do XGBoost. Nos **23 916 jogos** de 2019–2023, a comparação pareada deu Brier **0,213074 → 0,212523**, melhoria **0,000550**; bootstrap por **1 265 torneios**, 2 000 reamostragens: **[0,000345; 0,000738]**. Melhorou nos cinco anos e em ATP/WTA e nas três superfícies nesse intervalo. Três controlos com a mesma coluna baralhada deram Brier médio anual **0,213113**, **0,213107** e **0,213141**, todos piores do que a referência **0,213058**.

Nos **13 734 jogos** de 2024–maio de 2026, a melhoria foi menor: Brier **0,213292 → 0,213022**, diferença **0,000270**; bootstrap por **519 torneios**: **[−0,000032; 0,000582]**. O intervalo inclui zero. O ganho ATP foi **0,000013** e na relva houve deterioração **0,000096**. Os três anos tiveram diferenças positivas, mas 2024+ já tinha sido consultado durante o desenvolvimento do projeto, pelo que **não é um holdout puro** para esta hipótese. Os intervalos não corrigem a escolha entre 15 configurações. A confirmação requer resultados futuros recolhidos após congelar o candidato.

O candidato fica treinado e versionado em `artifacts/xgboost-prematch-v5-layoff-*.joblib`, com avaliação em `artifacts/layoff_research.json`. **Não substitui** o XGBoost v4 exibido na agenda. Esta decisão evita converter uma melhoria histórica modesta em confiança excessiva.

Referências metodológicas: [modelo dinâmico por superfície](https://doi.org/10.1111/rssa.12464), [Bradley–Terry para ténis](https://doi.org/10.1016/j.ijforecast.2010.04.004), [previsão de serviço e resposta com shrinkage](https://journals.sagepub.com/doi/10.3233/JSA-200345), [comparação de Elo no ténis](https://irep.ntu.ac.uk/id/eprint/42038/) e [regularização de XGBoost](https://xgboost.readthedocs.io/en/latest/parameter.html). Estas fontes motivam candidatos; **os resultados numéricos acima provêm apenas do nosso arquivo e dos testes executados**.

## Apostas e combinadas

**Número de apostas históricas executadas/testadas: 0.** Não há chave de odds configurada nem preços históricos com timestamp alinhados à hora real dos jogos. Custos, ROI, CLV, drawdown, DSR, PBO, CPCV, testes nulos, sensibilidade e paper tracking **não são calculáveis**. A página diária mostra zero sugestões reais até existirem cotações verificáveis. O construtor de combinadas calcula apenas odds e pagamentos teóricos, identifica entradas manuais e exige preço conjunto da casa para pernas do mesmo encontro.

Reprodução: `scripts/bootstrap.py --skip-download`, `scripts/compare_models.py`, `scripts/backtest_predictions.py`, `scripts/refit_operational.py`, `scripts/research_layoff.py`. Artefactos: `artifacts/evaluation.json`, `model_comparison.json`, `prediction_backtest.json`, `operational.json`, `layoff_research.json`. As outras configurações e controlos estão registados nos relatórios de experiência em `work/` nesta instalação.
