"""Somente regressões selecionadas; nunca descobre a suíte ampla upstream."""
import argparse
from pathlib import Path

from experiments.mineru.study import ROOT, bounded_process


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import tempfile
    # Rodar por código estático instala seccomp ANTES de importar pytest/terceiros.
    code = """
import sys
sys.path.insert(0, sys.argv[1])
from isolation import restrict_worker
restrict_worker()
from worker import verify_mineru_sources
verify_mineru_sources()
import pytest
raise SystemExit(pytest.main(['-q', '-o', 'addopts=', '-p', 'no:cacheprovider', *sys.argv[2:]]))
"""
    tests = [ROOT / "upstream_tests/test_candidate_controls.py",
             args.upstream.absolute() / "tests/unittest/test_parser_api_contract.py",
             args.upstream.absolute() / "tests/unittest/test_doclib_telemetry_core.py"]
    with tempfile.TemporaryDirectory(prefix="radar-mineru-checks-") as temp:
        raw = bounded_process([str(Path(args.python).absolute()), "-E", "-s", "-B",
                               "-c", code, str(ROOT), *map(str, tests)], Path(temp))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(raw)
    print(raw.decode())


if __name__ == "__main__":
    main()
