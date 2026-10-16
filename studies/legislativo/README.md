# Estudo legislativo — contrato e recuperação lexical

Código original MIT de Carlos Felipe, inspirado nos padrões de proveniência/famílias/splits estudados em [LLM Legislativo](https://github.com/BaruqueRodrigues/llm-legislativo/tree/6951114da14782ae1433a19f2c4bd1d2442f0ccb). Não incorpora código upstream, corpus oficial ou pesos.

```sh
python3 -m unittest -v test_legislativo.py
python3 -m studies.legislativo.run --output /CAMINHO/NOVO/fixture-package.json
```

São **34 documentos sintéticos, 17 famílias e 54 casos**. Todos os documentos usam URLs `.invalid`, datas e estados fictícios; não têm validade jurídica. Escopo de consulta (Casa, tipo, split e data) é passado explicitamente pelo caso, não extraído de linguagem natural. A pesquisa só é lexical. Resultado 54/54 na fixture demonstra o contrato desses casos; não demonstra qualidade em legislação real ou texto gerado.

O validador rejeita família/texto idêntico entre splits, IDs repetidos, hashes alterados, versões sobrepostas, origem/intervalos inválidos e gabarito fora do escopo. Até 500 documentos/200 casos; texto 16 KiB por documento; entrada JSON 1 MiB, sem chaves duplicadas, NaN ou symlink final. Leitura não é sandbox contra troca concorrente de caminhos ou componente pai malicioso.

Saída `radar-legislative-package/v1`: corpus, casos e replay por IDs/hash. Cada citação tem texto completo delimitado por offsets Unicode, versão, Casa, tipo, origem declarada e hash; **review_status=pending**. O texto pode ser recuperado no corpus pelo ID; a citação não publica nem aprova nada. O `source_study` é uma referência conceitual, não prova de autoria ou origem dos dados fictícios. Hash canônico do pacote: `1d9034bdd2d6448c35733664099cb0e25709fb89e282db809e1c0ebe3171e347`.

O módulo é opcional: busca.py, reservas existentes e pgvector não mudam. O consumidor no `avaliacao-rag-juridico` usa esse JSON por hash; não instala este repositório como dependência nem reexecuta o ranking. Os projetos permanecem independentes, relacionados por versão/hash.

Para documentos reais, preparar adaptador de seleção e revisão de licença/fonte/qualidade. Campos de intervalo representam metadados revisados do recorte; não inferem automaticamente vigência legal. Não baixar o corpus completo nem iniciar treino com este comando.

No Assistente Documental, uma integração futura deve registrar essas ocorrências pelo fluxo de ingestão existente e exigir revisão vinculada ao hash da fonte e texto. Este replay mantém a revisão pendente; não altera PDFs, banco, API ou UI daquele projeto. Não é evidência automaticamente aprovada pelo Evidence Kit: identidade/revisão da aplicação continuam necessárias.

Validação local da base + mudança: 32 testes, sendo 30 aprovados e dois ignorados (integração Docker/pgvector); nove testes novos. Sem rede, LLM, embedding, n8n ou banco real nesta funcionalidade. A CI existente executa unittest discover e inclui esses testes.

Rollback: remover studies/legislativo e o teste; nenhum estado de serviço ou schema de banco foi alterado. Aprovação/merge humano permanecem pendentes.
