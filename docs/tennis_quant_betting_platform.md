# Tennis Quant Betting Intelligence Platform
## Especificação completa do projeto

> Documento de visão, arquitetura, dados, modelos, backtesting, value engine, plataforma e roadmap para construir uma plataforma quantitativa profissional de análise de apostas em ténis.

---

# 1. Visão do projeto

O objetivo é construir uma plataforma de **Sports Quantitative Analytics** especializada inicialmente em ténis.

A plataforma não deve ser um simples "bot de palpites". Deve funcionar como um **quantitative betting terminal**, capaz de:

- recolher dados históricos e atuais;
- construir perfis quantitativos de jogadores;
- analisar cada jogo ao maior nível de detalhe possível;
- modelar a probabilidade de diferentes resultados;
- simular partidas;
- calcular fair odds;
- recolher e comparar odds de mercado;
- identificar discrepâncias entre preço de mercado e probabilidade estimada;
- calcular expected value;
- analisar movimento das odds;
- medir closing line value;
- fazer backtesting rigoroso;
- evitar data leakage;
- acompanhar calibração e model drift;
- explicar quantitativamente por que razão um mercado aparece como oportunidade;
- apresentar todos os jogos e mercados num dashboard profissional;
- manter histórico imutável das previsões e versões dos modelos.

A IA generativa será uma camada de explicação e interação. **O motor quantitativo é que produz as probabilidades e sinais.**

---

# 2. Princípio fundamental

A arquitetura deve separar quatro conceitos:

1. **Prediction**
2. **Probability**
3. **Fair Price**
4. **Betting Value**

Exemplo:

- Modelo estima que jogador A ganha: 63%.
- Fair odds = 1 / 0,63 = 1,587.
- Mercado oferece 1,80.
- Existe uma diferença entre a fair price estimada e o preço de mercado.
- Essa diferença pode representar valor esperado positivo, mas apenas se a estimativa tiver qualidade e incerteza aceitável.

Nunca concluir apenas:

> "O jogador vai ganhar."

A pergunta quantitativa é:

> "Qual é a distribuição de resultados estimada pelo modelo e como se compara com o preço disponível no mercado?"

---

# 3. Objetivos

## 3.1 Objetivo principal

Construir um sistema capaz de analisar automaticamente todos os jogos de ténis disponíveis e avaliar múltiplos mercados.

## 3.2 Objetivos secundários

- criar uma base histórica auditável;
- construir centenas de features;
- testar diferentes famílias de modelos;
- produzir probabilidades calibradas;
- simular jogos;
- avaliar mercados;
- medir EV;
- medir CLV;
- fazer backtesting walk-forward;
- analisar drawdown e risco;
- detetar model drift;
- construir um terminal visual;
- permitir investigação manual de qualquer jogo;
- permitir criar e testar estratégias personalizadas.

---

# 4. Filosofia quantitativa

A plataforma deve seguir este pipeline:

```text
RAW DATA
   ↓
DATA VALIDATION
   ↓
NORMALIZATION
   ↓
FEATURE ENGINEERING
   ↓
PLAYER STATE
   ↓
MATCHUP ENGINE
   ↓
PREDICTION MODELS
   ↓
PROBABILITY CALIBRATION
   ↓
MATCH SIMULATION
   ↓
MARKET PRICING
   ↓
FAIR ODDS
   ↓
MARKET COMPARISON
   ↓
VALUE ENGINE
   ↓
RISK / UNCERTAINTY
   ↓
BACKTEST / HISTORICAL VALIDATION
   ↓
SIGNAL
   ↓
DASHBOARD
   ↓
AI EXPLANATION
```

---

# 5. Escopo inicial

## Desporto

Ténis.

## Circuitos

- ATP
- WTA

## Competições

Prioridade:

- Grand Slams
- ATP Masters
- WTA 1000
- ATP 500
- WTA 500
- ATP 250
- WTA 250

Posteriormente:

- Challenger
- ITF
- competições adicionais

## Mercados iniciais

1. Match Winner
2. Game Handicap
3. Total Games
4. Set Betting
5. Set Handicap
6. Player Games

Posteriormente:

7. Aces
8. Double Faults
9. Breaks
10. First Set
11. Player Props
12. outros mercados disponíveis

---

# 6. Arquitetura geral

```text
                         DATA SOURCES
                              │
             ┌────────────────┼────────────────┐
             │                │                │
          RESULTS            ODDS             NEWS
             │                │                │
          RANKINGS          WEATHER          INJURY
             │                │                │
           STATS             PBP             SHOT DATA
             └────────────────┼────────────────┘
                              ↓
                       DATA INGESTION
                              ↓
                         RAW STORAGE
                              ↓
                     DATA WAREHOUSE
                              ↓
                       FEATURE STORE
                              ↓
                    PLAYER STATE ENGINE
                              ↓
                       MATCHUP ENGINE
                              ↓
                    MODELING PIPELINE
                              ↓
                    PROBABILITY ENGINE
                              ↓
                     MONTE CARLO ENGINE
                              ↓
                      MARKET ENGINE
                              ↓
                       VALUE ENGINE
                              ↓
                      BACKTEST ENGINE
                              ↓
                        MODEL REGISTRY
                              ↓
                         API LAYER
                              ↓
                       WEB DASHBOARD
                              ↓
                       AI ANALYST
```

