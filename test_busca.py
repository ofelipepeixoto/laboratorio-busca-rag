import unittest

from busca import avaliar, buscar


class TestComparacao(unittest.TestCase):
    def test_equivalencias_recuperam_formulacoes_alternativas(self):
        self.assertIsNone(buscar("Quando começa?"))
        self.assertEqual(buscar("Quando começa?", expandir=True)["id"], "prazo")
        self.assertIsNone(buscar("Como cancelar?"))
        self.assertEqual(buscar("Como cancelar?", expandir=True)["id"], "rescisao")

    def test_baseline_e_melhoria_mensuraveis(self):
        resultados = avaliar()
        self.assertEqual(sum(r["acertou"] for r in resultados["literal"]), 4)
        self.assertEqual(sum(r["acertou"] for r in resultados["equivalencias"]), 6)

    def test_pergunta_sem_suporte_nao_retorna_documento(self):
        self.assertIsNone(buscar("Qual é a cor do logotipo?", expandir=True))


if __name__ == "__main__":
    unittest.main()
