# Resultados de investigação v0.1

Execução local em 27-09-2026. Dados históricos ATP/WTA do snapshot fixado no manifesto. O último torneio representado começa em **25-05-2026**; a plataforma não contém calendário ou odds atuais.

## Cobertura e divisão

- 24 ficheiros raw, 62 056 registos normalizados.
- 59 895 partidas concluídas elegíveis para o modelo. Walkovers, abandonos e registos sem score ficam fora do treino e da avaliação.
- Treino: 35 257; calibração: 5 306; seleção: 5 598; teste fora da amostra: 13 734.
- Famílias testadas: **3** (Elo, logística, XGBoost). Parâmetros pré-definidos; sem sweep de estratégias ou thresholds.

## Probabilidade de vencedor

| Modelo | Brier seleção 2023 ↓ | Brier teste OOS 2024–2026 ↓ | Log loss OOS ↓ | Acerto OOS |
|---|---:|---:|---:|---:|
| Elo | 0,217146 | 0,216209 | 0,620048 | 64,5% |
| Logística | 0,214553 | 0,214795 | 0,617055 | 65,3% |
| XGBoost | **0,213858** | **0,214493** | **0,616293** | **65,4%** |

XGBoost foi selecionado exclusivamente pelo Brier de 2023. No teste OOS supera Elo por 0,001716 e logística por 0,000302 em Brier. Bootstrap emparelhado por torneio, 2 000 reamostragens: intervalo 95% da diferença favorável ao XGBoost de **[0,000693; 0,002774]** contra Elo e **[−0,000076; 0,000690]** contra logística. O segundo intervalo inclui zero: **não há evidência robusta de vantagem sobre a logística** neste snapshot. Os intervalos não demonstram retorno financeiro futuro.

## Estabilidade observada do XGBoost

| Subgrupo OOS | N | Brier |
|---|---:|---:|
| 2024 | 5 736 | 0,213917 |
| 2025 | 5 343 | 0,216769 |
| 2026 até maio | 2 655 | 0,211157 |
| ATP | 7 192 | 0,214441 |
| WTA | 6 542 | 0,214551 |
| Hard | 8 125 | 0,214338 |
| Clay | 4 276 | 0,214508 |
| Grass | 1 189 | 0,216653 |

**Falha observada:** em 2025, a logística (Brier 0,216590) supera XGBoost (0,216769). A vantagem do XGBoost não é uniforme por ano e não está confirmada face à logística pelo bootstrap por torneio. Os dados não justificam promovê-lo a sinal de aposta.

## Apostas

**Não avaliado.** O dataset não contém odds com timestamp nem a hora de cada partida. Número de apostas: **0**. Custos, ROI, CLV, drawdown, DSR, PBO, CPCV, testes nulos, sensibilidade e paper tracking: **não calculáveis nesta versão**. Nenhum sinal pode ser promovido. O comparador de odds do painel produz apenas cenários manuais hipotéticos.

Ficheiros de reprodução: `artifacts/evaluation.json`, `artifacts/model_comparison.json`, `data/manifest.json`; código em `apps/api/tennis_quant/` e `scripts/compare_models.py`. Os artefactos contêm dados/modelos de pesquisa locais e são ignorados pelo Git.