---

# 7. Fontes de dados

A plataforma deve ser preparada para trabalhar com várias fontes.

Nunca depender de uma única fonte quando for possível evitar.

## 7.1 Histórico de resultados

Fonte de investigação inicial:

- Jeff Sackmann Tennis datasets
- ATP/WTA historical results
- rankings
- player data
- match statistics

Objetivo:

- construir dataset inicial;
- testar features;
- validar modelos;
- fazer os primeiros backtests.

## 7.2 Dados profissionais

Para produção podem ser avaliados fornecedores como:

- Sportradar
- Tennis Abstract / Tennis Insight e equivalentes
- Tennis APIs especializadas
- fornecedores oficiais/licenciados
- feeds profissionais de odds

A fonte escolhida deve ser avaliada por:

- cobertura;
- profundidade;
- latência;
- histórico;
- estabilidade;
- licença;
- custo;
- granularidade.

## 7.3 Point-by-point

Idealmente recolher:

- ponto;
- servidor;
- resultado do ponto;
- score;
- set;
- game;
- break point;
- tiebreak;
- ace;
- double fault;
- duração;
- contexto do ponto.

## 7.4 Shot-by-shot

Quando disponível:

- tipo de pancada;
- forehand;
- backhand;
- slice;
- volley;
- smash;
- direção;
- profundidade;
- winner;
- erro;
- rally length;
- return direction;
- approach.

## 7.5 Odds

Guardar:

- bookmaker;
- mercado;
- seleção;
- odd;
- timestamp;
- status;
- limite quando disponível;
- exchange price quando disponível.

Não guardar apenas a odd final.

Guardar toda a trajetória.

---

# 8. Raw Data Layer

Nunca alterar o dado original.

Estrutura conceptual:

```text
/raw
  /results
  /rankings
  /players
  /matches
  /match_stats
  /point_by_point
  /shot_data
  /odds
  /news
  /injuries
  /weather
```

Cada registo deve ter:

- source;
- ingestion_timestamp;
- event_timestamp;
- source_id;
- raw_payload;
- parser_version;
- checksum/hash;
- data_quality_status.

Objetivo:

Permitir reconstruir exatamente o que o sistema sabia em determinado momento.

---

# 9. Point-in-time data

Este é um requisito crítico.

Cada informação deve ser associada ao momento em que ficou disponível.

Exemplo:

```text
match_start = 2026-09-19 18:00
```

Uma notícia publicada às 20:00 não pode entrar na previsão das 18:00.

Uma estatística calculada depois do jogo também não pode entrar na previsão.

Todas as features devem respeitar:

```text
feature_timestamp <= prediction_timestamp
```

---

# 10. Data Leakage Prevention

Criar um módulo específico de auditoria.

Verificar:

- future matches;
- future rankings;
- future statistics;
- future injuries;
- future news;
- closing odds usadas indevidamente;
- duplicated observations;
- target leakage;
- normalization baseada no futuro;
- features calculadas com janelas incorretas.

Se for detetado leakage:

```text
TRAINING BLOCKED
```

---

# 11. Database

PostgreSQL como base principal.

Tabelas principais:

```text
players
tournaments
venues
matches
sets
games
points
match_stats
player_rankings
player_ratings
player_surface_ratings
player_form
player_fatigue
player_travel
player_injuries
news
weather
markets
bookmakers
odds_snapshots
predictions
model_versions
features
signals
bets
backtests
strategies
strategy_runs
clv_observations
```

---

# 12. Player table

Campos principais:

```text
player_id
name
gender
country
hand
backhand_type
height
birth_date
turned_pro
status
```

Não assumir que todas as características estão disponíveis.

---

# 13. Match table

```text
match_id
tournament_id
round
date
start_time
surface
indoor
best_of
player_1
player_2
winner
loser
score
duration
status
```

---

# 14. Match Statistics

Guardar métricas completas:

### Serve

- first serve %
- first serve points won
- second serve points won
- service points won
- aces
- double faults
- break points saved
- service games
- hold %

### Return

- return points won
- first serve return points won
- second serve return points won
- break points won
- break conversion
- break %
- return games

### Overall

- total points won
- total games won
- sets won
- tiebreaks
- winners
- unforced errors
- net points
- rally statistics quando disponíveis.

---

# 15. Player State Engine

Cada jogador terá um estado quantitativo atualizado antes de cada jogo.

Exemplo:

```text
PLAYER STATE

Overall Elo
Surface Elo
Recent Elo
Serve Rating
Return Rating
Hard Rating
Clay Rating
Grass Rating
Indoor Rating
Outdoor Rating
Form Index
Fatigue Index
Travel Stress
Injury Risk
Opponent-Adjusted Form
```

---

# 16. Recency Engine

Cada estatística deve existir em múltiplas janelas:

- carreira;
- 3 anos;
- 2 anos;
- 1 ano;
- 6 meses;
- 3 meses;
- 30 dias;
- últimos 20 jogos;
- últimos 10;
- últimos 5.

Utilizar:

- rolling averages;
- EWMA;
- exponential decay;
- recency weighting.

Os parâmetros de decay devem ser aprendidos através de validação.

---

# 17. Elo System

Construir várias versões:

```text
Global Elo
Hard Elo
Clay Elo
Grass Elo
Indoor Elo
Outdoor Elo
Recent Elo
Serve Elo
Return Elo
```

