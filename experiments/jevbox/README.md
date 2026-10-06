# Extração seletiva Jevbox — piloto local

Decisão executada: **C — EXTRACT**, com adoção condicionada à avaliação.
Nenhuma plataforma completa, ícone Nucleo, provedor pago ou asset de UI foi
incorporado. Os baselines anteriores do laboratório permanecem disponíveis.

## O que foi entregue

| Componente | Destino | Origem e limite |
|---|---|---|
| Referências a trechos com página integral, hashes e revisão | [radar-evidence-kit PR 6](https://github.com/ofelipepeixoto/radar-evidence-kit/pull/6) | Código original, contrato aditivo 0.2 |
| Export limitado e revalidação no Store atual | [assistente-documental-ia PR 6](https://github.com/ofelipepeixoto/assistente-documental-ia/pull/6) | Código original; identidade local continua não verificada |
| Pontuação geométrica de rotas | `route_score.py` | Adaptação MIT de `extendRoute` do Jevbox; validação estrita adicionada |
| Comparação plana versus documento → trechos | `retrieval.py`, `evaluate.py` | Código original, roteador lexical; não reproduz o LLM do Jevbox |
| Limite JSON, atualização source-map-js e documentação | `patches/` | Patches sobre o upstream fixado, verificados em checkout descartável |
| Regressões, PDF/SQLite reais e avaliação congelada | `tests/`, `probes/`, GitHub Actions | Sem chamadas pagas e sem dados de clientes |

O SHA upstream é `aaa9381bcdca4dc7c383ab6778cb8aece72b9e3e`.
`source-manifest.json` registra origem, hashes dos patches/testes/licença e
commits dos consumidores. Preserve `third_party/JEVBOX-LICENSE.txt`:
Copyright 2026 CrowdView Inc, dba Extend. A fórmula adaptada não é apresentada
como criação original. O restante do experimento original usa `LICENSE`,
Copyright 2026 Carlos Felipe; isso não relicencia arquivos anteriores do repo.

## Resultado e decisão

Protocolo e arquivos foram congelados em `data-manifest.json` antes da primeira
execução: 6 documentos, 12 páginas fictícias, 4 perguntas de desenvolvimento
e 12 reservadas. Nenhum ajuste foi feito usando os resultados reservados.
Os dois métodos usam as equivalências já existentes em `busca.termos` e exigem
todos os termos na passagem final. Top-k=3; hierarquia seleciona 2 documentos.

| Métrica no conjunto reservado | Plano | Hierárquico |
|---|---:|---:|
| Página relevante recuperada (recall@3) | 9/9 — 100% | 7/9 — 77,8% |
| Precisão das citações por rótulo de página | 9/13 — 69,2% | 7/11 — 63,6% |
| Top-1 correto ou abstenção correta | 10/12 | 10/12 |
| Abstenção correta nos casos sem resposta | 3/3 | 3/3 |
| Integridade dos registros retornados | 100% | 100% |

**Manter a busca plana; não promover a hierarquia.** Índices temáticos
funcionaram como distrações: a poda retirou duas páginas relevantes. Hashes
corretos não garantem relevância ou suporte semântico. O roteador lexical é
um controle barato para estudar esse risco; esses resultados não medem a
qualidade do `jev.choose` original. Sua média geométrica usa escores heurísticos,
não probabilidades calibradas. Com cobertura completa exigida, as passagens
aceitas têm empate de escore; o principal efeito medido é a poda documental.

`results.json` registra casos, hashes e métricas reproduzíveis. A aprovação
do CI significa que o experimento e os controles funcionam, não que a
hipótese hierárquica venceu. `reserved_non_regression=false` e
`production_authorized=false` são resultados explícitos.

`performance-observed.json` contém 300 buscas por método em um processo local,
com p50/p95 e pico de alocações Python. Exclui ingestão, consulta ao Store,
rede, inferência, RSS e concorrência. Não permite extrapolar para 1.000 ou
10.000 usuários. Todas as páginas desse corpus cabem em uma janela; qualidade
de chunking longo, OCR e documentos reais ainda não foi avaliada.

## Executar o experimento

Na raiz do laboratório, Python 3.11 ou 3.12:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install --no-deps -r experiments/jevbox/requirements.txt
python -m experiments.jevbox.verify_sources
python -m unittest discover -s experiments/jevbox/tests -v
python -m experiments.jevbox.evaluate --check
python -m experiments.jevbox.evaluate --performance /tmp/jevbox-performance.json
```

A instalação precisa de rede; a avaliação não. Não requer chave de API.
Os três testes de integração documental são opcionais nesse comando local;
para executá-los, prepare o consumidor fixado:

```sh
git clone https://github.com/ofelipepeixoto/assistente-documental-ia.git /tmp/documental-jevbox
git -C /tmp/documental-jevbox checkout --detach df532b43801f51fc132debf92fa7e1a140bc1342
python -m pip install --require-hashes -r /tmp/documental-jevbox/requirements-pdf.txt
RADAR_REQUIRE_DOCUMENTAL=1 RADAR_DOCUMENTAL_PATH=/tmp/documental-jevbox \
  python -m unittest discover -s experiments/jevbox/tests -v
```

O CI exige esses testes, com PDF/SQLite reais e dois runtimes Python. Confirma
exclusão de página pendente, integridade, identidade não promovida, escopo
confiável e rejeição de snapshot após mudança de revisão. Os testes de busca
também verificam isolamento antes de pontuar e instruções maliciosas como dados.

## Verificar os patches upstream

Em ambiente descartável, com Node 24, pnpm 12.9.1 e Docker, clone Jevbox no
SHA acima. O workflow `jevbox-extract.yml` documenta o procedimento exato:
verifica manifesto, aplica os três patches, instala lockfile sem hooks,
prepara PostgreSQL/SpiceDB/Mailpit locais, instala Chromium, executa as oito
regressões originais, suíte completa upstream, tipos/build e audit com gate
para avisos altos/críticos. Encerra somente os serviços do runner descartável.
Não usa segredos nem aponta banco ou storage para produção.

O patch JSON limita bytes decodificados antes do parse (64 MiB por padrão),
inclusive streaming sem Content-Length, e cancela o leitor. Não limita todos
os SDKs de rede; validar teto com respostas legítimas do parser antes de adotar.
O patch de dependência fixa `source-map-js` em 1.2.2; avisos futuros podem fazer
o gate falhar. Não rodar `audit fix --force` nem retirar esse gate para passar.

Os patches ficam isolados no laboratório. Não alteram o projeto de terceiros
nem introduzem seu servidor nos projetos Radar. Uma integração futura exige
escolher o componente, carregar sua licença e executar os mesmos controles.

## Operação, integração e reversão

Integrar na ordem: kit → documental → laboratório. Dependências são SHAs
imutáveis, não branches. Nenhum schema persistido do Store ou journal mudou.
Reversão: retirar consumidores primeiro (laboratório, documental) e depois o
contrato aditivo, por PR de revert; não apagar documentos, banco ou evidências.
O export anterior continua utilizável durante a revisão destas PRs.

Não há endpoint novo, MCP novo nem workflow n8n ativado. n8n poderá disparar
preparação, revisão e acompanhamento quando houver backend autenticado;
tenant, ACL, revisão, parsing e reserva financeira continuam no backend.
Nenhum JSON de agente ou workflow pode autorizar execução ou promover identidade.
O control plane atual não foi alterado nem teve seus pins/bloqueios contornados.

Antes de um piloto com modelos: definir identidade e permissões reais,
corpus autorizado, limite financeiro explícito, preço verificado, reserva
atômica e reconciliação, worker isolado, storage privado, métricas mínimas e
procedimento de recuperação. Não existe orçamento aprovado nesta entrega.
Chamadas de modelo e custo de API do experimento são zero; isso não mede
custo total de infraestrutura. RAG real e integração operacional ficam
condicionados a esses gates e a uma avaliação que justifique a mudança.
