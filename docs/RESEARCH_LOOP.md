# Ciclo de evolução — estado em 30-09-2026

## Concluído
- Três rondas: 22 configurações novas, duas referências e seis controlos.
- Candidato atual: recency_730d; ganho incremental ainda incerto. Operacional: v4.
- 33 previsões prospectivas congeladas e identificação por versão.
- Agenda, resultados, navegação e investigação reorganizados; build e 16 testes passaram.

## Próxima ronda — por executar
1. Prioridade: obter resultados completos depois de maio com licença, origem e hora/data verificáveis. Não substituir o arquivo congelado nem misturar resultados ESPN provisórios no treino automaticamente.
2. Fechar resultados das previsões congeladas só com identidade, orientação dos jogadores e hora consistentes. Apresentar métricas por versão, sem duplicar encontros na contagem global.
3. Estudar uma hipótese limitada de pooling entre circuito/superfície com a cobertura atual; fixar especificação e critério antes de correr, registar fracassos e não reutilizar 2024+ como confirmação independente.
4. Validar interface móvel/desktop, filtros, teclado, probabilidades complementares e estados de erro após cada mudança.
5. Rever conteúdo e código numa passagem separada, executar só os testes necessários e atualizar relatório/estado.

## Regras do ciclo
Uma hipótese nova exige pergunta concreta, mecanismo plausível e comparação reproduzível. Não repetir grelhas ou alterar critérios para salvar um resultado fraco. Usar caches existentes após validar IDs/checksums. Nenhuma promoção sem evidência prospectiva suficiente; nenhuma promessa de máximo global ou de lucro. Manter movimentos discretos e controlos nativos. Não acrescentar dependências sem necessidade demonstrada.

Comandos: `.venv/Scripts/python.exe scripts/analyze_research.py`; `.venv/Scripts/python.exe scripts/predict_research.py --day AAAA-MM-DD --refresh`; `.venv/Scripts/python.exe -m pytest -q`; `npm run build` em apps/dashboard.

## Continuidade agendada
Heartbeat neste chat: de duas em duas horas até 30-09-2026 às 23:59 de Lisboa, com aviso apenas em mudanças relevantes. ID: evoluir-tennis-quant-at-ao-fim-do-dia.

## Verificação final da interface
Exportação estática compilada e testada com snapshots reais. Pesquisa, limpeza de filtros, ATP + só estimativas e menu móvel verificados; largura de conteúdo igual à viewport, sem overflow horizontal. Versão publicada e verificada no GitHub Pages; alterações seguintes seguem o mesmo processo autorizado.

## Atualização 13:51 UTC
Fonte recente encontrada e preservada: recent_source_audit.json. Resolver 2 chaves ATP repetidas e 3 conflitos de identidade; rever licença/proveniência WTA. Nenhum treino novo. Primeiro jogo liquidado: candidato da segunda ronda pior que v4; n=1, evidência insuficiente. Ronda seguinte prioriza auditoria do cruzamento de nomes/encontros antes de integrar dados.

## Publicação autorizada
Após alterações, enviar para origin/master e verificar o workflow de GitHub Pages; autorização expressa do utilizador em 30-09-2026. Não deixar melhorias apenas locais.

### Agenda — ordenação do favorito
Adicionada ordenação global por max(p, 1-p), decrescente, com desempate por hora e jogos sem estimativa no fim. Datas visíveis nos cartões. Verificação: node apps/dashboard/lib/agenda.test.mjs (favorito B, empates, valores inválidos, imutabilidade). Não representa garantia de segurança nem valor de aposta.

### Plano e comparação Betclic — 30/09/2026
Consulta manual ao mercado vencedor do encontro de toda a oferta de ténis carregada até ao fim: 140 encontros com duas cotações; 28 correspondências com modelo e 112 sem modelo aplicável (pares, direto, ausência de correspondência). Não inclui outros desportos nem vencedores de competição. Apenas campos de cotações públicas exportados; nenhuma informação da conta. Consulta pontual, cotações com validade de seis horas. Página /plano: banca, exposição já aberta, limites, mínimo hipotético editável, prudência, 1/4 Kelly, alocação determinística, custos mínimos, comparação de combinadas sob independência, exportação. Sem promoção de sinal: exposição real sempre zero. Teste node apps/dashboard/lib/bankroll.test.mjs cobre limites totais, repetição do encontro, mínimos, cotação expirada, iniciado, NaN. A margem de 5 pp é sensibilidade, não intervalo de confiança; não existe estratégia ótima nem rentabilidade afirmada.

## Atualização 15:52 UTC
Dois novos resultados ESPN fechados com a regra de identidade e horas: Frech venceu Jacquemot; Zarazua venceu Bondar. Segunda ronda: 3/3 previsões liquidáveis, ambos os modelos acertam 2/3; Brier v4 0,146072846 vs candidato 0,149322653, log-loss 0,450203394 vs 0,470183153. Candidato pior nesta amostra minúscula; nenhuma promoção. Recency_730d: 30 pendentes. Métricas recalculadas diretamente com math, identidade/horas cobertas pelo teste de liquidação. Auditoria do CSV ATP em cache com SHA verificado: as duas chaves repetidas correspondem a jogos distintos, não linhas idênticas. Uma cruza datas de torneios diferentes, a outra cruza um jogo e um W/O na mesma data. Três IDs têm nomes incompatíveis; manter quarentena até confirmação independente. Evidência por linha anexada ao relatório; não foi escolhido arbitrariamente um registo nem integrado no treino.
