# Laboratório de busca documental

Comparação reproduzível entre busca por palavras literais e busca com um pequeno dicionário manual de equivalências, usando somente documentos fictícios. O objetivo é mostrar como medir recuperação antes de escolher uma arquitetura mais complexa.

## Executar

Requer Python 3, sem dependências externas:

```bash
python busca.py
python -m unittest -v test_busca.py
```

Os casos de teste estão em `dados/perguntas.json`; o corpus está em `dados/documentos.json`. O workflow executa a comparação a cada alteração.

## Resultado inicial

| Método | Acertos nos 6 casos |
| --- | ---: |
| Palavras literais | 4/6 |
| Equivalências manuais | 6/6 |

As perguntas «Quando começa?» e «Como cancelar?» são recuperadas após mapear *começa → início* e *cancelar → rescisão*. Esse ganho é específico do conjunto pequeno e não prova desempenho em documentos reais.

## Limites e próximos experimentos

Os dois métodos são **lexicais**. Este repositório ainda não implementa embeddings, busca vetorial, reranking ou geração por LLM; portanto, não demonstra um pipeline RAG completo. Para evoluir, ampliar os casos fictícios, separar treino e avaliação e comparar métodos sob o mesmo conjunto sem ajustar o dicionário após ver os resultados de teste.
