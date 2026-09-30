"""Build an evidence-linked study report from completed experiment artifacts."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / "artifacts"
    first = json.loads((out / "innovation_research.json").read_text(encoding="utf-8"))
    final = json.loads((out / "enrichment_research.json").read_text(encoding="utf-8"))
    controls = [json.loads((out / f"{name}_placebo.json").read_text(encoding="utf-8")) for name in ("innovation", "enrichment")]
    arrays = np.load(out / "enrichment_predictions.npz")
    selected, y, years = final["selected"], arrays["y"], arrays["years"]
    metrics = {}
    for label, mask in (("development", (years >= 2019) & (years <= 2023)),
                        ("diagnostic", (years >= 2024) & (years <= 2026))):
        metrics[label] = {}
        for name in ("v4", "v5_layoff", selected):
            p = arrays[name][mask]
            target = y[mask]
            bucket = np.minimum((p * 10).astype(int), 9)
            ece = sum(np.mean(bucket == b) * abs(np.mean(target[bucket == b]) - np.mean(p[bucket == b]))
                      for b in range(10) if np.any(bucket == b))
            metrics[label][name] = {"accuracy": float(np.mean((p >= .5) == target)), "ece_10": float(ece)}
    files = ["apps/api/tennis_quant/innovation.py", "apps/api/tennis_quant/research_metadata.py",
             "apps/api/tennis_quant/features.py", "apps/api/tennis_quant/model.py",
             "scripts/research_innovation.py", "scripts/research_enrichment.py", "scripts/research_placebo.py",
             "scripts/predict_research.py"]
    forward = sorted((out / "forward").glob("*.json"))
    audit = {"created_at": datetime.now(timezone.utc).isoformat(), "additional_metrics": metrics,
             "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
             "artifact_sha256": hashlib.sha256((out / final["artifact"]).read_bytes()).hexdigest(),
             "new_model_configurations": 14, "references": 2, "shuffle_controls": 6,
             "forward_snapshots": [p.name for p in forward]}
    (out / "research_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    lines = ["# Evolução quantitativa do Tennis Quant — 30-09-2026", "",
             "O novo candidato reduz o erro probabilístico histórico face ao XGBoost v4 e ao desafiante v5. Está treinado e aplicado a previsões futuras congeladas, em modo de investigação. Não há confirmação prospectiva nem evidência de rentabilidade.", "",
             "## Resultado principal", "",
             "Comparação com origens móveis idênticas; Brier e log loss menores são melhores. Os valores abaixo são agregados por jogo, distintos da média anual usada para selecionar.", "",
             "| Período | Jogos | Brier v4 | Brier novo | Redução relativa | Log loss v4 | Log loss novo |", "|---|---:|---:|---:|---:|---:|---:|"]
    for period, label in (("development", "2019–2023 · desenvolvimento"), ("diagnostic", "2024–maio 2026 · diagnóstico")):
        pair = final[period]["v4"]
        a, b = pair["baseline"], pair["selected"]
        lines.append(f"| {label} | {a['n']:,} | {a['brier']:.6f} | {b['brier']:.6f} | {(1-b['brier']/a['brier'])*100:.2f}% | {a['log_loss']:.6f} | {b['log_loss']:.6f} |")
    lines += ["", "Fonte: `artifacts/enrichment_research.json`, `development.v4` e `diagnostic.v4`.", "",
              "| Comparação | Melhoria de Brier | Intervalo bootstrap 95% | Torneios |", "|---|---:|---|---:|"]
    for period in ("development", "diagnostic"):
        for reference in ("v4", "v5_layoff"):
            p = final[period][reference]["paired"]
            lines.append(f"| {period} / {reference} | {p['improvement']:.6f} | [{p['bootstrap_95'][0]:.6f}; {p['bootstrap_95'][1]:.6f}] | {p['n_tournaments']} |")
    simultaneous = final["simultaneous_all_rounds"][selected]
    lines += ["", f"Em desenvolvimento, intervalo simultâneo face ao v5: [{simultaneous['simultaneous_95'][0]:.6f}; {simultaneous['simultaneous_95'][1]:.6f}], incluindo as comparações das duas rondas desta sessão. Bootstrap pareado de 2 000 amostras por torneio. Não corrige as escolhas das sessões anteriores. Fonte: `simultaneous_all_rounds.all_metadata_context`.", "",
              "Os intervalos são aproximações por reamostragem de torneios; dependência entre torneios através dos mesmos jogadores não é modelada. Não constituem garantia de melhoria futura.", "",
              "## O que foi acrescentado", "",
              "O XGBoost mantém os seus parâmetros anteriores. O ganho vem de informação adicional: filtro de aptidão e incerteza inspirado em xadrez; aptidões de serviço/resposta ajustadas à oposição e à superfície, inspiradas em ataque/defesa de videojogos; proporção histórica de jogos ganhos nos sets suportados; cadeia ponto–jogo–set–encontro; idade, curva de idade, altura e pontos de ranking recuperados dos CSV; interação entre Elo e formato de três/cinco sets. O modelo final usa 27 variáveis, contra 11 no v4.", "",
              "As fontes primárias e adaptações estão em [RESEARCH_2026-09-30.md](RESEARCH_2026-09-30.md). As implementações são aproximações próprias, não reproduções integrais de Glicko ou TrueSkill.", "",
              "## Todas as configurações", "",
              "14 configurações novas, duas referências e seis controlos baralhados. O projeto já tinha documentado 15 configurações e três controlos anteriores; essas tentativas continuam relevantes para o risco de seleção múltipla.", "",
              "| Configuração | Brier médio anual 2019–2023 |", "|---|---:|"]
    for name, value in sorted(final["all_development_scores"].items(), key=lambda item: item[1]):
        lines.append(f"| {'**'+name+'**' if name == selected else name} | {value:.6f} |")
    lines += ["", "Fonte: `enrichment_research.json/all_development_scores`; detalhes anuais nas duas folhas JSON `results/<configuração>/yearly`. Os modelos isolados Markov e de aptidão dinâmica perderam; separar ATP/WTA também ficou abaixo do modelo agregado com a mesma informação. A interação de formato melhora apenas ligeiramente sobre `all_metadata`; não há uma ablação que atribua todo o ganho a uma variável específica.", "",
              "| Controlo | Seed | Brier médio anual |", "|---|---:|---:|"]
    for control in controls:
        for seed, values in control["controls"].items():
            lines.append(f"| {control.get('target', 'all')} baralhado | {seed} | {values['mean_annual_brier']:.6f} |")
    lines += ["", "Fontes: `innovation_placebo.json/controls` e `enrichment_placebo.json/controls`. As colunas adicionais são baralhadas conjuntamente dentro de circuito/ano; não são features deployáveis nem testes de lucro. Os seis controlos perderam contra o v5 e contra os candidatos reais.", "",
              "## Estabilidade e calibração", "",
              "| Ano | Brier v4 | Brier novo | Acerto v4 | Acerto novo |", "|---|---:|---:|---:|---:|"]
    for year in range(2019, 2027):
        mask = years == year
        a, b, target = arrays["v4"][mask], arrays[selected][mask], y[mask]
        lines.append(f"| {year} | {np.mean((a-target)**2):.6f} | {np.mean((b-target)**2):.6f} | {np.mean((a>=.5)==target)*100:.2f}% | {np.mean((b>=.5)==target)*100:.2f}% |")
    lines += ["", "O Brier melhora nos oito anos, mas o acerto desce em 2026 parcial. A qualidade de probabilidades e a taxa de acerto são objetivos diferentes. Fonte: `enrichment_predictions.npz`, máscaras `years`, previsões `v4` e `all_metadata_context`.", "",
              "| Subgrupo diagnóstico | Jogos | Brier v5 | Brier novo |", "|---|---:|---:|---:|"]
    for label, pair in final["diagnostic"]["subgroups"].items():
        lines.append(f"| {label} | {pair['baseline']['n']} | {pair['baseline']['brier']:.6f} | {pair['selected']['brier']:.6f} |")
    lines += ["", "Todos os cinco subgrupos melhoram em Brier, mas a vantagem na relva é pequena e não foi estabelecida significância individual. Fonte: `diagnostic.subgroups`.", ""]
    for period in metrics:
        a, b = metrics[period]["v4"], metrics[period][selected]
        lines.append(f"ECE de 10 intervalos / {period}: v4 {a['ece_10']:.6f}, novo {b['ece_10']:.6f}. Acerto agregado: {a['accuracy']*100:.2f}% → {b['accuracy']*100:.2f}%. Fonte: `research_audit.json/additional_metrics/{period}`.")
    lines += ["", "## Cobertura e limites", "",
              f"Arquivo: {first['n']:,} jogos elegíveis. {first['coverage']['service_observations']:,} observações jogador/serviço válidas; {first['coverage']['score_observations']:,} scores com pelo menos um set suportado. Metadados anteriores: idade {final['coverage']['prior_age']:,}, altura {final['coverage']['prior_height']:,}, pontos de ranking {final['coverage']['prior_ranking_points']:,}, num total de {final['coverage']['player_snapshots']:,} snapshots jogador/encontro. Fontes: `innovation_research.json/coverage` e `enrichment_research.json/coverage`.", "",
              "Todas as features de resultado/metadados são lidas antes de atualizar o bloco circuito/data. Idade e ranking usam observações de torneios anteriores. O modelo de pontos assume iid, limita a contagem efetiva e usa priors fixos por circuito; a cadeia aproxima regras de desempate e continuidade do serviço entre sets. O score usa apenas sets até sete jogos e exclui os longos/ambíguos. Estes limites são conhecidos, não incertezas resolvidas.", "",
              "2024+ já tinha sido consultado e a segunda ronda ocorreu depois do diagnóstico da primeira. É diagnóstico retrospectivo, não holdout intocado. Não foram encontrados resultados posteriores ao arquivo original nas fontes consultadas; os repositórios originais devolveram 404 e o espelho é um snapshot. Não há novos dados externos de treino nesta entrega, nem odds temporizadas que permitam inferir lucro.", "",
              "## Aplicação e reprodução", "",
              f"Candidato treinado: `artifacts/{final['artifact']}`. A API `/api/models` expõe os quatro relatórios de investigação. As probabilidades operacionais do v4 mantêm a referência para comparação futura.", ""]
    for path in forward:
        snapshot = json.loads(path.read_text())
        lines.append(f"Previsões congeladas: `artifacts/forward/{path.name}`, {len(snapshot['forecasts'])} encontros, {len(snapshot['skipped'])} excluídos. Inclui probabilidade v4, probabilidade nova, features, instante anterior ao jogo e checksum do artefacto. Estado: investigação; não são recomendações.")
    lines += ["", "```powershell", ".venv/Scripts/python.exe scripts/research_innovation.py",
              ".venv/Scripts/python.exe scripts/research_enrichment.py", ".venv/Scripts/python.exe scripts/research_placebo.py",
              ".venv/Scripts/python.exe scripts/research_placebo.py --enrichment", ".venv/Scripts/python.exe -m pytest -q",
              ".venv/Scripts/python.exe scripts/predict_research.py --day AAAA-MM-DD --refresh",
              ".venv/Scripts/python.exe scripts/summarize_research.py", "```", "",
              "Verificação executada nesta sessão: 13 testes passaram, incluindo cronologia, simetria, metadados inválidos e reprodução das previsões 2026 pelo vetor de inferência. Checksum do código e modelo em `research_audit.json`.", "",
              "## 🟠 Por executar — confirmação", "",
              "- Acumular previsões congeladas e resultados novos com correspondência verificável; três previsões ainda não medem capacidade prospectiva.",
              "- Atualizar o arquivo de resultados com fonte e cronologia auditáveis; o estado dos jogadores continua limitado a maio de 2026.",
              "- Avaliar deriva de calibração e intervalos por subgrupo; verificar a pequena vantagem na relva.",
              "- Recolher odds com hora real e custos antes de testar qualquer estratégia de aposta.",
              "- Estudar pontos a ponto, lesões e contexto de torneio quando houver dados temporizados suficientes. Nenhuma destas pendências é apresentada como resultado validado."]
    (ROOT / "docs" / "RESULTS_2026-09-30.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"selected": selected, "metrics": metrics, "report": "docs/RESULTS_2026-09-30.md"}, indent=2))


if __name__ == "__main__":
    main()