Possivelmente:

```text
Opponent-adjusted Elo
Tournament-adjusted Elo
Surface-speed adjusted Elo
```

Também guardar o histórico temporal de cada rating.

---

# 18. Glicko / Bayesian Ratings

Avaliar:

- Glicko;
- Glicko-2;
- Bayesian dynamic ratings.

Objetivo:

Além do rating, obter incerteza.

Exemplo:

```text
Player A
Rating = 2150
Uncertainty = ±42
```

---

# 19. Serve Model

Criar um modelo dedicado à qualidade do serviço.

Features:

- first serve percentage;
- ace rate;
- double fault rate;
- first serve points won;
- second serve points won;
- service points won;
- hold percentage;
- break points saved;
- opponent return quality;
- surface;
- court speed;
- opponent handedness;
- opponent return side.

Output:

```text
Expected Hold %
Expected Service Points Won %
Expected Aces
Expected Double Faults
```

---

# 20. Return Model

Modelo específico para retorno.

Features:

- return points won;
- first serve return;
- second serve return;
- break rate;
- break points created;
- break points converted;
- opponent serve strength;
- surface;
- court speed;
- opponent style.

Output:

```text
Expected Break %
Expected Return Points Won %
Expected Breaks
```

---

# 21. Matchup Engine

Não comparar apenas ratings.

Calcular:

```text
Player A serve vs Player B return
Player B serve vs Player A return
```

E:

```text
baseline vs baseline
aggression vs defense
rally tolerance
left/right matchup
surface matchup
serve/return interaction
```

---

# 22. Surface Engine

Separar:

```text
Hard
Clay
Grass
```

E quando possível:

```text
Hard Indoor
Hard Outdoor
Fast Hard
Medium Hard
Slow Hard
```

Features de superfície devem ter shrinkage para evitar overfitting quando o jogador tem poucas observações.

---

# 23. Court Speed

Quando disponível:

- court speed;
- altitude;
- indoor/outdoor;
- historical ace rate;
- historical hold rate;
- average rally length.

Pode-se inferir court-speed proxy através de dados históricos quando a informação direta não estiver disponível.

---

# 24. Opponent Quality Adjustment

Uma vitória contra um jogador de nível muito alto não deve valer o mesmo que uma vitória contra um jogador muito abaixo.

Criar:

```text
Opponent-adjusted performance
```

Exemplo:

```text
Raw hold = 88%
Adjusted hold = 84.7%
```

porque os adversários enfrentados eram relativamente fracos.

---

# 25. H2H Engine

Não usar H2H simplesmente como:

```text
A 5 - 2 B
```

Separar:

- overall;
- surface;
- recent;
- last 3;
- last 5;
- serve;
- return;
- games;
- sets;
- tiebreaks;
- average duration.

Aplicar recency weighting.

Nunca permitir que H2H tenha peso excessivo quando a amostra é pequena.

---

# 26. Fatigue Engine

Criar:

```text
Matches last 3 days
Matches last 7 days
Matches last 14 days
Sets last 7 days
Games last 7 days
Court time last 7 days
Court time last 14 days
Previous match duration
Previous match score
Rest hours
```

Também:

```text
Travel distance
Time-zone change
Tournament sequence
```

Output:

```text
Fatigue Index
Recovery Index
Schedule Stress Index
```

---

# 27. Travel Engine

Calcular:

- localização do último jogo;
- localização do próximo jogo;
- distância;
- tempo entre jogos;
- mudança de timezone;
- mudança de altitude;
- mudança de superfície.

---

# 28. Tournament Context

Features:

- tournament tier;
- round;
- seed;
- ranking points;
- defending points;
- qualifying;
- previous round duration;
- days in tournament;
- draw position;
- potential next opponent.

Não assumir impacto psicológico sem evidência.

---

# 29. Weather Engine

Para jogos outdoor:

- temperatura;
- humidade;
- vento;
- precipitação;
- altitude;
- pressão;
- court conditions.

Transformar em features quando existir fundamentação estatística.

---

# 30. Injury / Fitness Engine

Criar base separada.

Campos:

```text
player
body_area
event
date
severity
status
source
source_quality
confidence
```

Classificação:

```text
Official
High-quality media
Reliable journalist
Rumour
Unknown
```

Apenas informação disponível antes do jogo pode influenciar a previsão.

---

# 31. News Engine

Pipeline:

```text
NEWS
 ↓
ENTITY EXTRACTION
 ↓
EVENT CLASSIFICATION
 ↓
SOURCE QUALITY
 ↓
TIMESTAMP
 ↓
RECENCY
 ↓
IMPACT ESTIMATION
 ↓
FEATURE
```

Categorias:

- injury;
- withdrawal;
- coaching;
- travel;
- tournament;
- equipment;
- schedule;
- personal context quando relevante e publicamente verificável.

Evitar especulação.

---

# 32. Point-by-point Engine

Usar PBP para estimar:

- point win probability;
- serve point probability;
- return point probability;
- break probability;
- tiebreak probability;
- momentum proxies;
- clutch performance.

Não assumir que "momentum" existe como fenómeno causal só porque uma sequência de pontos aconteceu. Testar estatisticamente.

---

# 33. Shot Data Engine

Quando disponível:

- forehand;
- backhand;
- slice;
- volley;
- serve direction;
- return direction;
- depth;
- rally length;
- winner/error;
- net approach.

Usar como camada opcional devido à cobertura limitada.

---

# 34. Player Style Clustering

Aplicar clustering para descobrir estilos.

Possíveis grupos:

- big server;
- aggressive baseliner;
- counterpuncher;
- defensive baseliner;
- all-court;
- serve-and-volley;
- clay specialist.

O cluster não deve ser atribuído manualmente.

---

# 35. Feature Store

Todas as features devem ter:

```text
feature_name
player_id / match_id
value
timestamp
source
feature_version
calculation_version
```

Exemplo:

```text
surface_elo = 2187
timestamp = 2026-09-19 14:00
```

---

# 36. Feature Groups

Organizar centenas de features:

```text
A. Ranking
B. Elo
C. Surface
D. Serve
E. Return
F. Form
G. H2H
H. Fatigue
I. Travel
J. Tournament
K. Weather
L. Injury
M. News
N. Point-by-point
O. Shot data
P. Market
Q. Context
```

---

# 37. Feature Selection

Testar:

- correlation;
- mutual information;
- permutation importance;
- SHAP;
- regularization;
- recursive feature elimination.

Não escolher features apenas porque melhoram o ROI num único período.

---

# 38. Model Families

Construir múltiplos modelos.

## Baselines

1. Market implied probability
2. Elo
3. Logistic Regression

## Machine Learning

4. Random Forest
5. XGBoost
6. LightGBM

## Bayesian

7. Bayesian logistic
8. Dynamic Bayesian ratings

## Specialized

9. Serve model
10. Return model
11. Matchup model
12. Point simulation

---

# 39. Ensemble

Combinar modelos apenas quando houver benefício demonstrado.

Exemplo conceptual:

```text
Elo
Logistic
XGBoost
Bayesian
Serve/Return
Simulation
        ↓
Ensemble
```

Os pesos devem ser definidos por validação, não manualmente.

---

# 40. Probability Calibration

Depois da previsão:

- Platt scaling;
- isotonic regression;
- beta calibration;
- calibration curves.

Avaliar:

- Brier Score;
- Log Loss;
- Expected Calibration Error;
- reliability diagrams.

---

# 41. Model Uncertainty

Guardar:

```text
point estimate
confidence interval
prediction interval
model disagreement
data quality
```

Exemplo:

```text
Probability = 57.2%
Interval = 52.9%–61.4%
Model disagreement = 5.7pp
```

---

# 42. Monte Carlo Match Simulator

Simular milhares ou milhões de jogos.

Pipeline:

```text
Point
 ↓
Game
 ↓
Set
 ↓
Match
```

Outputs:

- match win probability;
- set probabilities;
- game distribution;
- expected games;
- expected sets;
- expected breaks;
- tiebreak probability;
- correct score probabilities;
- player game distribution.

---

# 43. Market Distribution Engine

A partir da distribuição simulada:

```text
P(Over 21.5)
P(Over 22.5)
P(Over 23.5)
P(Over 24.5)
```

e:

```text
P(Player -2.5)
P(Player -3.5)
P(Player -4.5)
```

Criar uma curva completa de preços.

---

# 44. Odds Engine

Guardar todas as odds por:

```text
bookmaker
market
selection
timestamp
```

Calcular:

```text
decimal odds
implied probability
no-vig probability
market median
best price
sharp reference
closing price
```

---

# 45. Fair Odds

Para cada mercado:

```text
Fair Odds = 1 / Model Probability
```

Quando o mercado exigir múltiplos resultados, garantir que as probabilidades formam uma distribuição válida.

---

# 46. Expected Value

Para uma aposta decimal:

```text
EV = P(win) × odds - 1
```

Exemplo:

```text
P = 0.57
Odds = 1.95

EV = 0.57 × 1.95 - 1
EV = +0.1115
EV = +11.15%
```

Não tratar EV como lucro garantido.

---

# 47. Edge

Separar:

```text
Probability Edge
= Model Probability - Market No-Vig Probability
```

de:

```text
Price Edge
= Market Odds / Fair Odds - 1
```

e:

```text
EV
```

---

# 48. Market Scanner

Processar todos os jogos:

```text
TODAY
 ↓
ALL MATCHES
 ↓
ALL MARKETS
 ↓
ALL BOOKMAKERS
 ↓
VALUE ENGINE
 ↓
FILTERS
 ↓
SIGNALS
```

Output:

```text
Match
Market
Bookmaker
Odds
Model Probability
Market Probability
Fair Odds
EV
Edge
Confidence
Data Quality
```

---

# 49. Signal Engine

Um sinal não é simplesmente:

```text BET
```

Terá estados:

```text
NO SIGNAL
WATCH
VALUE
STRONG VALUE
DATA INSUFFICIENT
HIGH UNCERTAINTY
MARKET MOVING
STALE ODDS
```

Os nomes podem ser ajustados, mas devem representar regras quantitativas, não opiniões.

---

# 50. Signal Confidence

Construir score baseado em:

- calibration;
- model agreement;
- data completeness;
- sample size;
- historical performance of similar situations;
- market liquidity;
- odds stability;
- injury uncertainty;
- feature uncertainty.

Não transformar o score num "grau de certeza" absoluto.

---

# 51. Odds Movement Engine

Guardar:

```text
Opening Odds
Current Odds
Best Odds
Median Odds
Closing Odds
```

Calcular:

```text
Opening → Current
Current → Closing
Opening → Closing
```

Mostrar gráfico temporal.

---

# 52. Closing Line Value

Para cada sinal:

```text
Entry Odds
Closing Odds
```

Calcular CLV de forma consistente com o mercado.

Guardar:

```text
CLV
CLV %
CLV absolute
CLV by bookmaker
CLV by market
```

---

# 53. Prediction Archive

Cada previsão deve ser imutável.

Campos:

```text
prediction_id
match_id
market_id
timestamp
model_version
feature_version
probability
fair_odds
uncertainty
market_odds
EV
```

Nunca sobrescrever previsões antigas.

---

# 54. Model Registry

Cada modelo tem:

```text
model_id
version
training_period
feature_version
hyperparameters
calibration_method
training_dataset_hash
metrics
deployment_date
status
```

Estados:

```text
research
validation
candidate
production
retired
```

---

# 55. Backtesting

Usar principalmente:

## Walk-forward validation

Exemplo:

```text
Train: 2015–2020
Test: 2021

Train: 2015–2021
Test: 2022

Train: 2015–2022
Test: 2023

Train: 2015–2023
Test: 2024

Train: 2015–2024
Test: 2025
```

---

# 56. Train / Validation / Test

Separação recomendada:

```text
TRAIN
historical period

VALIDATION
model selection

TEST
untouched

LIVE
future observations
```

O test set não deve ser utilizado para escolher parâmetros.

---

# 57. Historical Odds Backtest

O backtester deve reproduzir o mercado como existia na altura.

Para cada aposta:

```text
prediction timestamp
available odds
selected odds
closing odds
result
```

Nunca utilizar uma odd que ainda não existia no momento do sinal.

---

# 58. Backtest Metrics

## Profitability

- total bets;
- wins;
- losses;
- hit rate;
- turnover;
- profit;
- ROI;
- yield;
- average odds.

## Risk

- max drawdown;
- average drawdown;
- longest losing streak;
- bankroll volatility;
- worst month;
- worst surface;
- worst market.

## Prediction

- Brier Score;
- Log Loss;
- calibration;
- ROC-AUC quando apropriado.

## Market

- CLV;
- average edge;
- average EV;
- closing probability difference.

---

# 59. Bootstrap / Monte Carlo Backtest

Fazer milhares de reamostragens dos resultados.

Obter:

```text
Expected ROI
Median ROI
5th percentile
25th percentile
75th percentile
95th percentile
Probability ROI > 0
```

Também simular trajetórias de bankroll.

---

# 60. Strategy Lab

Permitir criar estratégias:

```text
Market = Match Winner
Min Edge = 4%
Odds = 1.70–3.00
Confidence >= 75
Data Quality >= 90
Surface = Hard
```

Executar backtest.

Guardar a estratégia.

---

# 61. Strategy Parameters

Filtros possíveis:

- sport;
- tour;
- tournament;
- surface;
- market;
- odds range;
- minimum EV;
- minimum edge;
- confidence;
- data quality;
- ranking range;
- favorite/underdog;
- fatigue;
- rest;
- model disagreement;
- bookmaker;
- time-to-start;
- liquidity.

---

# 62. Strategy Overfitting Protection

Não procurar apenas a estratégia com maior ROI histórico.

Aplicar:

- out-of-sample;
- walk-forward;
- parameter stability;
- sensitivity analysis;
- minimum sample size;
- multiple testing awareness;
- bootstrap;
- regime testing.

Se:

```text
Edge >= 5% → ROI +6%
Edge >= 6% → ROI +7%
Edge >= 7% → ROI +6.5%
```

é mais robusto do que:

```text
Edge >= 6.37% → ROI +14%
```

sem estabilidade.

---

# 63. Model Drift

Monitorizar:

- Brier;
- Log Loss;
- calibration;
- CLV;
- ROI;
- feature distributions;
- prediction distributions.

Detetar:

```text
data drift
concept drift
performance drift
market drift
```

---

# 64. Model Health Dashboard

Exemplo:

```text
MODEL HEALTH

Calibration          96.2%
Brier                0.182
Log Loss             0.549
CLV                  +3.7%
ROI                  +4.1%
Max Drawdown         -9.2%

Data Quality         97%
Model Agreement      92%
Drift                LOW
```

As cores verde/amarelo/vermelho devem representar thresholds previamente definidos e não uma opinião subjetiva.

---

# 65. Match Analysis Page

Cada jogo terá:

## Header

```text
PLAYER A
vs
PLAYER B

Tournament
Round
Surface
Date
```

## Prediction

```text
Player A 63.7%
Player B 36.3%
```

## Fair Odds

```text
A 1.57
B 2.75
```

## Model Agreement

```text
Elo       61.2%
XGB       65.1%
Bayesian  63.8%
Sim       64.0%
```

---

# 66. Player Comparison

Tabela:

```text
Metric              Player A   Player B

Global Elo             ...
Surface Elo            ...
Form                   ...
Serve Rating           ...
Return Rating          ...
Hold %                 ...
Break %                ...
Fatigue                ...
Rest                   ...
Travel                 ...
```

---

# 67. Matchup Analysis

```text
A serve vs B return
B serve vs A return
A baseline vs B baseline
A style vs B style
```

