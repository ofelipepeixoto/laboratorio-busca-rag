# MinerU — experimento isolado (B — STUDY)

Implementação autoral de Carlos Felipe / Help Mídias, com assistência de IA.
Objetivo: verificar extração por página antes de conectar outro parser ao
`assistente-documental-ia`. Código deste experimento sob
[MIT dos controles Radar](../../licenses/RADAR-CONTROLS-MIT.txt); MinerU,
DocVortex, modelos e patches derivados conservam seus próprios termos.

**Resultado local de 07/10/2026: continuar STUDY; integração não aprovada.**
O experimento concluiu as dez execuções. O gate de qualidade falhou porque
MinerU Flash representou uma linha da tabela como imagem e não extraiu seu texto.
Não alteramos o corpus, o limiar ou a expectativa para esconder essa perda.

| Conjunto fictício | Páginas | pypdf: campos críticos | MinerU Flash: campos críticos |
|---|---:|---:|---:|
| Contrato (desenvolvimento) | 2 | 4/4 | 4/4 |
| Tabela (desenvolvimento) | 1 | 3/3 | 2/3 |
| Cláusulas (reserva) | 2 | 5/5 | 5/5 |
| Instrução como dado (reserva) | 1 | 1/1 | 1/1 |
| PDF digitalizado, sem texto | 1 | 0/1, precisa OCR/revisão | 0/1, precisa OCR/revisão |

Total nos digitais: **13/13 versus 12/13**. A linha perdida é
`Revisão | 1 | R$ 250,00`. O PDF de tabela é texto disposto em linhas com
separadores, não um benchmark de relações de células de tabelas complexas.
Não há qualidade de RAG, retrieval, OCR ou raciocínio jurídico medida aqui.
O caso de instrução maliciosa apenas confirma extração como texto em um fluxo
sem agente/LLM; não comprova resistência de um agente a prompt injection.

## Executar

Linux x86_64, Python **3.12**, `libseccomp.so.2`, git e um ambiente virtual dedicado.
Os baselines já existentes no repositório continuam sem dependências externas.
O MinerU é opcional, instalado apenas para este experimento.

```sh
python3 -m unittest experiments.mineru.test_study -v
python3.12 -m venv .venv-mineru
bash experiments/mineru/prepare.sh /tmp/radar-mineru-source .venv-mineru/bin/python
python3 -m experiments.mineru.patch_checks \
  --python .venv-mineru/bin/python --upstream /tmp/radar-mineru-source \
  --output experiments/mineru/output/patch-checks.txt
.venv-mineru/bin/python -m unittest experiments.mineru.test_worker -v
python3 -m experiments.mineru.study --python .venv-mineru/bin/python \
  --output experiments/mineru/output/comparison.json
```

O destino de `prepare.sh` deve ser novo. A preparação baixa código e dependências;
não baixa pesos, não configura chaves e não executa o servidor MinerU. A execução
do parsing e dos testes selecionados ocorre em processos restritos, sem rede.
Use `--engine pypdf` para comparar apenas o baseline. Não há opção para enviar
URLs, documentos pessoais, modelos pagos, tier OCR ou credenciais.

`execution_complete` indica que todos os parsers solicitados terminaram e
retornaram resultados estruturalmente válidos. O código de saída da CLI verifica
essa conclusão. **`quality_gate_passed` é separado:** exige todos os campos
críticos digitais na página correta e sinalização de ausência de texto no scan.
O workflow pode estar verde com qualidade reprovada, pois registrar resultado
negativo é uma execução válida do estudo. `integration_approved` permanece
sempre `false`; nenhum destes campos concede aprovação humana.

## Contrato e controles

- `manifest.json` fixa cinco PDFs fictícios, expectativas e hashes antes das
  medições. Os dois casos de reserva não ajustam o parser. A reserva é pequena,
  sintética e visível no código; não é avaliação cega nem amostra independente real.
- A CLI aceita somente essas fixtures. Confere hash, caminho sem traversal,
  ausência de symlink e limite de 10 MiB antes de executar o worker.
- Cada execução copia um único PDF para diretório temporário, limpa variáveis de
  segredos/proxy, usa HOME temporário e descarta logs do parser.
- Antes dos imports de terceiros, o worker aplica limites de 20 s de CPU,
  2 GiB de memória virtual **por processo**, 2 MiB por arquivo de saída, 64
  descritores e zero core dumps. O processo pai impõe 30 s de relógio e encerra
  o grupo de processos também no sucesso. Não há quota agregada de memória/PIDs.
- Seccomp nega sockets de rede, `connect` inclusive Unix e `io_uring`; pares
  Unix anônimos para asyncio permanecem disponíveis. Subprocessos do renderizador
  herdam os filtros. Sem Linux/libseccomp, falha fechada.
- PDF criptografado, mais de 50 páginas, saída parcial/desordenada ou página
  acima de 16 KiB de texto são rejeitados. Uma imagem nunca conta como texto:
  o renderer de imagem produz string vazia, sem exportar base64/assets.
- Origem, página, hash do texto e revisão `pending` são validados. A normalização
  faz NFC, espaços e, apenas para MinerU, remove o escape Markdown de cifrão.
  Não elimina números ou negações. É teste de presença por página, não avaliação
  completa de fidelidade ou contradições.
- O relatório armazena hashes, métricas, versões e tempos; não inclui texto
  extraído, caminhos de usuário ou prompts. Temporários são removidos ao sair
  normalmente; queda abrupta do host pode exigir limpeza dos diretórios
  `radar-mineru-*` em `/tmp`.

