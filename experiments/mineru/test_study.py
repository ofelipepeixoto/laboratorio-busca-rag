"""Contratos e isolamento reais; dependências de parsing são opcionais."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from experiments.mineru import study
from experiments.mineru.isolation import MAX_OUTPUT, MAX_PAGE_TEXT


def result(text="Prazo: 30 dias."):
    return {"schema": 1, "engine": "pypdf", "source_sha256": "a" * 64,
            "review_state": "pending", "parse_seconds": 0.1,
            "pages": [{"number": 1, "text": text, "text_sha256": study.digest(text.encode())}]}


class Contracts(unittest.TestCase):
    def validate(self, candidate):
        return study.validate_result(candidate, "pypdf", "a" * 64, 1)

    def test_valid_pending_result(self):
        self.assertEqual(self.validate(result())["review_state"], "pending")

    def test_identity_and_review_are_bound(self):
        for key, value in [("engine", "other"), ("source_sha256", "b" * 64),
                           ("review_state", "approved")]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate({**result(), key: value})

    def test_invalid_durations(self):
        for seconds in [float("inf"), float("nan"), -1, True, "1"]:
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                self.validate({**result(), "parse_seconds": seconds})

    def test_missing_duplicate_reordered_pages(self):
        for pages in [[], result()["pages"] * 2,
                      [{**result()["pages"][0], "number": 2}],
                      [{**result()["pages"][0], "number": True}]]:
            with self.subTest(pages=pages), self.assertRaises(ValueError):
                self.validate({**result(), "pages": pages})

    def test_modified_text_rejected(self):
        candidate = result()
        candidate["pages"][0]["text"] = "Prazo: 130 dias."
        with self.assertRaisesRegex(ValueError, "text_hash"):
            self.validate(candidate)

    def test_utf8_byte_limit(self):
        with self.assertRaisesRegex(ValueError, "invalid_page_text"):
            self.validate(result("á" * (MAX_PAGE_TEXT // 2 + 1)))

    def test_currency_escape_only(self):
        self.assertEqual(study.normalize(r"R\$ 75,50 NÃO", "mineru-flash"), "R$ 75,50 NÃO")
        self.assertEqual(study.normalize(r"R\$ 75,50", "pypdf"), r"R\$ 75,50")

    def test_incorrect_number_does_not_match_suffix(self):
        case = {"critical": [[1, "30 dias"]]}
        self.assertEqual(study.metrics(case, result("130 dias"))["critical_found"], 0)

    def test_phrase_on_wrong_page_does_not_pass(self):
        candidate = result("")
        candidate["pages"].append({"number": 2, "text": "30 dias"})
        self.assertEqual(study.metrics({"critical": [[1, "30 dias"]]}, candidate)["critical_found"], 0)

    def test_empty_scan_is_not_successful_extraction(self):
        score = study.metrics({"critical": [[1, "R$ 890,00"]]}, result(""))
        self.assertEqual(score["critical_recall"], 0)
        self.assertTrue(score["needs_review_or_ocr"])

    def test_frozen_fixture_hashes(self):
        manifest = json.loads((study.ROOT / "manifest.json").read_text())
        self.assertEqual(len(manifest["cases"]), 5)
        self.assertEqual(sum(len(c["pages"]) for c in manifest["cases"]), 7)
        for case in manifest["cases"]:
            data = (study.ROOT / "fixtures" / case["file"]).read_bytes()
            self.assertEqual(study.digest(data), case["sha256"])

    def test_urls_traversal_and_unknown_engine_rejected(self):
        for path in ["https://example.invalid/a.pdf", "../a.pdf", "/a.pdf"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                study.run_case({"file": path}, "pypdf", sys.executable)
        with self.assertRaises(ValueError):
            study.run_case({}, "llm", sys.executable)

    def test_tampered_fixture_rejected_before_worker(self):
        case = json.loads((study.ROOT / "manifest.json").read_text())["cases"][0]
        with patch.object(study, "bounded_process") as worker:
            with self.assertRaisesRegex(ValueError, "fixture_changed"):
                study.run_case({**case, "sha256": "0" * 64}, "pypdf", sys.executable)
            worker.assert_not_called()

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "fixtures").mkdir()
            (root / "fixtures" / "x.pdf").symlink_to(study.ROOT / "fixtures" / "contrato.pdf")
            with patch.object(study, "ROOT", root), self.assertRaisesRegex(ValueError, "invalid_fixture"):
                study.run_case({"file": "x.pdf"}, "pypdf", sys.executable)

    def test_no_secret_or_proxy_in_child_environment(self):
        with patch.dict(os.environ, {"API_KEY": "fixture-secret", "HTTP_PROXY": "fixture", "PYTHONPATH": "fixture"}):
            environment = study.child_environment(Path("/tmp/example"))
        for key in ["API_KEY", "HTTP_PROXY", "PYTHONPATH"]:
            self.assertNotIn(key, environment)

    def test_failure_never_promotes_integration(self):
        with patch.object(study, "run_case", side_effect=ValueError("fixture")):
            report = study.evaluate(sys.executable)
        self.assertFalse(report["execution_complete"])
        self.assertFalse(report["quality_gate_passed"])
        self.assertFalse(report["integration_approved"])
        self.assertEqual(len(report["failures"]), 10)


class Isolation(unittest.TestCase):
    def invoke(self, code, timeout=5):
        prefix = f"import sys; sys.path.insert(0, {str(study.ROOT)!r}); from isolation import restrict_worker; restrict_worker(); "
        with tempfile.TemporaryDirectory() as temp:
            return study.bounded_process([sys.executable, "-E", "-s", "-B", "-c", prefix + code], Path(temp), timeout)

    def test_kernel_blocks_native_ipv4_ipv6_and_unix_connect(self):
        code = '''
import ctypes, errno, socket
lib = ctypes.CDLL(None, use_errno=True)
for family in (socket.AF_INET, socket.AF_INET6):
    assert lib.socket(family, socket.SOCK_STREAM, 0) == -1
    assert ctypes.get_errno() == errno.EPERM
a,b = socket.socketpair()
try:
    try: a.connect('/tmp/nonexistent-radar.sock')
    except PermissionError: pass
    else: raise AssertionError('Unix connect allowed')
finally: a.close(); b.close()
print('blocked')
'''
        self.assertEqual(self.invoke(code).strip(), b"blocked")

    def test_subprocess_inherits_network_restriction(self):
        code = "import subprocess; p=subprocess.run([sys.executable,'-c','import socket; socket.socket(socket.AF_INET)'],stderr=subprocess.DEVNULL); assert p.returncode != 0; print('inherited')"
        self.assertEqual(self.invoke(code).strip(), b"inherited")

    def test_wall_timeout(self):
        with self.assertRaisesRegex(ValueError, "worker_timeout"):
            self.invoke("import time; time.sleep(5)", timeout=0.2)

    def test_large_output_fails_closed(self):
        with self.assertRaises(ValueError):
            self.invoke(f"sys.stdout.write('a' * {MAX_OUTPUT + 1})")

    def test_memory_limit_is_applied(self):
        code = "import resource; from isolation import MEMORY_BYTES; assert resource.getrlimit(resource.RLIMIT_AS) == (MEMORY_BYTES,MEMORY_BYTES); print('limited')"
        self.assertEqual(self.invoke(code).strip(), b"limited")

    def test_missing_seccomp_cannot_continue(self):
        code = f"import sys;sys.path.insert(0,{str(study.ROOT)!r});from unittest.mock import patch;from isolation import restrict_worker;\nwith patch('ctypes.CDLL',side_effect=OSError('missing')): restrict_worker()"
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(ValueError):
            study.bounded_process([sys.executable, "-c", code], Path(temp))


if __name__ == "__main__":
    unittest.main()
