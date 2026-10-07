# Laboratório de busca documental

Estudo independente proposto: [Headroom offline](experiments/headroom/README.md).
Compara originais e compactação em fixtures sintéticas; qualidade de respostas,
economia real e adoção continuam pendentes.

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

Os dois métodos em `busca.py` são **lexicais**. O experimento opcional abaixo
armazena esses vetores lexicais no pgvector, sem embeddings semânticos, reranking
ou geração por LLM; portanto, não demonstra um pipeline RAG completo.

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

## Reserva independente e gate de integração

A proposta pgvector (`b49661f`) foi composta ao main lexical (`d5ccac6`).
`dados/reserva.json` contém oito perguntas novas, com categorias e expectativas
definidas antes da execução. Seu SHA-256 é
`c8d877589c52238779cf2cdcdb3a217d88a688a90e8f8efa963971fce81ce1df`.
Não foram ajustados corpus, equivalências, ranking ou limiar com esses resultados.

```sh
python3 -m unittest discover -v
python3 avaliar_reserva.py
```

Nesta execução offline, literal, equivalências e referência matemática cosseno
obtiveram precision@1 **0,8**, recall@1 **0,8** e abstenção correta em **2/3**
casos sem suporte. A pergunta sobre multa continua falso positivo: uma cláusula
de aviso de rescisão não fornece valor de multa. Métricas avaliam citações top-1;
citação errada conta falso positivo e perda do documento esperado. Denominador
zero aparece como `null`, sem produzir uma nota perfeita.

`cosine_reference` calcula vetores lexicais em Python: **não é execução pgvector**.
O relatório `resultado_reserva.json` marca `database_executed: false`.
Nesta execução local, dez testes passaram e dois testes PostgreSQL foram
ignorados porque Docker não estava disponível. O resultado pgvector 7/7 acima
é o registro do experimento anterior incorporado pela PR, não uma nova medição.
A CI `pgvector.yml` habilita ambos os testes reais, incluindo paridade da reserva
com a referência matemática. Antes de usar um banco existente, verificar esse
job no commit composto; nenhuma conexão Supabase/Postgres de produção foi feita.

Pgvector permanece a primeira candidata para armazenamento vetorial se a demanda
justificar. Estes oito casos não medem embeddings semânticos, desempenho, escala,
segurança do banco ou qualidade jurídica. A evolução continua experimental.

## Controle de segredos

Gitleaks fixado, fixtures e scan do histórico completo disponível estão
documentados em [docs/segredos-ci.md](docs/segredos-ci.md). O job privilegiado
usa apenas script/política da base confiável e lê a PR como dados; seu bootstrap
não equivale a check obrigatório já homologado.

A inicialização agora espera TCP em `127.0.0.1` e usa o mesmo host no psql.
O servidor temporário de initdb pode aceitar socket Unix antes do restart final;
essa condição foi observada na primeira CI composta. A regressão de protocolo
reproduz a falha anterior sob simulação e conserva o teste real como gate.
