"""Reserva sintética fixa: recuperação, citação top-1 e abstenção sem geração."""
import hashlib
import json
from pathlib import Path

from busca import buscar, carregar
from experimento_pgvector import cosine_reference


def metrics(rows):
    correct = sum(row['obtido'] is not None and row['obtido'] == row['esperado'] for row in rows)
    emitted = sum(row['obtido'] is not None for row in rows)
    answerable = sum(row['esperado'] is not None for row in rows)
    unsupported = len(rows) - answerable
    abstained = len(rows) - emitted
    abstention_correct = sum(row['obtido'] is None and row['esperado'] is None for row in rows)
    unsupported_fp = sum(row['obtido'] is not None and row['esperado'] is None for row in rows)
    return {'total': len(rows), 'correct_citations': correct, 'emitted_citations': emitted,
            'answerable': answerable, 'unsupported': unsupported, 'abstained': abstained,
            'correct_abstentions': abstention_correct,
            'precision_at_1': correct/emitted if emitted else None,
            'recall_at_1': correct/answerable if answerable else None,
            'abstention_precision': abstention_correct/abstained if abstained else None,
            'abstention_recall': abstention_correct/unsupported if unsupported else None,
            'unsupported_false_positive_rate': unsupported_fp/unsupported if unsupported else None}


def report():
    raw = (Path(__file__).parent/'dados/reserva.json').read_bytes()
    questions = json.loads(raw)
    documents = carregar('documentos.json')
    methods = {}
    for name in ('literal', 'equivalencias', 'cosine_reference'):
        rows = []
        for case in questions:
            result = (cosine_reference(case['pergunta'], documents) if name == 'cosine_reference'
                      else (buscar(case['pergunta'], expandir=name == 'equivalencias') or {}).get('id'))
            rows.append({**case, 'obtido': result})
        methods[name] = {'metrics': metrics(rows), 'cases': rows}
    return {'scope': 'synthetic_reserved_retrieval_only',
            'reserved_sha256': hashlib.sha256(raw).hexdigest(),
            'database_executed': False, 'methods': methods,
            'limits': ['Cosine reference is stdlib arithmetic, not a pgvector integration run.',
                       'No embeddings, LLM, legal correctness or generated answer support is measured.',
                       'Reserve defined before this run; no dictionary/ranking changes made from its results.']}


if __name__ == '__main__':
    print(json.dumps(report(), ensure_ascii=False, sort_keys=True, indent=2))
