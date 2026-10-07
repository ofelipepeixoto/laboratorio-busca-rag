import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from compare import UPSTREAM_SHA, build_index, compare, graph_search, validate_index
from evaluate import ROOT


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("CODE_GRAPH_UPSTREAM"):
            raise unittest.SkipTest("Set CODE_GRAPH_UPSTREAM to run the real pinned indexer")
        cls.upstream = Path(os.environ["CODE_GRAPH_UPSTREAM"]).resolve()
        cls.index = build_index(cls.upstream)

    def test_actual_upstream_matches_complete_committed_report(self):
        actual = compare(self.upstream)
        self.assertEqual(actual, json.loads((ROOT / "comparison.json").read_text()))

    def test_changed_snapshot_cannot_claim_original_source_hash(self):
        copytree = shutil.copytree
        def corrupt_copy(source, destination):
            result = copytree(source, destination)
            path = Path(destination) / "billing.py"
            path.write_text(path.read_text().replace("def total(items):", "def changed_total(items):"))
            return result
        with patch("compare.shutil.copytree", side_effect=corrupt_copy):
            with self.assertRaisesRegex(ValueError, "SOURCE_HASH_MISMATCH"):
                build_index(self.upstream)

    def test_same_name_is_not_same_symbol(self):
        task = {"operation": "callers", "symbol": "legacy.total"}
        self.assertEqual(graph_search(self.index, task), [{"file": "legacy.py", "lines": [11]}])

    def test_no_silent_unsupported_operation(self):
        with self.assertRaisesRegex(ValueError, "OPERATION_NOT_ALLOWED"):
            graph_search(self.index, {"operation": "shell", "symbol": "billing"})

    def test_stale_revision_or_manifest_refused(self):
        for key, value in (("upstream_sha", "changed"), ("manifest", {})):
            index = copy.deepcopy(self.index)
            index[key] = value
            with self.assertRaisesRegex(ValueError, "STALE_INDEX"):
                validate_index(index)

    def test_outside_file_and_invalid_span_refused(self):
        for replacement in ({"file": "../private.py"}, {"start": 0}, {"end": 999}):
            index = copy.deepcopy(self.index)
            index["nodes"]["radar_fixture.billing.total"].update(replacement)
            with self.assertRaises(ValueError):
                validate_index(index)

    def test_missing_module_refused(self):
        index = copy.deepcopy(self.index)
        index["nodes"].pop("radar_fixture.billing")
        with self.assertRaisesRegex(ValueError, "COVERAGE_INCOMPLETE"):
            validate_index(index)

    def test_failed_worker_cannot_produce_success(self):
        result = subprocess.CompletedProcess([], 1, "", "private-error-marker")
        with patch("compare.subprocess.check_output", side_effect=[UPSTREAM_SHA, ""]), \
                patch("compare.subprocess.run", return_value=result):
            with self.assertRaisesRegex(ValueError, "^INDEX_BUILD_FAILED$"):
                build_index(self.upstream)

    def test_dirty_upstream_refused(self):
        with patch("compare.subprocess.check_output", side_effect=[UPSTREAM_SHA, " M file.py"]):
            with self.assertRaisesRegex(ValueError, "UPSTREAM_REVISION_MISMATCH"):
                build_index(self.upstream)

    def test_wrong_upstream_revision_refused(self):
        with patch("compare.subprocess.check_output", return_value="not-the-pin"):
            with self.assertRaisesRegex(ValueError, "UPSTREAM_REVISION_MISMATCH"):
                build_index(self.upstream)

    def test_parse_failure_is_sanitized(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "invalid.py").write_text("def PRIVATE_MARKER(\n")
            result = subprocess.run(
                [str(self.upstream / ".venv/bin/python"), "-I", str(ROOT / "worker.py"),
                 str(self.upstream), str(root)],
                cwd=temp, env={"HOME": temp, "PATH": "/usr/bin:/bin"},
                capture_output=True, text=True, timeout=90)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr.strip(), "CODE_GRAPH_WORKER_FAILED")

    def test_sources_remain_frozen_and_execution_sentinel_was_not_run(self):
        self.assertEqual(self.index["upstream_sha"], UPSTREAM_SHA)
        self.assertIn("radar_fixture.entry.run", self.index["nodes"])
        # Successful parse of entry.py (unconditional raise) cannot be import execution.
        validate_index(self.index)
