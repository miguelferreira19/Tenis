# Tennis Quant v0.4 — piloto automático

**Site:** https://miguelferreira19.github.io/Tenis/ — abre em «Apostas de hoje».

De 2 em 2 horas a tarefa do Windows «TennisQuant Piloto» (no teu PC, `scripts/autopilot_local.ps1`; a Betclic bloqueia os servidores do GitHub) lê as odds públicas da Betclic, escolhe as apostas da estratégia, calcula os montantes, fecha os resultados com a ESPN e envia o livro para o GitHub, que reconstrói o site. Com o PC desligado não há apostas novas; os resultados continuam a ser fechados no site. Tu só abres o link de cada jogo na Betclic, apostas o montante indicado e marcas «Já apostei». Os montantes ajustam-se à banca que escreves no site (guardada só no teu browser).

- Estratégia, regras de banca e resultados esperados: página **Estratégia** do site e [docs/RESULTS_2026-10-02.md](docs/RESULTS_2026-10-02.md).
- Retorno esperado da estratégia: **negativo (~−2% por euro)**. Usa a conta demo para confirmar antes de usar dinheiro.
- O piloto não coloca apostas. O clique final é sempre teu.

Correr em local (Windows):

```powershell
.\.venv\Scripts\python.exe scripts\autopilot.py           # lê a Betclic, decide, fecha resultados
.\.venv\Scripts\python.exe scripts\backtest_strategy.py   # refaz o backtest da estratégia
.\.venv\Scripts\python.exe scripts\research_market.py     # modelo contra mercado (ronda 4)
```

---

## Plataforma de investigação (v0.3)

Investigação de 30-09-2026: [estudo de metodologias](docs/RESEARCH_2026-09-30.md) e [resultados completos](docs/RESULTS_2026-09-30.md). Novo candidato com aptidão dinâmica, serviço ajustado à oposição, margens e metadados; comparação de 14 configurações adicionais, seis controlos e previsões futuras congeladas. Continua em investigação, com referência operacional v4 para comparação prospectiva.

Assistente local de análise de ténis. Integra calendário atual ATP/WTA, leitura rápida dos jogos de hoje, resultados recentes, arquivo e backtesting de probabilidades, odds atuais quando existe uma chave, e calculadora de combinadas. **Sem recomendações nem sinais de aposta aprovados.**

## Arranque local (Windows)

Requer Python 3.14+ e Node.js 24+. O primeiro arranque precisa de acesso à Internet para instalar dependências e descarregar os dados de investigação.

```powershell
cd 'C:\Users\migue\Documents\Codex\2026-09-27\que\outputs\tennis-quant'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\bootstrap.py
```

Terminal 1:

```powershell
cd 'C:\Users\migue\Documents\Codex\2026-09-27\que\outputs\tennis-quant'
$env:PYTHONPATH='apps/api'
.\.venv\Scripts\python.exe -m uvicorn tennis_quant.api:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd 'C:\Users\migue\Documents\Codex\2026-09-27\que\outputs\tennis-quant\apps\dashboard'
npm install
npm run dev
```

