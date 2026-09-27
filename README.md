# Tennis Quant v0.1

Terminal local de investigação quantitativa para ténis, construído a partir do plano fornecido pelo utilizador. Esta versão importa resultados ATP/WTA, calcula variáveis antes do início de cada torneio, compara Elo, regressão logística e XGBoost, calibra probabilidades e apresenta o teste fora da amostra no painel.

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

Nesta máquina, as dependências e os dados já foram instalados. Para reabrir a plataforma, bastam os comandos dos dois terminais.

## O que está implementado

- Base de dados com jogadores, torneios, jogos, odds, previsões, versões de modelo, testes e proveniência raw. SQLAlchemy suporta SQLite para arranque local e PostgreSQL via `DATABASE_URL`.
- Importação de resultados ATP/WTA de 2015 até ao último ano disponível no snapshot fixado. Ficheiros raw imutáveis e SHA-256 por fonte.
- Elo global e por superfície, rankings, forma, serviço, resposta e descanso entre torneios. Todas as variáveis são calculadas antes de incorporar jogos com a mesma data de início de torneio.
- Elo, regressão logística e XGBoost. Treino: 2015–2021; calibração: 2022; seleção por Brier: 2023; teste OOS: 2024 em diante. As três famílias são mostradas, incluindo as que perderam.
- Painel de jogos, detalhe quantitativo, comparação de modelos, auditoria de fontes e cenário manual de fair odd / EV matemático.
- Importador de snapshots de odds por CSV com origem e timestamp. Sem hora real do encontro, estes registos não passam automaticamente a odds elegíveis para backtest.

## Estado quantitativo

**Investigação. Sem sinais de aposta aprovados.** O CSV histórico indica a data de início do torneio, não a hora do jogo. Esta limitação impede verificar preços disponíveis antes de cada encontro. O projeto não calcula ROI, CLV, PBO, DSR ou CPCV a partir de odds inexistentes, nem mostra EV manual como evidência histórica.

Os resultados concretos do teste estão em `artifacts/evaluation.json` e no ecrã **Modelos**. Os valores são recalculados apenas quando se executa `scripts/bootstrap.py`.

## PostgreSQL

O ficheiro `docker-compose.yml` descreve uma instância local. Quando Docker estiver disponível:

```powershell
docker compose up -d postgres
$env:DATABASE_URL='postgresql+psycopg://tennis:local_only_change_me@127.0.0.1:5432/tennis_quant'
.\.venv\Scripts\python.exe scripts\bootstrap.py
```

O caminho SQLite é o que foi executado nesta instalação; PostgreSQL ainda requer teste de integração neste equipamento, onde Docker não está instalado.

## Odds próprias

Formato em `docs/ODDS_FORMAT.csv`. Cada linha requer `match_id`, `market=match_winner`, `selection_id`, `bookmaker`, `decimal_odds`, `observed_at` com timezone e `source_ref`.

```powershell
.\.venv\Scripts\python.exe scripts\import_odds.py C:\caminho\odds.csv --source 'Fornecedor autorizado'
```

O importador rejeita jogos e seleções desconhecidos, preços inválidos, timestamps sem timezone ou futuros e linhas sem proveniência. O ficheiro original fica guardado por checksum.

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

