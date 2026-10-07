"""Behavior/risk checks for the original Radar experiment (MIT)."""
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from .study import (
    SOURCE_PATH,
    Evidence,
    compare,
    digest,
    expand_bounded,
    load_transform,
    present,
    read_cases,
)


def evidence(text):
    return Evidence("synthetic", text, digest(text), ())


class Contracts(unittest.TestCase):
    def test_frozen_corpus_and_unicode_citations(self):
        cases = read_cases()
        self.assertEqual(len(cases), 6)
        self.assertEqual(sum(len(c.anchors) for c in cases), 13)
        unicode_case = cases[-1]
        start, end, text = unicode_case.anchors[0]
        self.assertEqual(unicode_case.quote(start, end, unicode_case.original_digest), text)

    def test_changed_original_is_rejected(self):
        case = read_cases()[0]
        with self.assertRaises(ValueError):
            replace(case, original=case.original.replace("NÃO", "SIM")).validate()

    def test_changed_anchor_is_rejected(self):
        case = read_cases()[0]
        with self.assertRaises(ValueError):
            replace(case, anchors=((0, 4, "invented"),)).validate()

    def test_wrong_hash_cannot_resolve_quote(self):
        case = read_cases()[0]
        with self.assertRaises(ValueError):
            case.quote(0, 1, "unverified")

    def test_invalid_offsets_cannot_resolve_quote(self):
        case = read_cases()[0]
        for start, end in [(-1, 1), (0, 99999), (1, 1), (True, 3), (0, 1.5)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                case.quote(start, end, case.original_digest)

    def test_bounded_inverse_preserves_trailing_newline(self):
        text = "x\n... (repeated 100 times)\n"
        self.assertEqual(expand_bounded(text, 200), "x\n" * 100)

    def test_bounded_inverse_preserves_no_trailing_newline(self):
        self.assertEqual(expand_bounded("x\n... (repeated 3 times)", 5), "x\nx\nx")

    def test_empty_lines_are_bounded(self):
        self.assertEqual(expand_bounded("\n... (repeated 20 times)\n", 20), "\n" * 20)
        with self.assertRaises(ValueError):
            expand_bounded("\n... (repeated 20 times)\n", 19)

    def test_huge_marker_is_rejected_before_expansion(self):
        with self.assertRaises(ValueError):
            expand_bounded("x\n... (repeated 1000000000 times)\n", 100)

    def test_zero_count_and_invalid_budgets_rejected(self):
        with self.assertRaises(ValueError):
            expand_bounded("x\n... (repeated 0 times)\n", 100)
        for budget in [-1, True]:
            with self.assertRaises(ValueError):
                expand_bounded("x", budget)

    def test_marker_passthrough_never_calls_transform(self):
        def forbidden(_):
            self.fail("Literal marker must bypass transform")
        for marker in ["... (repeated 1000000000 times)", "... (repeats 100 lines from 1 lines back)"]:
            original = "x\n" + marker + "\n"
            self.assertEqual(present(evidence(original), SimpleNamespace(collapse_runs=forbidden)),
                             (original, "literal_marker_bypass"))

    def test_input_budget_checked_before_transform(self):
        def forbidden(_):
            self.fail("Over-budget input must bypass transform")
        raw = "é" * 40000
        self.assertEqual(present(evidence(raw), SimpleNamespace(collapse_runs=forbidden)),
                         (raw, "input_budget_bypass"))

    def test_non_reversible_candidate_is_bypassed(self):
        self.assertEqual(present(evidence("não autorizado"), SimpleNamespace(collapse_runs=lambda _: "autorizado")),
                         ("não autorizado", "roundtrip_bypass"))

    def test_amplifying_candidate_is_bypassed(self):
        self.assertEqual(present(evidence("small"), SimpleNamespace(collapse_runs=lambda _: "x\n... (repeated 1000000000 times)\n")),
                         ("small", "expansion_budget_bypass"))

    def test_no_gain_preserves_original(self):
        self.assertEqual(present(evidence("x"), SimpleNamespace(collapse_runs=lambda x: x)),
                         ("x", "no_gain_bypass"))

    def test_baseline_does_not_claim_execution_or_savings(self):
        result = compare(read_cases(), None)
        self.assertEqual(result["byte_reduction_fraction"], 0)
        self.assertFalse(result["headroom_transform_executed"])
        self.assertTrue(result["integrity_gate_passed"])
        self.assertFalse(result["integration_approved"])
        self.assertIsNone(result["answer_quality_gate_passed"])
        self.assertFalse(result["tokens_measured"])

    def test_changed_upstream_refused_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / SOURCE_PATH
            path.parent.mkdir(parents=True)
            path.write_text('raise RuntimeError("must never execute")')
            with self.assertRaises(ValueError):
                load_transform(root)

    def test_duplicate_source_ids_refused(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "corpus.json"
            row = {"id": "same", "original": "x", "sha256": digest("x"), "anchors": []}
            path.write_text(json.dumps([row, row]))
            with self.assertRaises(ValueError):
                read_cases(path)


@unittest.skipUnless(os.environ.get("HEADROOM_STUDY_SOURCE"), "Explicit audited checkout required")
class ActualUpstream(unittest.TestCase):
    def test_actual_transform_and_citation_integrity(self):
        module = load_transform(Path(os.environ["HEADROOM_STUDY_SOURCE"]))
        cases = read_cases()
        before = tuple(c.original for c in cases)
        result = compare(cases, module)
        self.assertTrue(result["headroom_transform_executed"])
        self.assertTrue(result["integrity_gate_passed"])
        self.assertEqual(sum(r["status"] == "compressed" for r in result["cases"]), 3)
        self.assertLess(result["presented_bytes"], result["original_bytes"])
        self.assertEqual(tuple(c.original for c in cases), before)

    def test_only_audited_stdlib_module_loaded(self):
        import sys
        before = set(sys.modules)
        load_transform(Path(os.environ["HEADROOM_STUDY_SOURCE"]))
        self.assertFalse(any(name == "headroom" or name.startswith("headroom.")
                             for name in set(sys.modules) - before))


if __name__ == "__main__":
    unittest.main()
