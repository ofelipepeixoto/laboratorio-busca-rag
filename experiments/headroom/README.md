# Headroom: estudo de compactação offline

**B — STUDY. Integração não aprovada.** Este módulo compara a apresentação
original com a compactação de linhas repetidas do Headroom, usando seis textos
fictícios PT-BR congelados antes da execução. Não executa geração por modelo,
tokenização, proxy, MCP, memória, recuperações CCR ou provedores.

## Resultado reproduzido

| Métrica | Observação nas fixtures |
| --- | ---: |
| Bytes UTF-8 antes/depois | 1.468 / 643 |
| Redução de bytes | 56,2% |
| Casos comprimidos | 3/6 |
| Round-trip exato e hash original | 6/6 |
| Trechos críticos originais | 13/13 |
| Tokens, custo e qualidade de respostas | Não avaliados |

A redução descreve payloads de texto sintético com repetições intencionais;
não mede economia de tokens, custo total, prompts completos ou efeito do cache.
Reconstrução exata em software **não prova** que um modelo interpretará a forma
compactada corretamente. Os 13 trechos são verificados no original, não tratados
como qualidade de citação produzida por IA.

`result.json` é gerado. Seu gate de integridade é separado de
`answer_quality_gate_passed: null` e `integration_approved: false`.

## Reprodução

Baseline e contratos sem dependências externas:

```sh
python3 -m experiments.headroom.study
python3 -m unittest experiments.headroom.test_study -v
```

Sem checkout explícito, dois testes de transformação real são ignorados; o
baseline não se apresenta como execução do Headroom. Preparação opcional com
rede, sem instalação de pacotes nem build Rust:

```sh
git clone https://github.com/headroomlabs-ai/headroom.git /tmp/headroom-study
git -C /tmp/headroom-study checkout 87e05b68b8aa578f1439abfc8006b38cd09db14d
HEADROOM_STUDY_SOURCE=/tmp/headroom-study python3 -m unittest experiments.headroom.test_study -v
python3 -m experiments.headroom.study --headroom-source /tmp/headroom-study --output /tmp/result-headroom.json
cmp experiments/headroom/result.json /tmp/result-headroom.json
```

Somente `headroom/transforms/lossless_compaction.py`, verificado pelo SHA-256
embutido no loader, é executado. Esse arquivo auditado importa apenas `os` e `re`.
O pacote Headroom e sua telemetria não são importados. Conteúdo alterado é
recusado antes de execução. Isso não constitui sandbox de Python arbitrário.
O checkout de preparação requer rede; a comparação não usa rede.

## Fronteiras e correção da amplificação

O experimento chama apenas `collapse_runs`, e usa um inversor original com
orçamento derivado do comprimento do original. Não chama `expand_runs` nem
`compact_lossless` do upstream: a auditoria reproduziu expansão sem limite
nesses caminhos. Contagens são verificadas antes de multiplicar a lista.
Marcadores literais, incluindo back-references de blocos, provocam bypass antes
da transformação. Entrada máxima: 64 KiB UTF-8; corpus máximo: 256 KiB e 32 casos.
Esses limites não são quota de memória total do processo.

Os originais e seus spans permanecem imutáveis. Índices são caracteres Unicode
Python, não offsets de bytes. Hash protege integridade, não autentica usuário,
tenant ou autoria. A função `quote` não é endpoint de recuperação multi-tenant.
Nenhum consumidor existente chama esse módulo.

## Autoria e revisão

Harness, inversor limitado, fixtures e testes são originais de Carlos Felipe /
Help Mídias, com assistência de IA, sob `licenses/RADAR-CONTROLS-MIT.txt`.
Headroom é dos contribuidores upstream; não há reivindicação de autoria da
biblioteca. Licença Apache-2.0 e NOTICE do snapshot estão em `upstream-notices/`.
O checkout externo é uma dependência de estudo, não cópia do framework nesta PR.

Leia nesta ordem: README → corpus → study → testes → resultado → workflow.
O CI reproduz a transformação real e compara o resultado congelado. CI verde
aprova execução/controles, não qualidade de respostas ou adoção.

## Próximo gate e reversão

Antes de ampliar: completar build Rust e os testes upstream bloqueados na
auditoria; comparar com seleção/deduplicação simples; avaliar respostas e
citações em português; medir tokens e custo líquido com budget explícito.
Somente depois considerar contrato com `avaliacao-rag-juridico`, Evidence Kit e
control plane. A avaliação aqui não demonstra RAG completo ou correção jurídica.

Reverter esta PR remove o experimento e seu workflow, sem banco, migração,
novo repositório, alteração de configuração operacional ou consumidor.
