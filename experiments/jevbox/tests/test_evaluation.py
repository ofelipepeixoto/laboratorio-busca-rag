# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
import unittest
from unittest.mock import patch

from experiments.jevbox.evaluate import evaluate, load_frozen, ratio, summarize


class EvaluationTests(unittest.TestCase):
    def test_empty_denominators_remain_undefined(self):
        self.assertIsNone(ratio(0, 0))
        result = summarize([])
        self.assertEqual(result["cases"], 0)
        self.assertTrue(all(v is None for k, v in result.items() if k != "cases"))

    def test_citation_precision_and_recall_are_not_conflated_with_integrity(self):
        rows = [{"relevant": ["right:1"], "retrieved": ["right:1", "wrong:1"], "integrity_valid": True},
                {"relevant": [], "retrieved": [], "integrity_valid": True}]
        result = summarize(rows)
        self.assertEqual(result["citation_precision_at_3"], 0.5)
        self.assertEqual(result["page_recall_at_3"], 1)
        self.assertEqual(result["integrity_rate"], 1)
        self.assertEqual(result["unanswerable_correct_abstention_rate"], 1)

    def test_splits_are_disjoint_and_frozen_inputs_have_complete_labels(self):
        _, data = load_frozen()
        self.assertFalse({c["id"] for c in data["development"]} & {c["id"] for c in data["reserved"]})
        self.assertFalse({c["query"] for c in data["development"]} & {c["query"] for c in data["reserved"]})
        valid = {f"{d['id']}:{i}" for d in data["corpus"]["documents"] for i in range(1, len(d["pages"]) + 1)}
        for case in data["development"] + data["reserved"]:
            self.assertTrue(set(case["relevant"]) <= valid)

    def test_report_reproducible_offline_and_does_not_authorize_production(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            first, second = evaluate(), evaluate()
        self.assertEqual(first, second)
        self.assertEqual(first["external_model_calls"], 0)
        self.assertFalse(first["production_authorized"])
        self.assertFalse(first["reserved_non_regression"])


if __name__ == "__main__":
    unittest.main()
