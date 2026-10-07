"""Negativas reais do parser pypdf no ambiente opcional fixado."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from experiments.mineru.corpus import pdf_bytes
from experiments.mineru.study import ROOT, child_environment


class Worker(unittest.TestCase):
    def invoke(self, data, engine="pypdf"):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "fixture.pdf"
            path.write_bytes(data)
            result = subprocess.run([sys.executable, "-E", "-s", "-B", str(ROOT / "worker.py"), engine, str(path)],
                                    cwd=root, env=child_environment(root), capture_output=True,
                                    timeout=30, check=False)
            self.assertNotEqual(result.returncode, 0)
            return json.loads(result.stdout)["error"]

    def test_non_pdf_rejected(self):
        self.assertEqual(self.invoke(b"<html>fixture</html>"), "pdf_required")

    def test_page_limit(self):
        self.assertEqual(self.invoke(pdf_bytes([["fixture"]] * 51)), "page_limit")

    def test_encrypted_pdf_rejected(self):
        from pypdf import PdfWriter
        import io
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        writer.encrypt("fixture-password")
        buffer = io.BytesIO()
        writer.write(buffer)
        self.assertEqual(self.invoke(buffer.getvalue()), "encrypted_pdf")

    def test_malformed_pdf_fails_closed(self):
        self.assertEqual(self.invoke(b"%PDF-1.4\nbroken"), "worker_failed")

    def test_unknown_engine_rejected(self):
        self.assertEqual(self.invoke(pdf_bytes([["fixture"]]), "remote-api"), "engine_not_allowed")

    def test_too_large_input_rejected(self):
        from experiments.mineru.isolation import MAX_INPUT
        self.assertEqual(self.invoke(b"%PDF-" + b" " * MAX_INPUT), "invalid_input")


if __name__ == "__main__":
    unittest.main()