Abre [http://127.0.0.1:3000](http://127.0.0.1:3000). A documentação interativa da API está em [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### No telemóvel

Com o computador ligado e o telemóvel na mesma rede Wi-Fi, abre **http://192.168.1.213:3000** no browser do telemóvel. Este é o endereço local atual do computador e pode mudar quando a rede atribuir outro IP. Para consultar o novo endereço, corre `Get-NetIPAddress -AddressFamily IPv4 | Where-Object InterfaceAlias -eq 'Wi-Fi'` e substitui o IP no URL. O painel escuta na rede; a API permanece em `127.0.0.1:8000` e é acedida através do painel. A ligação pelo IP local e o proxy `/api` foram testados neste computador; a abertura no telemóvel depende da rede e da firewall locais. Não há acesso fora da rede Wi-Fi nesta instalação.

Nesta máquina, as dependências e os dados já foram instalados. Para reabrir a plataforma, bastam os comandos dos dois terminais.

## Site publicado (GitHub Pages)

O workflow [`.github/workflows/site.yml`](.github/workflows/site.yml) atualiza sozinho um site estático, de 3 em 3 horas e a cada push: descarrega os CSV fixados, reconstrói a base só com jogos (cerca de 30 s), lê a ESPN, aplica o modelo operacional versionado em `artifacts/`, exporta as respostas da API para JSON (`scripts/export_snapshot.py`) e publica o build estático do painel. Se a ESPN não responder, o workflow falha e o site anterior fica no ar.

Configuração (uma vez): criar o repositório no GitHub, em **Settings → Pages** escolher **Source: GitHub Actions**, fazer push e correr o workflow em **Actions → Atualizar site → Run workflow**. O endereço fica `https://<utilizador>.github.io/<repositório>/`.

No site publicado não existem a pesquisa no arquivo histórico, o cenário de preço e o botão de atualizar odds (precisam da API Python; continuam a funcionar em local). As combinadas são calculadas no browser (`apps/dashboard/lib/parlay.ts`, espelho de `parlay.py`; verificação: `node apps/dashboard/lib/parlay.test.mjs`).

Limites: o arquivo de resultados termina em maio de 2026 e não há fonte atualizada, por isso Elo, forma, descanso e carga refletem essa data (o painel já o avisa). Em repositórios públicos o GitHub desativa workflows agendados após 60 dias sem atividade: basta reativar em **Actions**. Para refazer o modelo, corre `scripts/refit_operational.py` em local e faz commit do novo `artifacts/xgboost-operational-*.joblib` e de `evaluation.json`/`operational.json`.

Testar o build estático em local (PowerShell):

```powershell
.\.venv\Scripts\python.exe scripts\export_snapshot.py
cd apps\dashboard
$env:NEXT_PUBLIC_STATIC='1'; $env:NEXT_PUBLIC_BASE_PATH='/tennis-quant'
npm run build   # resultado em apps/dashboard/out
```

## O que está implementado

- Base de dados com jogadores, torneios, jogos, odds, previsões, versões de modelo, testes e proveniência raw. SQLAlchemy suporta SQLite para arranque local e PostgreSQL via `DATABASE_URL`.
- Importação de resultados ATP/WTA de 2015 até ao último ano disponível no snapshot fixado. Ficheiros raw imutáveis e SHA-256 por fonte.
- Elo global e por superfície, rankings, forma, serviço, resposta, descanso, serviço/resposta por superfície regularizados e carga em 30 dias. Todas as variáveis são calculadas antes de incorporar jogos com a mesma data de início de torneio.
- Elo, regressão logística e XGBoost. Treino: 2015–2021; calibração: 2022; seleção por Brier: 2023; diagnóstico histórico: 2024 em diante. As três famílias são mostradas, incluindo as que perderam.
- Modelo desafiante que acrescenta o tempo desde o último torneio; comparação anual 2019–2026, bootstrap por torneio e controlos com variável baralhada. Está versionado como investigação e não substitui as probabilidades diárias.
- Painel de jogos, detalhe quantitativo, comparação de modelos, backtests anuais e de calibração, auditoria de fontes e cenário manual de fair odd / EV matemático.
- Agenda de jogos futuros alimentada pelo [marcador público ESPN](https://www.espn.com/tennis/scoreboard/), com atualização por data e ligação para a origem. A tab «Jogos de hoje» mostra rapidamente o jogador estatisticamente mais provável e a probabilidade quando ambos os jogadores e o nível da prova estão confirmados para o modelo.
- Resultados dos últimos três dias separados do arquivo de treino. O arquivo antigo permanece identificado como histórico e a entrada da plataforma abre nos próximos jogos.
- Odds por casa, hora e seleção com [The Odds API](https://the-odds-api.com/sports/tennis-odds.html), quando configurada. Preços com mais de seis horas não entram na vista diária; a atualização é manual para controlar créditos.
- Bilhete de simples, combinada, sistema k/N e round robin até oito seleções, incluindo comparação por casa quando há odds recentes para todas as seleções. O cálculo é indicativo e não envia apostas.
- Importador de snapshots de odds por CSV com origem e timestamp. Sem hora real do encontro, estes registos não passam automaticamente a odds elegíveis para backtest.

## Estado quantitativo

**Investigação. Sem sinais de aposta aprovados.** O CSV histórico indica a data de início do torneio, não a hora do jogo. Esta limitação impede verificar preços disponíveis antes de cada encontro. O projeto não calcula ROI, CLV, PBO, DSR ou CPCV a partir de odds inexistentes, nem mostra EV manual como evidência histórica. O teste 2024+ foi consultado durante a evolução do v4; novos jogos futuros são necessários para confirmação.

Os resultados estão em `RESULTS.md`, nos artefactos JSON e nos ecrãs **Modelos** e **Backtests**. Para recalcular: `scripts/bootstrap.py --skip-download`, `scripts/compare_models.py`, `scripts/backtest_predictions.py`, `scripts/refit_operational.py` e `scripts/research_layoff.py`.

## Ligar odds atuais

A instalação atual **não tem chave de odds**. Os jogos futuros e resultados recentes aparecem sem ela; apenas os preços reais ficam vazios. Para usar a [API de odds](https://the-odds-api.com/liveapi/guides/v4/), define a variável no terminal que arranca a API:

```powershell
$env:ODDS_API_KEY='a_tua_chave'
$env:PYTHONPATH='apps/api'
.\.venv\Scripts\python.exe -m uvicorn tennis_quant.api:app --host 127.0.0.1 --port 8000
```

Abre **Próximos jogos** e carrega em **Atualizar odds**. A integração consulta ATP/WTA ativos, região `eu`, mercado `h2h` e até 12 competições por execução. A cobertura de ténis do fornecedor varia; o plano gratuito inclui odds atuais, enquanto o histórico requer plano pago. A aplicação nunca armazena a chave em ficheiros ou na base de dados. Consulta `docs/RESEARCH_2026-09-27.md` para fontes e limites.

Para uma atualização local sem abrir o browser: `.\.venv\Scripts\python.exe scripts\refresh_odds.py --region eu --max-sports 12`. O comando é idempotente para snapshots iguais. Uma execução periódica requer agendamento explícito no sistema e uma chave configurada; não há recolha automática nesta instalação.

## PostgreSQL

O ficheiro `docker-compose.yml` descreve uma instância local. Quando Docker estiver disponível:

```powershell
docker compose up -d postgres
$env:DATABASE_URL='postgresql+psycopg://tennis:local_only_change_me@127.0.0.1:5432/tennis_quant'
.\.venv\Scripts\python.exe scripts\bootstrap.py
```

O caminho SQLite é o que foi executado nesta instalação; PostgreSQL ainda requer teste de integração neste equipamento, onde Docker não está instalado. A API pagina o arquivo e os preços atuais têm índice por jogo/casa/seleção/hora. Para vários utilizadores e recolha contínua, são necessários migrações formais, fila de tarefas e monitorização antes de escalar produção.

## Odds próprias

Formato em `docs/ODDS_FORMAT.csv`. Cada linha requer `match_id`, `market=match_winner`, `selection_id`, `bookmaker`, `decimal_odds`, `observed_at` com timezone e `source_ref`.

```powershell
.\.venv\Scripts\python.exe scripts\import_odds.py C:\caminho\odds.csv --source 'Fornecedor autorizado'
```

O importador rejeita jogos e seleções desconhecidos, preços inválidos, timestamps sem timezone ou futuros e linhas sem proveniência. O ficheiro original fica guardado por checksum. Estes snapshots de jogos históricos não se confundem com a tabela separada de fixtures futuras.

## Estrutura

```text
apps/api/tennis_quant/   API, schema, importação, features e modelos
apps/dashboard/          Next.js, TypeScript e interface
scripts/                 Bootstrap e importador de odds
tests/                   Testes de cronologia e simetria
docs/                    Metodologia, fontes, roadmap e plano original
data/raw/                Ficheiros originais (ignorados pelo Git)
data/tennis_quant.db     Base local (ignorada pelo Git)
artifacts/               Modelos e métricas (ignorados pelo Git)
```

## Licença dos dados

Os dados de resultados são atribuídos a Jeff Sackmann / Tennis Abstract e ao [arquivo espelho](https://github.com/Aneeshers/tennis-sackmann-archive), sob **CC BY-NC-SA 4.0**. São usados aqui para investigação não comercial. Os ficheiros raw não devem ser redistribuídos sem verificar as condições aplicáveis. Ver `docs/DATA_SOURCES.md`.

