# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
"""Three real repositories composed in CI; no backend or identity mocks."""

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from radar_evidence import Scope
from experiments.jevbox.retrieval import search

REQUIRED = os.environ.get("RADAR_REQUIRE_DOCUMENTAL") == "1"
DOCUMENTAL = os.environ.get("RADAR_DOCUMENTAL_PATH")
if REQUIRED and not DOCUMENTAL:
    raise RuntimeError("CI must supply the pinned documental checkout")
if DOCUMENTAL:
    root = Path(DOCUMENTAL).resolve(strict=True)
    if not (root / "ingestion" / "passages.py").is_file():
        raise RuntimeError("documental passage adapter missing")
    sys.path.insert(0, str(root))
    from avaliacao.pdf_fixtures import make_pdf
    from ingestion.contracts import LabError
    from ingestion.passages import export_passage_snapshot, validate_passage_snapshot
    from ingestion.store import Store

@unittest.skipUnless(DOCUMENTAL, "optional locally; mandatory in Jevbox integration CI")
class DocumentalIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.store = Store(self.workspace.name)
        self.doc = self.store.ingest(make_pdf([
            "Pagamento mensal fictício; contexto revisado. " * 20,
            "Pagamento secreto de página pendente; não deve ser recuperado.",
        ]), "ficticio.pdf")
        self.doc = self.store.review(self.doc["id"], 1, self.doc["revision"], "Operador local", "approved")
        self.config = {"tenant_id": "local", "project_id": "integration"}
        self.payload = export_passage_snapshot(
            self.store, **self.config, expected_revisions={self.doc["id"]: self.doc["revision"]},
        )

    def consume(self):
        return validate_passage_snapshot(self.store, self.payload, **self.config, document_ids=[self.doc["id"]])

    def test_pdf_to_passages_to_search_keeps_original_review_and_hashes(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            passages = self.consume()
            scope = Scope(**self.config, current_revisions={self.doc["id"]: self.doc["revision"]})
            self.assertGreater(len(passages), 1)
            for method in ("flat", "hierarchical"):
                self.assertEqual(search("pagamento mensal", passages, scope, method=method), [])
                hits = search("pagamento mensal", passages, scope, method=method, require_verified_review=False)
                self.assertTrue(hits)
                self.assertTrue(all(h.evidence.page == 1 and not h.evidence.identity_verified for h in hits))
                self.assertTrue(all(h.evidence.source_sha256 == self.doc["source_sha256"] for h in hits))
                self.assertEqual(search("pagamento secreto", passages, scope, require_verified_review=False), [])

    def test_revision_revocation_blocks_old_snapshot_and_cached_hits(self):
        passages = self.consume()
        self.doc = self.store.review(self.doc["id"], 1, self.doc["revision"], "Operador local", "rejected")
        with self.assertRaises(LabError):
            self.consume()
        current = Scope(**self.config, current_revisions={self.doc["id"]: self.doc["revision"]})
        self.assertEqual(search("pagamento mensal", passages, current, require_verified_review=False), [])

    def test_self_consistent_file_cannot_choose_its_trusted_project(self):
        with self.assertRaises(LabError):
            validate_passage_snapshot(self.store, self.payload, tenant_id="local", project_id="different",
                                      document_ids=[self.doc["id"]])


if __name__ == "__main__":
    unittest.main()
