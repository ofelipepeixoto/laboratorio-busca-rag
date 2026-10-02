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

## Experimento pgvector opcional

`busca.py` e suas expectativas continuam intactos (literal 4/6, equivalências 6/6).
O novo experimento usa os mesmos seis casos e acrescenta uma pergunta sem suporte:
literal **5/7**, equivalências **7/7**, pgvector **7/7** nesta fixture.
Os vetores são bag-of-words binários normalizados, com as equivalências existentes;
não são embeddings semânticos e o resultado não demonstra superioridade do pgvector.
A busca usa cosseno exato, score positivo e desempate por id, sem HNSW/IVFFlat.

Com Docker disponível:

```sh
docker pull pgvector/pgvector@sha256:3e8b3adfd27b5707128f60956f62a793c3c9326ea8cfaf0eab7adccb5d700b21
PGVECTOR_TESTS=1 python3 -m unittest discover -v
python3 experimento_pgvector.py
```

A imagem está fixada por digest (pgvector 0.8.1 / PostgreSQL 17). Cada execução cria
um contêiner com nome aleatório, sem rede ou portas, dados em tmpfs e remoção em
`finally`; nenhum DSN externo é aceito. Não usa Supabase, produção, credenciais ou
chave paga. `POSTGRES_HOST_AUTH_METHOD=trust` só vale nesse banco descartável sem rede.
Download da imagem exige rede antes do experimento. Interrupção abrupta do processo
pode exigir remover o contêiner `rag-pgvector-*` que ele criou.

`resultado_pgvector.json` registra versão, representação, casos e pontuações.
Testes cobrem vetor zero, normalização, vocabulário determinístico, escape SQL,
paridade do baseline e execução real no PostgreSQL. A fixture pequena não mede
latência representativa, escala, ANN ou relevância em documentos reais.

Adaptação e experimento originais deste projeto, feitos com assistência de IA.
[pgvector](https://github.com/pgvector/pgvector/tree/v0.8.1) é dos contribuidores
upstream, licença PostgreSQL; PostgreSQL tem sua própria licença. Nenhum código
upstream foi copiado ou reivindicado como autoria do projeto.
