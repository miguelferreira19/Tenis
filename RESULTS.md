# Resultados de investigação v0.2

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

## Apostas e combinadas

**Número de apostas históricas executadas/testadas: 0.** Não há chave de odds configurada nem preços históricos com timestamp alinhados à hora real dos jogos. Custos, ROI, CLV, drawdown, DSR, PBO, CPCV, testes nulos, sensibilidade e paper tracking **não são calculáveis**. A página diária mostra zero sugestões reais até existirem cotações verificáveis. O construtor de combinadas calcula apenas odds e pagamentos teóricos, identifica entradas manuais e exige preço conjunto da casa para pernas do mesmo encontro.

Reprodução: `scripts/bootstrap.py --skip-download`, `scripts/compare_models.py`, `scripts/backtest_predictions.py`, `scripts/refit_operational.py`. Artefactos: `artifacts/evaluation.json`, `model_comparison.json`, `prediction_backtest.json`, `operational.json`.
