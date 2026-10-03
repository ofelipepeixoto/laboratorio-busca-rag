import os
import unittest

from avaliar_reserva import metrics, report
from busca import carregar
from experimento_pgvector import cosine_reference, run


class ReservedTests(unittest.TestCase):
    def test_empty_results_do_not_report_perfect_scores(self):
        result = metrics([])
        self.assertIsNone(result['precision_at_1'])
        self.assertIsNone(result['abstention_recall'])

    def test_wrong_citation_is_both_false_positive_and_missing_expected_document(self):
        result = metrics([{'esperado': 'a', 'obtido': 'b'}])
        self.assertEqual(result['precision_at_1'], 0)
        self.assertEqual(result['recall_at_1'], 0)

    def test_insufficient_clause_remains_false_positive(self):
        result = report()
        self.assertFalse(result['database_executed'])
        for method in result['methods'].values():
            case = next(c for c in method['cases'] if c['categoria'] == 'trecho_insuficiente')
            self.assertIsNone(case['esperado'])
            self.assertEqual(case['obtido'], 'rescisao')
            self.assertGreater(method['metrics']['unsupported_false_positive_rate'], 0)

    def test_zero_query_and_tie_are_deterministic(self):
        docs = [{'id': 'z', 'texto': 'prazo'}, {'id': 'a', 'texto': 'prazo'}]
        self.assertIsNone(cosine_reference('xyz', docs))
        self.assertEqual(cosine_reference('prazo', docs), 'a')

    @unittest.skipUnless(os.environ.get('PGVECTOR_TESTS') == '1', 'Integração real requer Docker isolado')
    def test_real_pgvector_matches_reserved_arithmetic_reference(self):
        questions = carregar('reserva.json')
        result = run(questions=questions)
        docs = carregar('documentos.json')
        self.assertEqual([r['pgvector'] for r in result['cases']],
                         [cosine_reference(c['pergunta'], docs) for c in questions])


if __name__ == '__main__':
    unittest.main()
