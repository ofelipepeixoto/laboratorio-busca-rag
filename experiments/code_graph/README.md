# Code-Graph-RAG: estudo de manutenção de código

Decisão **B — STUDY**, autorizada após a auditoria de 06/10/2026. Este estudo
fica no laboratório existente. Não substitui o RAG documental nem depende do
experimento Jevbox da [PR #4](https://github.com/ofelipepeixoto/laboratorio-busca-rag/pull/4).
Nenhum arquivo daquele experimento ou README principal foi alterado.

A segunda camada, com o indexador real, comandos e limitações de isolamento,
está em [COMPARISON.md](COMPARISON.md). Permanece experimental e dependente
da revisão do corpus e baseline.

## Etapa 1: corpus e baseline

```sh
python3 experiments/code_graph/evaluate.py
python3 -m unittest discover -s experiments/code_graph -p 'test_baseline.py' -v
```

São seis arquivos Python fictícios e 20 tarefas rotuladas manualmente antes da
execução do grafo: dez de desenvolvimento e dez de reserva. `manifest.json`
congela os bytes dos arquivos e das tarefas. Não altere os rótulos para melhorar
pontuações; uma correção de corpus exige versão nova e invalida a reserva.
Os módulos são **dados**, não devem ser importados/executados. `entry.py`
contém uma exceção intencional para detectar execução acidental.

As operações são localizar definição, chamadores diretos e módulos importadores.
`symbol` identifica o alvo qualificado dentro da fixture; `term` é seu nome
literal para busca textual. `expected` lista os arquivos relevantes, não os
arquivos que apenas mencionam o nome. Chamadas dinâmicas não estão rotuladas.
Os rótulos podem ser conferidos diretamente nas seis fontes curtas.

A busca textual devolve até três arquivos com o termo completo, ordenados por
número de linhas correspondentes e nome do arquivo como desempate. Não interpreta
o tipo da pergunta, comentários ou nomes qualificados. É um baseline simples,
**não representa o Codex, um humano lendo código ou uma busca textual otimizada**.

Métricas: precisão e recall micro sobre conjuntos de arquivos retornados (até 3),
além de acerto exato do conjunto. Resultado errado conta falso positivo e omissão;
abstenção só é exata quando o esperado está vazio. Não há geração por LLM.

| Busca literal | Conjunto exato | Precisão até 3 | Recall até 3 |
| --- | ---: | ---: | ---: |
| Desenvolvimento | 0/10 | 0,333 | 0,900 |
| Reserva | 1/10 | 0,400 | 1,000 |

Resultados por tarefa e linhas recuperadas: `baseline.json`. Comentários com
nomes repetidos e símbolos homônimos tornam o corpus deliberadamente adversarial
à busca literal. A reserva compartilha módulos e padrões com desenvolvimento;
não é amostra independente de repositórios reais. Não permite afirmar ganho
generalizável, economia de tempo ou qualidade de respostas.

## Sequência e critérios

1. Revisar corpus, expectativas e baseline nesta PR.
2. PR dependente: executar o indexador upstream fixado, comparar sem ajustar a
   reserva e documentar falhas, proveniência, limites e isolamento efetivamente usado.
3. Antes de integrar: avaliar uma busca textual mais forte, outro corpus ainda
   não visto, isolamento de sistema operacional, privacidade de todos os logs e
   custos/latência em repositórios representativos.
4. Somente com evidência e revisão: adapter restrito no Hub, catálogo no Control
   Plane e eventual orquestração n8n. Não criar servidor MCP ou repositório novo.

Uma PR deve manter uma unidade revisável; testes e documentação acompanham o
código. PRs dependentes permanecem rascunho até revisão da base; nenhum merge
automático. Não ativar workflows n8n, usar credenciais, chamar IA paga ou instalar
infraestrutura de produção como consequência deste estudo.

Código e dados originais Radar nesta pasta: licença MIT em
`../../licenses/RADAR-CONTROLS-MIT.txt`. Code-Graph-RAG é de Vitali Avagyan e
contribuidores, também MIT; os créditos upstream devem ser preservados. O estudo
não relicencia Memgraph ou outras dependências e não exige banco de grafo.