Outputs:

```text
Expected Hold
Expected Break
Expected Games
Expected Sets
Expected Tiebreaks
```

---

# 68. Market Analysis

Tabela:

```text
Market
Model Probability
Fair Odds
Best Market Odds
Market No-Vig Probability
Edge
EV
Confidence
```

---

# 69. Odds History

Gráfico:

```text
Opening
    \
     \
      Current
        \
         Closing
```

Por bookmaker.

---

# 70. Historical Similarity

Encontrar situações históricas semelhantes:

```text
Surface
Ranking difference
Elo difference
Serve difference
Return difference
Fatigue
Market odds
```

E mostrar:

```text
Similar matches = N

Predicted range
Actual outcomes
Historical calibration
Historical CLV
```

Nunca usar esta amostra como prova definitiva.

---

# 71. Betting Terminal

Página principal:

```text
TODAY

ALL MATCHES
VALUE SCANNER
MARKET MOVERS
UPCOMING
MODEL ALERTS
```

Filtros:

```text
ATP / WTA
Surface
Tournament
Market
Odds
EV
Edge
Confidence
Bookmaker
```

---

# 72. Value Scanner

Exemplo:

```text
MATCH              MARKET       ODDS   MODEL   FAIR   EV

A vs B             O22.5        1.91   57.1%   1.75   +8.9%
C vs D             ML           2.10   51.9%   1.93   +9.0%
E vs F             -2.5         1.95   55.8%   1.79   +8.8%
```

Ordenação deve poder ser alterada por:

- EV;
- edge;
- confidence;
- CLV expectation;
- data quality.

Não apresentar uma "ranking of best bets" como verdade absoluta. A ordenação é apenas uma forma de explorar sinais segundo critérios definidos.

---

# 73. Bet Journal

Registar:

```text
signal
timestamp
market
odds
stake
result
closing odds
CLV
model version
strategy
```

Dashboard:

```text
Total bets
Profit
ROI
CLV
Drawdown
Calibration
```

---

# 74. Bankroll Simulator

Permitir:

- flat staking;
- fixed percentage;
- fractional Kelly;
- Kelly apenas como ferramenta matemática;
- custom staking.

Simular:

```text
starting bankroll
number of bets
expected edge
variance
```

Não apresentar nenhuma estratégia de staking como garantia de lucro.

---

# 75. Data Quality Dashboard

Para cada jogo:

```text
Stats           100%
Odds             99%
PBP              97%
News             84%
Injury           76%
Weather         100%

Overall          94%
```

Se informação essencial estiver ausente:

```text
DATA INSUFFICIENT
```

---

# 76. AI Analyst

A IA recebe apenas outputs estruturados.

Input:

```text
probabilities
fair odds
features
model contributions
uncertainty
market data
historical metrics
```

Output:

- resumo;
- principais fatores;
- mercados relevantes;
- explicação quantitativa;
- riscos;
- informação em falta.

A IA não deve inventar estatísticas.

---

# 77. Explainability

Utilizar:

- SHAP;
- feature importance;
- permutation importance;
- partial dependence quando adequado.

Exemplo:

```text
Factors increasing Player A probability

Surface Elo            +3.8pp
Return advantage        +2.1pp
Rest differential       +1.4pp
Serve matchup           +1.1pp
Fatigue                  -0.7pp
```

Os valores devem ser derivados do modelo.

---

# 78. Alert System

Alertas:

```text
New value signal
Odds moved significantly
Model probability changed
Injury news
Market divergence
Data quality issue
Model drift
Unexpected model disagreement
```

---

# 79. Live Betting — Fase posterior

Só depois do pré-jogo estar validado.

Live engine:

```text
Current score
Serve
Point probability
Player state
Fatigue
Momentum proxy
Market odds
```

Atualizar:

```text
P(match win)
P(next set)
P(next game)
P(total games)
```

Não confundir atualização estatística com causalidade de "momentum".

---

# 80. Technology Stack

## Backend

Python

- FastAPI
- Polars
- NumPy
- SciPy
- pandas
- scikit-learn
- XGBoost
- LightGBM
- PyMC

## Database

PostgreSQL

Possivelmente:

- TimescaleDB
- Redis para cache

## Data orchestration

Inicialmente:

- Prefect

Escala:

- Airflow / Dagster

## Frontend

- Next.js
- TypeScript
- Tailwind
- Recharts
- ECharts

## Infrastructure

Inicialmente:

- Docker
- PostgreSQL
- cloud object storage
- Vercel para frontend se conveniente

---

# 81. Estrutura do projeto

```text
tennis-quant/
│
├── apps/
│   ├── api/
│   ├── dashboard/
│   └── worker/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── features/
│
├── models/
│   ├── elo/
│   ├── logistic/
│   ├── xgboost/
│   ├── bayesian/
│   ├── simulation/
│   └── ensemble/
│
├── backtesting/
│   ├── engine/
│   ├── strategies/
│   ├── metrics/
│   └── reports/
│
├── features/
│   ├── ranking/
│   ├── serve/
│   ├── return/
│   ├── fatigue/
│   ├── surface/
│   ├── matchup/
│   ├── weather/
│   └── market/
│
├── ingestion/
│   ├── results/
│   ├── odds/
│   ├── news/
│   └── weather/
│
├── simulation/
├── notebooks/
├── tests/
├── configs/
└── docs/
```