**Limite essencial:** estes controles não isolam o filesystem, não eliminam
vulnerabilidades de bibliotecas nativas e não autorizam documentos hostis/reais.
Para esse piloto posterior é necessário worker/container sem privilégios,
filesystem mínimo, quotas agregadas e política de egress validada. Seccomp não
substitui identidade, autorização, backups, jobs persistidos ou revisão humana.
Não há API, preview HTML, upload remoto, Doclib ou integração n8n nesta camada.

## Snapshot, patches e licenças

MinerU **4.0.10**, commit
[`ed50cc15bc2c9bfb00520dadfe61979866e62236`](https://github.com/opendatalab/MinerU/tree/ed50cc15bc2c9bfb00520dadfe61979866e62236).
`prepare.sh` aplica três patches da auditoria, em ordem: consentimento explícito
de telemetria, upload limitado por stream e rejeição de chave vazia/com espaços.
Eles não corrigem todas as lacunas nem tornam a API pronta para produção.
Essas rotas não são usadas no experimento Flash.

`source-pin.sha256` é **gerado**: hashes dos 316 arquivos Python do candidato.
O worker exige correspondência exata e versões selecionadas de MinerU, DocVortex,
pypdf e PDFium. `constraints.txt` é o inventário fixado da auditoria, não um lock
com hashes de wheels nem garantia da proveniência de binários transitivos.
No ambiente dedicado desta etapa foram instaladas 112 distribuições.

Os checksums usam formato `SHA256  caminho`. Na publicação inicial, um mapa JSON
`caminho: hash` gerou seis falsos positivos do scanner de segredos para nomes com
`api`. Todos foram conferidos contra os bytes locais. O formato foi corrigido
sem exceções no scanner, alteração de sua política ou remoção de controles.

O MinerU usa licença personalizada baseada em Apache-2.0, com condições
adicionais comerciais e de atribuição; leia
[licença original](licenses/MinerU-LICENSE.md) e
[avisos](THIRD_PARTY_NOTICES.md). Não relicenciar os patches como MIT.
Nenhum peso foi baixado; a due diligence de pesos/OCR, `mineru-llama-cpp` e
componentes vendorizados apontada na auditoria permanece pendente para adoção.

## Evidência desta implementação

- **22 testes** de contratos/isolamento aprovados, incluindo sockets via libc,
  herança por subprocesso, timeout, saída excessiva, fonte adulterada, páginas,
  hashes, valores não finitos e limpeza de variáveis sensíveis.
- **186 testes selecionados do candidato** aprovados: 25 regressões da auditoria
  + 161 existentes. Um teste de telemetria upstream é alterado deliberadamente
  pelo patch para exigir consentimento afirmativo.
- **Seis testes de entradas inválidas** com parser real: PDF criptografado,
  corrompido, acima de 50 páginas/10 MiB, conteúdo não PDF e engine não permitida.
- **10 testes existentes do laboratório aprovados; dois pgvector ignorados
  localmente** por falta de Docker. Os workflows existentes continuam responsáveis
  pela execução real do banco.
- Dez execuções reais do parser em sete páginas sintéticas. Em cada caso um novo
  worker: pypdf cerca de 0,36–0,42 s e MinerU cerca de 3,02–3,93 s nesta máquina.
  Os tempos incluem inicialização e conferência de fontes; não medem p95,
  capacidade, custo de produção ou RSS isolado.

Resultados em [comparison-2026-10-07.json](results/comparison-2026-10-07.json)
e [patch-checks-2026-10-07.txt](results/patch-checks-2026-10-07.txt). Os diagnósticos
anteriores de lint/tipos e o bloqueio da suíte ampla constam da auditoria, não foram
resolvidos nem reclassificados por estes testes selecionados. A suíte ampla não
é executada pelo workflow, que faz checkout da própria PR e fixa separadamente
o commit upstream correto.

## Revisão, reversão e próximo gate

Ordem de leitura: este README → `manifest.json`/`corpus.py` → `study.py` →
`worker.py`/`isolation.py` → testes → workflow → patches/avisos. Fixtures PDF,
manifest, hashes de fonte, constraints e resultados são arquivos gerados.
Para regenerar o corpus, use `python -m experiments.mineru.corpus` no ambiente
fixado e revise qualquer diff antes de mudar o manifesto. O scan usa PDFium 5.14.0.

Esta PR é independente das PRs Jevbox e Code-Graph-RAG. Não depende de código
ainda não integrado. Uma única PR mantém junto contrato, corpus, executor,
testes e medição do mesmo experimento; não adiciona produto ou refatoração geral.
Reversão: reverter a PR remove o experimento e seu workflow; não há migração,
alteração de produção ou consumidor dependente.

**Próximo gate ainda não atendido:** corpus autorizado de scans/tabelas reais,
licenças/proveniência dos componentes selecionados, OCR em isolamento completo,
ganho de qualidade útil contra os parsers existentes e revisão humana dos erros.
Somente depois abrir adaptação no assistente, mantendo original/página/hash e
aprovação do Evidence Kit. Não há motivo demonstrado para substituir pypdf agora.

Referências técnicas: [seccomp/libseccomp](https://www.man7.org/linux/man-pages/man3/seccomp_rule_add.3.html),
[limites de recursos Linux](https://www.man7.org/linux/man-pages/man2/setrlimit.2.html).
