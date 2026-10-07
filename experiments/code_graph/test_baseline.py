import json
import shutil
import tempfile
import unittest
from pathlib import Path

from evaluate import ROOT, digest, evaluate, grade, lexical, verify_fixture


class BaselineTests(unittest.TestCase):
    def test_tasks_have_independent_labels_and_both_splits(self):
        tasks = json.loads((ROOT / "tasks.json").read_text())
        self.assertEqual(len({t["id"] for t in tasks}), 20)
        self.assertEqual(sum(t["split"] == "reserved" for t in tasks), 10)
        for task in tasks:
            for name in task["expected"]:
                self.assertTrue((ROOT / "corpus" / name).is_file())

    def test_wrong_citation_counts_both_false_positive_and_miss(self):
        self.assertEqual(grade(["a.py"], [{"file": "b.py"}]),
                         {"tp": 0, "fp": 1, "fn": 1, "exact": False})

    def test_abstention_is_not_automatically_correct(self):
        self.assertTrue(grade([], [])["exact"])
        self.assertFalse(grade(["a.py"], [])["exact"])

    def test_comments_are_real_baseline_false_positives(self):
        self.assertEqual(lexical({"term": "ghost"})[0]["file"], "legacy.py")

    def test_committed_results_reproduce(self):
        self.assertEqual(evaluate(lexical), json.loads((ROOT / "baseline.json").read_text()))

    def test_alternate_fixture_is_also_the_retrieval_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "corpus").mkdir()
            (root / "corpus" / "alternate.py").write_text("alternate_only = 1\n")
            task = {"id": "probe", "split": "development", "term": "alternate_only",
                    "expected": ["alternate.py"]}
            (root / "tasks.json").write_text(json.dumps([task]))
            manifest = {name: digest((root / name).read_bytes())
                        for name in ("tasks.json", "corpus/alternate.py")}
            (root / "manifest.json").write_text(json.dumps(manifest))
            result = evaluate(lexical, root=root)
            self.assertEqual(result["rows"][0]["hits"], [{"file": "alternate.py", "lines": [1]}])
            self.assertTrue(result["rows"][0]["exact"])

    def test_fixture_tampering_additions_and_symlinks_are_rejected(self):
        for mode in ("modify", "add", "symlink"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "fixture"
                shutil.copytree(ROOT, root)
                path = root / "corpus" / "billing.py"
                if mode == "modify":
                    path.write_text("changed")
                elif mode == "add":
                    (path.parent / "extra.py").write_text("pass")
                else:
                    path.unlink()
                    path.symlink_to(ROOT / "corpus" / "billing.py")
                with self.assertRaises(ValueError):
                    verify_fixture(root)