---

# 82. Fases de desenvolvimento

## Phase 0 — Research

Definir:

- fontes;
- custos;
- cobertura;
- schema;
- métricas;
- metodologia.

## Phase 1 — Data Warehouse

Construir:

- players;
- tournaments;
- matches;
- results;
- rankings;
- stats.

## Phase 2 — Historical Dataset

2015–2026, quando disponível.

## Phase 3 — Feature Engine

Primeiras 100–200 features.

## Phase 4 — Baseline Models

- Elo;
- logistic;
- market baseline.

## Phase 5 — ML

- XGBoost;
- LightGBM;
- calibration.

## Phase 6 — Simulation

Point → Game → Set → Match.

## Phase 7 — Odds Engine

Odds históricas + current odds.

## Phase 8 — Value Engine

Fair odds + EV + edge.

## Phase 9 — Backtesting

Walk-forward + OOS + bootstrap.

## Phase 10 — Dashboard

Match pages + scanner.

## Phase 11 — News / Injury

## Phase 12 — Advanced PBP

## Phase 13 — Shot Data

## Phase 14 — Live

---

# 83. MVP

O primeiro MVP deve ser pequeno mas quantitativamente sólido.

### Dados

- ATP/WTA;
- 2015–2026;
- resultados;
- rankings;
- stats;
- superfície;
- odds.

### Features

- Elo;
- surface Elo;
- ranking;
- form;
- serve;
- return;
- H2H;
- opponent adjustment;
- fatigue básica.

### Modelos

- Elo;
- Logistic;
- XGBoost.

### Output

- win probability;
- fair odds;
- EV;
- edge.

### Backtest

- walk-forward;
- historical odds;
- ROI;
- CLV;
- Brier;
- Log Loss;
- drawdown.

---

# 84. Critérios para considerar o MVP válido

Não basta "ter ROI positivo".

O MVP deve demonstrar:

1. ausência de leakage;
2. calibration aceitável;
3. performance fora da amostra;
4. estabilidade por período;
5. estabilidade por superfície;
6. estabilidade por odds range;
7. CLV positivo ou informativo;
8. resultados não dependentes de poucas apostas;
9. performance comparada com baselines;
10. reproducibilidade.

---

# 85. Métricas principais da plataforma

## Prediction

- Brier Score
- Log Loss
- Calibration
- ECE

## Betting

- ROI
- Yield
- Profit
- Hit Rate
- EV
- Edge

## Market

- CLV
- Opening-to-close movement
- Best price
- Market median

## Risk

- Max Drawdown
- Volatility
- Losing streak
- Bankroll trajectory

## Data

- Completeness
- Freshness
- Source reliability
- Coverage

---

# 86. Princípios de engenharia

1. Nunca sobrescrever raw data.
2. Nunca usar informação futura.
3. Todas as previsões têm timestamp.
4. Todas as previsões têm model version.
5. Todas as features têm version.
6. Backtests devem ser reproduzíveis.
7. Resultados devem ser auditáveis.
8. Separar research de production.
9. Não selecionar modelos pelo resultado de um único período.
10. Não confundir correlação com causalidade.
11. Não inventar dados ausentes.
12. Guardar a origem de cada informação.

---

# 87. Segurança estatística

Evitar:

- overfitting;
- p-hacking;
- cherry-picking;
- survivorship bias;
- look-ahead bias;
- selection bias;
- data leakage;
- múltiplos testes sem controlo;
- otimização excessiva dos thresholds.

---

# 88. Regra para novas features

Uma nova feature só entra em produção se:

```text
1. Existe racional estatístico
2. Está disponível point-in-time
3. Não tem leakage
4. Tem cobertura suficiente
5. Melhora validação
6. Mantém estabilidade OOS
7. Não depende de um pequeno número de casos
```

---

# 89. Regra para novas estratégias

Uma estratégia deve passar:

```text
Historical Backtest
        ↓
Walk-forward
        ↓
Out-of-sample
        ↓
Sensitivity
        ↓
Bootstrap
        ↓
Paper tracking
        ↓
Production candidate
```

---

# 90. Paper Trading

Antes de qualquer utilização real:

- executar sinais em tempo real;
- guardar odds;
- guardar sinais;
- simular execução;
- medir CLV;
- medir slippage;
- comparar com backtest.

---

# 91. Execution Reality

O backtest deve considerar:

- odd realmente disponível;
- timestamp;
- delay;
- market suspension;
- line movement;
- stake limits quando disponíveis;
- missing odds;
- bookmaker downtime.

Um backtest que assume sempre a melhor odd histórica disponível pode ser artificialmente otimista.

---

# 92. Market Efficiency Analysis

Estudar:

```text
Model vs Market
```

por:

- ATP/WTA;
- surface;
- tournament;
- odds range;
- favorite/underdog;
- market type;
- bookmaker;
- time before match.

Objetivo:

descobrir onde o modelo acrescenta informação.

---

# 93. Market Regime Detection

O mercado pode comportar-se de maneira diferente em diferentes períodos.

Criar análises:

```text
2018–2020
2021–2022
2023–2024
2025–2026
```

e também por:

- ATP/WTA;
- bookmaker;
- market type.

---

# 94. Similar Match Engine

Para qualquer jogo:

