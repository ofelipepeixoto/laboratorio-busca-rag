import json
import os
import unittest
from pathlib import Path
from experimento_pgvector import literal, run, sql_experiment, vector, vocabulary
from busca import carregar


class VetoresTests(unittest.TestCase):
    def test_zero_norm_and_normalization(self):
        self.assertEqual(vector('desconhecido', ['prazo']), [0.0])
        self.assertEqual(vector('Como cancelar?', ['rescisao']), [1.0])
        self.assertAlmostEqual(sum(x*x for x in vector('prazo inicio', ['prazo', 'inicio'])), 1)

    def test_vocabulary_stable_and_sql_escaped(self):
        docs = carregar('documentos.json')
        self.assertEqual(vocabulary(docs), vocabulary(list(reversed(docs))))
        self.assertEqual(literal("d'água"), "'d''água'")
        self.assertIn('ORDER BY', sql_experiment(docs, carregar('perguntas.json')))
        with self.assertRaises(ValueError):
            sql_experiment([], [])

    @unittest.skipUnless(os.environ.get('PGVECTOR_TESTS') == '1', 'Requer Docker; habilitado no CI')
    def test_real_pgvector_preserves_baseline(self):
        report = run()
        self.assertEqual(report['pgvector_version'], '0.8.1')
        self.assertEqual(report['scores'], {'literal': 5, 'equivalencias': 7, 'pgvector': 7})
        self.assertIsNone(report['cases'][-1]['pgvector'])
        Path('resultado_pgvector.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
