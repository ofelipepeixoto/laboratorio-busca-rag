"""Lifecycle failures via subprocess mocks; never starts a Docker daemon/container."""
import json
import subprocess
import unittest
from unittest.mock import patch

import experimento_pgvector as experiment


class CleanupTests(unittest.TestCase):
    def simulate(self, failure_at=None, cleanup_failure=None, collision=False, absent=False):
        self.calls = []
        self.container_id = 'a' * 64
        self.name = None
        self.owner = None
        self.failure = subprocess.TimeoutExpired(['docker', failure_at or 'run'], 60)

        def fake_subprocess(args, **kwargs):
            self.calls.append(args)
            self.assertEqual(kwargs['timeout'], 60)
            self.assertTrue(kwargs['check'])
            if args[1] == 'run':
                self.name = args[args.index('--name') + 1]
                if '--label' in args:
                    label = args[args.index('--label') + 1]
                    self.owner = label.split('=', 1)[1]
                if failure_at == 'run':
                    raise self.failure
                stdout = self.container_id
            elif args[1] == 'inspect':
                self.assertEqual(args[-1], self.name)
                if cleanup_failure:
                    raise cleanup_failure
                if absent:
                    raise subprocess.CalledProcessError(1, args, stderr=f'Error: No such object: {self.name}')
                stdout = json.dumps({'Id':self.container_id, 'Config':{'Labels':{
                    'radar.pgvector.execution': 'unrelated' if collision else self.owner}}})
            elif args[1] == 'rm':
                self.assertEqual(args, ['docker', 'rm', '--force', self.container_id])
                stdout = self.container_id
            elif args[1] == 'exec':
                if failure_at == 'readiness' and 'pg_isready' in args:
                    raise subprocess.CalledProcessError(1, args)
                if failure_at == 'query' and '-i' in args:
                    raise self.failure
                stdout = '0.8.1' if '-c' in args else '{"obtido":"prazo"}\n'
            else:
                raise AssertionError('Unexpected lifecycle command')
            return subprocess.CompletedProcess(args, 0, stdout, '')

        return patch.object(experiment.subprocess, 'run', side_effect=fake_subprocess)

    def assert_removed_once(self):
        self.assertEqual([c for c in self.calls if c[1] == 'rm'],
                         [['docker', 'rm', '--force', self.container_id]])

    def test_startup_timeout_still_removes_owned_container(self):
        with self.simulate('run'), self.assertRaises(subprocess.TimeoutExpired) as caught:
            experiment.run()
        self.assertIs(caught.exception, self.failure)
        self.assert_removed_once()

    def test_readiness_failure_removes_owned_container(self):
        with self.simulate('readiness'), patch.object(experiment.time, 'sleep'), \
                self.assertRaisesRegex(RuntimeError, 'Postgres não ficou pronto'):
            experiment.run()
        self.assert_removed_once()

    def test_query_timeout_removes_owned_container(self):
        with self.simulate('query'), self.assertRaises(subprocess.TimeoutExpired):
            experiment.run()
        self.assert_removed_once()

    def test_success_cleans_up_without_changing_result(self):
        with self.simulate():
            report = experiment.run(questions=[{'pergunta':'Qual é o prazo?', 'esperado':'prazo'}])
        self.assertEqual(report['scores']['pgvector'], 1)
        self.assert_removed_once()

    def test_name_collision_does_not_remove_unrelated_container(self):
        with self.simulate('run', collision=True), self.assertRaises(subprocess.TimeoutExpired):
            experiment.run()
        self.assertFalse(any(c[1] == 'rm' for c in self.calls))

    def test_absent_container_cleanup_can_be_repeated(self):
        with self.simulate('run', absent=True):
            with self.assertRaises(subprocess.TimeoutExpired):
                experiment.run()
            experiment.cleanup_container(self.name, self.owner)
            experiment.cleanup_container(self.name, self.owner)
        self.assertFalse(any(c[1] == 'rm' for c in self.calls))

    def test_cleanup_failure_keeps_original_startup_error(self):
        for error in (FileNotFoundError('docker'), subprocess.TimeoutExpired(['docker', 'inspect'], 60),
                      subprocess.CalledProcessError(1, ['docker', 'inspect'], stderr='daemon unavailable')):
            with self.subTest(error=type(error).__name__), self.simulate('run', cleanup_failure=error), \
                    self.assertRaises(subprocess.TimeoutExpired) as caught:
                experiment.run()
            self.assertIs(caught.exception, self.failure)
            self.assertIn('não confirmada', caught.exception.__notes__[0])

    def test_cleanup_failure_after_success_is_reported(self):
        with self.simulate(cleanup_failure=FileNotFoundError('docker')), self.assertRaises(FileNotFoundError):
            experiment.run(questions=[{'pergunta':'Qual é o prazo?', 'esperado':'prazo'}])

    def test_container_removed_between_inspect_and_remove_is_harmless(self):
        item = {'Id':'b' * 64, 'Config':{'Labels':{'radar.pgvector.execution':'owned'}}}
        missing = subprocess.CalledProcessError(1, ['docker', 'rm'], stderr=f"No such container: {item['Id']}")
        with patch.object(experiment, 'command', side_effect=[json.dumps(item), missing]):
            experiment.cleanup_container('synthetic-name', 'owned')

    def test_unlabelled_container_is_not_removed(self):
        item = {'Id':'b' * 64, 'Config':{'Labels':None}}
        with patch.object(experiment, 'command', return_value=json.dumps(item)) as command:
            experiment.cleanup_container('synthetic-name', 'owned')
        self.assertEqual(command.call_count, 1)

    def test_missing_docker_preserves_original_error(self):
        error = FileNotFoundError('docker')
        with patch.object(experiment.subprocess, 'run', side_effect=error) as command, \
                self.assertRaises(FileNotFoundError) as caught:
            experiment.run()
        self.assertIs(caught.exception, error)
        self.assertEqual([call.args[0][1] for call in command.call_args_list], ['run', 'inspect'])


if __name__ == '__main__':
    unittest.main()
