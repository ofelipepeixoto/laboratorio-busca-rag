"""Experimento local descartável: pgvector exato sobre vetores lexicais, sem modelos."""
import json
import math
from pathlib import Path
import subprocess
import time
import uuid

from busca import buscar, carregar, termos

IMAGE = 'pgvector/pgvector@sha256:3e8b3adfd27b5707128f60956f62a793c3c9326ea8cfaf0eab7adccb5d700b21'


def vocabulary(documents):
    return sorted(set().union(*(termos(d['texto'], True) for d in documents)))


def vector(text, words):
    present = termos(text, True)
    values = [float(word in present) for word in words]
    norm = math.sqrt(sum(x*x for x in values))
    return [x/norm if norm else 0.0 for x in values]


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def sql_experiment(documents, questions):
    words = vocabulary(documents)
    if not words:
        raise ValueError('Corpus vazio')
    sql = ['CREATE EXTENSION IF NOT EXISTS vector;',
           f'CREATE TEMP TABLE docs (id text PRIMARY KEY, embedding vector({len(words)}));']
    for doc in documents:
        sql.append(f"INSERT INTO docs VALUES ({literal(doc['id'])}, {literal(json.dumps(vector(doc['texto'], words)))});")
    for question in questions:
        values = vector(question['pergunta'], words)
        if not any(values):
            sql.append("SELECT json_build_object('obtido', NULL);")
        else:
            q = literal(json.dumps(values))
            sql.append("SELECT json_build_object('obtido', (SELECT id FROM docs "
                       f"WHERE embedding <=> {q}::vector < 1.0 "
                       f"ORDER BY embedding <=> {q}::vector, id LIMIT 1));")
    return '\n'.join(sql)


def cosine_reference(question, documents):
    """Referência matemática local; não executa PostgreSQL nem mede embeddings."""
    words = vocabulary(documents)
    query = vector(question, words)
    if not any(query):
        return None
    candidates = [(sum(a*b for a, b in zip(query, vector(doc['texto'], words))), doc['id'])
                  for doc in documents]
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][1] if candidates and candidates[0][0] > 0 else None


def command(args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=60, **kwargs).stdout


def run(questions=None):
    documents = carregar('documentos.json')
    questions = (carregar('perguntas.json') + [{'pergunta': 'Qual é a cor do logotipo?', 'esperado': None}]
                 if questions is None else questions)
    name = 'rag-pgvector-' + uuid.uuid4().hex[:12]
    # Não aceita DSN, nome de container existente, senha externa ou endereço de produção.
    command(['docker', 'run', '--detach', '--rm', '--network', 'none', '--memory', '512m',
             '--cpus', '1', '--name', name, '--tmpfs', '/var/lib/postgresql/data',
             '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', IMAGE])
    try:
        for _ in range(60):
            try:
                command(['docker', 'exec', name, 'pg_isready', '-U', 'postgres'])
                break
            except subprocess.CalledProcessError:
                time.sleep(0.25)
        else:
            raise RuntimeError('Postgres não ficou pronto')
        output = command(['docker', 'exec', '-i', name, 'psql', '-U', 'postgres', '-XAtq',
                          '-v', 'ON_ERROR_STOP=1'], input=sql_experiment(documents, questions))
        obtained = [json.loads(line)['obtido'] for line in output.splitlines()]
        if len(obtained) != len(questions):
            raise RuntimeError('Saída SQL incompleta')
        version = command(['docker', 'exec', name, 'psql', '-U', 'postgres', '-XAtq', '-c',
                           "SELECT extversion FROM pg_extension WHERE extname='vector'"]).strip()
        rows = []
        for case, result in zip(questions, obtained):
            rows.append({**case, 'literal': (buscar(case['pergunta']) or {}).get('id'),
                         'equivalencias': (buscar(case['pergunta'], True) or {}).get('id'),
                         'pgvector': result})
        report = {'image': IMAGE, 'pgvector_version': version,
                  'representation': 'bag-of-words binário normalizado + equivalências existentes; sem embedding semântico',
                  'search': 'cosseno exato, score > 0, desempate por id; sem índice ANN',
                  'cases': rows,
                  'scores': {m: sum(row[m] == row['esperado'] for row in rows)
                             for m in ('literal', 'equivalencias', 'pgvector')}, 'total': len(rows)}
        return report
    finally:
        command(['docker', 'rm', '--force', name])


if __name__ == '__main__':
    report = run()
    Path('resultado_pgvector.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
