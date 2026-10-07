# Comparação estrutural — segunda camada

Depende da [PR #5](https://github.com/ofelipepeixoto/laboratorio-busca-rag/pull/5).
Permanecer em rascunho até revisar corpus e baseline. Base do corpus:
`543107a28342fba6e02242d66a702c8c0f605113`; as expectativas foram publicadas
antes da primeira execução do grafo. Não houve ajuste após consultar a reserva.

## Reproduzir

Em Linux, com Python 3.12, git e uv 0.12.19 disponíveis:

```sh
git clone https://github.com/vitali87/code-graph-rag.git /tmp/radar-cgr-upstream
git -C /tmp/radar-cgr-upstream checkout --detach 14b47e1d55f8c22395158567a894dbffdeb1e3ae
uv sync --project /tmp/radar-cgr-upstream --frozen --no-dev --python 3.12
python3 experiments/code_graph/compare.py --upstream /tmp/radar-cgr-upstream
CODE_GRAPH_UPSTREAM=/tmp/radar-cgr-upstream python3 -m unittest discover -s experiments/code_graph -p 'test_*.py' -v
```

Use um diretório novo se esse caminho já existir. Clonar e instalar dependências
exige rede. O runner recusa outra revisão ou alterações rastreadas no upstream;
não baixa nem atualiza dependências durante a comparação. A CI instala pelo
`uv.lock` do commit fixado. Sem `CODE_GRAPH_UPSTREAM`, os testes do grafo ficam
explicitamente ignorados; isso não equivale a validar a integração.

## O que é executado

`worker.py` importa o **GraphUpdater real**, usa somente a gramática Python e
o coletor em memória `_CapturingIngestor` dos testes upstream. Essa API privada
é intencionalmente vinculada ao SHA auditado; mudanças exigem nova avaliação.
Não substituímos o grafo por um parser próprio. A indexação não necessita
Memgraph, Qdrant, embeddings, LLM, ferramentas MCP ou shell sobre o corpus.

O runner aceita apenas a fixture congelada desta pasta. Copia os seis arquivos
para um diretório descartável, marca os arquivos somente leitura, limpa o
ambiente do subprocesso e usa Python `-I`, timeout de 90 s, limite de CPU de
30 s e espaço de endereçamento de 2 GiB. Parsing com erro ou ausência de módulo
interrompe o teste. Cobertura de módulos **não prova** extração semântica completa.

**Não é sandbox de segurança.** O processo ainda tem permissões do usuário no
hospedeiro; arquivos somente leitura não são uma fronteira contra código hostil.
O ensaio local de bubblewrap falhou ao criar o namespace de rede. Portanto,
isolamento por sistema operacional e bloqueio de rede não foram homologados.
Não usar este runner para código privado, repositórios arbitrários ou clientes.
Não foram necessárias chamadas externas durante a extração; ausência de chamadas
neste caminho não equivale a um bloqueio técnico de rede.

Os logs loguru/stdlib do worker são silenciados; a interface de comando devolve
código genérico em caso de erro. O teste de sintaxe inválida confirma ausência
do marcador sintético no stdout/stderr. Isso não corrige os logs gerais do
upstream nem aplica o patch de privacidade de Cypher da auditoria.

## Resultados e evidências

| Método | Desenvolvimento exato | Reserva exata | Precisão/recall na reserva |
| --- | ---: | ---: | ---: |
| Literal top-3 | 0/10 | 1/10 | 0,400 / 1,000 |
| Grafo, consultas determinísticas | 10/10 | 10/10 | 1,000 / 1,000 |

`comparison.json` contém resultados por tarefa, versões e hashes de origem.
Para conferir uma citação, abra no commit do corpus o arquivo
`experiments/code_graph/corpus/<file>` na linha indicada. No grafo, a linha
refere-se à definição do chamador, símbolo ou início do módulo importador;
não é necessariamente a linha exata da chamada. Os limites dos símbolos são
validados pelo worker, mas a pontuação avalia **arquivos**, não exatidão de spans.
O índice existe apenas em memória: não é serviço de recuperação persistente.

Na revisão técnica, a cópia descartável foi alterada deliberadamente para
reproduzir uma lacuna: o runner anterior atribuía o hash da origem mesmo quando
a cópia diferia. Agora o worker calcula os hashes dos bytes lidos, verifica que
as fontes permanecem iguais ao final da indexação e o runner exige igualdade
com o manifesto congelado. Essa verificação detecta divergências da cópia;
não substitui isolamento contra um processo hostil com o mesmo usuário.
O teste de reprodução agora compara o relatório inteiro, incluindo versões,
commit, hashes e baseline, em vez de validar apenas a seção do grafo.
Corpus, rótulos e pontuações permanecem inalterados. O estudo possui 19 testes,
incluindo a regressão da PR #5: a busca precisa consultar a mesma pasta de
fontes selecionada pela avaliação. O callback recebe `root` explicitamente;
o grafo também valida manifesto e spans contra essa pasta.

Há assimetria explícita: o grafo recebe operação e símbolo qualificado; o
baseline usa apenas o nome literal. Distratores foram construídos para mostrar
esse problema, e a reserva reutiliza os mesmos módulos. Logo, o resultado
mostra capacidade estrutural nessa fixture, **não superioridade geral sobre
busca textual, desempenho do Codex ou qualidade de respostas de IA**.
Não foram medidos chamadas dinâmicas, outras linguagens, latência representativa,
concorrência, retomada, isolamento entre clientes ou custo em produção.

## Decisão e próximo gate

Manter **B — STUDY**. Primeiro revisar as duas PRs; depois comparar uma busca
textual sensível à operação e um corpus novo, mais representativo e ainda não
consultado. Homologar isolamento antes de admitir qualquer código privado.
Adapter de leitura no Hub, contrato no Evidence Kit, catálogo no Control Plane
e n8n continuam condicionados a esses resultados. Nenhum deles foi habilitado.

Créditos: [Code-Graph-RAG, Vitali Avagyan](https://github.com/vitali87/code-graph-rag/tree/14b47e1d55f8c22395158567a894dbffdeb1e3ae),
MIT; cópia do aviso em `UPSTREAM-LICENSE.txt`. Corpus, runner e avaliação são
adaptações originais Radar sob a licença indicada no README. Os termos de
dependências e serviços não são substituídos pela licença do projeto.
