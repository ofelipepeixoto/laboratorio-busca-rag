"""Regressão de protocolo de inicialização; simulação local, não integração DB."""
import subprocess
import unittest
from unittest.mock import patch

import experimento_pgvector as experiment


class ReadinessTests(unittest.TestCase):
    def test_temporary_unix_server_is_not_treated_as_final_readiness(self):
        state = {'tcp_probes': 0, 'final_ready': False, 'cleanup': False}

        def fake_command(args, **kwargs):
            if args[1] == 'run':
                return 'synthetic-container\n'
            if args[1] == 'rm':
                state['cleanup'] = True
                return 'synthetic-container\n'
            if 'pg_isready' in args:
                # Durante initdb, Unix já aceita enquanto TCP ainda não está pronto.
                if '-h' not in args:
                    return 'temporary Unix server accepting connections\n'
                state['tcp_probes'] += 1
                if state['tcp_probes'] < 3:
                    raise subprocess.CalledProcessError(2, args)
                state['final_ready'] = True
                return 'final TCP server accepting connections\n'
            if 'psql' in args:
                if not state['final_ready']:
                    raise subprocess.CalledProcessError(2, args, stderr='temporary server restarted')
                return '0.8.1\n' if '-c' in args else '{"obtido":"prazo"}\n'
            raise AssertionError('Comando inesperado no protocolo simulado')

        with patch.object(experiment, 'command', side_effect=fake_command), \
             patch.object(experiment.time, 'sleep'):
            result = experiment.run(questions=[{'pergunta': 'Qual é o prazo?', 'esperado': 'prazo'}])
        self.assertEqual(result['scores']['pgvector'], 1)
        self.assertTrue(state['final_ready'])
        self.assertTrue(state['cleanup'])


if __name__ == '__main__':
    unittest.main()