```text
Find historical matches
with similar:
- Elo difference
- surface
- serve difference
- return difference
- ranking
- odds
- fatigue
```

Depois mostrar:

```text
N = 2,417
Observed win rate
Observed distribution
Observed CLV
```

---

# 95. Model Explanation

Para cada sinal:

```text
WHY?

1. Surface mismatch
2. Serve advantage
3. Return advantage
4. Rest advantage
5. Opponent-adjusted form
6. Market price discrepancy
```

Mas sempre apresentar números.

---

# 96. Example final analysis

```text
SINNER vs ZVEREV

MODEL
Sinner: 63.7%
Zverev: 36.3%

FAIR
Sinner: 1.57
Zverev: 2.75

MARKET
Sinner: 1.72
Zverev: 2.15

EDGE
+6.8 percentage points

EV
+9.6%

UNCERTAINTY
53.1%–69.2%

MODEL AGREEMENT
High

DATA QUALITY
94/100

CLV HISTORY
+3.7%

KEY FACTORS
Surface-adjusted serve +3.2pp
Return matchup +2.4pp
Fatigue +1.1pp
H2H +0.4pp
```

---

# 97. O que a plataforma NÃO deve fazer

Não:

- garantir lucro;
- apresentar previsões como certezas;
- inventar notícias;
- inventar lesões;
- usar informação futura;
- esconder resultados negativos;
- apagar sinais perdedores;
- alterar modelos retroativamente;
- selecionar apenas backtests favoráveis;
- confundir bom backtest com garantia futura.

---

# 98. Roadmap de longo prazo

## Version 1

ATP/WTA pre-match.

## Version 2

Advanced player modeling.

## Version 3

Point-by-point.

## Version 4

News + injury.

## Version 5

Weather + travel + fatigue.

## Version 6

Advanced props.

## Version 7

Live models.

## Version 8

Automated model retraining.

## Version 9

Cross-sport architecture.

Possíveis extensões:

- futebol;
- basquetebol;
- NFL;
- NHL;
- F1;
- baseball.

A arquitetura deve ser construída de forma a permitir isso no futuro.

---

# 99. End State

O produto final deverá parecer mais com:

```text
BLOOMBERG / QUANT TERMINAL
             +
SPORTS ANALYTICS
             +
BETTING MARKET ANALYSIS
```

do que com:

```text
AI BETTING BOT
```

A plataforma deve conseguir responder quantitativamente:

> Quem tem maior probabilidade de ganhar?

> Quantos sets são esperados?

> Quantos games?

> Qual a distribuição de resultados?

> Qual a fair odd?

> Qual o preço atual?

> Qual a diferença entre mercado e modelo?

> Qual o EV?

> Qual a incerteza?

> Como o mercado se moveu?

> O modelo costuma acertar situações semelhantes?

> Qual o CLV histórico?

> O modelo está calibrado?

> Existe model drift?

> O sinal sobrevive a backtesting out-of-sample?

> Qual o risco de drawdown?

> Quais os mercados onde o modelo historicamente acrescenta mais informação?

---

# 100. Ordem recomendada de implementação

A ordem deve ser:

```text
1. Data architecture
2. Historical data ingestion
3. Data validation
4. Database
5. Point-in-time framework
6. Feature engine
7. Elo baseline
8. Logistic baseline
9. XGBoost
10. Probability calibration
11. Match simulation
12. Odds ingestion
13. Fair odds
14. Value engine
15. Backtesting
16. CLV
17. Strategy Lab
18. Dashboard
19. News
20. Injuries
21. Weather
22. PBP
23. Shot data
24. Live
```

---

# 101. Primeira tarefa prática

O primeiro sprint deve produzir:

```text
Tennis Quant v0.1

✓ PostgreSQL schema
✓ Player database
✓ Tournament database
✓ Match database
✓ Historical results
✓ Rankings
✓ Match stats
✓ Surface
✓ Elo
✓ Surface Elo
✓ Form metrics
✓ Serve metrics
✓ Return metrics
✓ Basic fatigue
✓ Baseline probability
✓ Historical backtest
✓ Basic odds integration
✓ Fair odds
✓ EV
✓ Basic dashboard
```

Só depois avançar para features mais complexas.

---

# 102. Resultado esperado

No final do primeiro grande ciclo, devemos ter uma plataforma em que seja possível:

```text
Abrir a plataforma
        ↓
Escolher "Ténis"
        ↓
Ver todos os jogos
        ↓
Ver todos os mercados
        ↓
Filtrar oportunidades
        ↓
Abrir um jogo
        ↓
Ver análise quantitativa completa
        ↓
Ver fair odds
        ↓
Ver odds reais
        ↓
Ver EV
        ↓
Ver incerteza
        ↓
Ver backtest de situações semelhantes
        ↓
Ver histórico de odds
        ↓
Ver CLV
        ↓
Ver explicação dos principais fatores
```

O objetivo não é simplesmente produzir "palpites".

O objetivo é construir uma **infraestrutura quantitativa auditável para estimar probabilidades, avaliar preços de mercado e estudar se determinadas estratégias possuem evidência histórica de valor**.

---

# 103. Nota final sobre apostas

A plataforma deve ser tratada como uma ferramenta estatística e de investigação. Backtests e expected value são estimativas sujeitas a erro de modelo, custos de execução, mudanças de mercado e variância. Resultados históricos não garantem resultados futuros.

