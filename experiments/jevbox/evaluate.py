# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
"""Frozen synthetic evaluation, without inference, network or provider prices."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import statistics
import time
import tracemalloc

from radar_evidence import Evidence, Scope, check_evidence, resolve_citation, split_evidence
from experiments.jevbox.retrieval import search

ROOT = Path(__file__).resolve().parent
METHODS = ("flat", "hierarchical")


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def load_frozen():
    manifest = json.loads((ROOT / "data-manifest.json").read_text())
    data = {}
    for path, digest in manifest["files"].items():
        raw = (ROOT / path).read_bytes()
        if sha256(raw).hexdigest() != digest:
            raise ValueError("frozen corpus changed: " + path)
        data[Path(path).stem] = json.loads(raw)
    if set(data) != {"corpus", "development", "reserved"}:
        raise ValueError("incomplete frozen dataset")
    return manifest, data


def fixtures(corpus):
    scope = Scope("synthetic-tenant", "offline-study", {d["id"]: 1 for d in corpus["documents"]})
    passages = []
    for document in corpus["documents"]:
        source = sha256(json.dumps(document, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        for page, text in enumerate(document["pages"], 1):
            parent = Evidence(
                scope.tenant_id, scope.project_id, document["id"], 1, page,
                0, len(text), text, source, sha256(text.encode()).hexdigest(),
                "approved", "synthetic reviewer fixture", True,
            )
            passages.extend(resolve_citation(citation, parent, scope)
                            for citation in split_evidence(parent))
    return passages, scope


def summarize(rows):
    relevant = sum(len(row["relevant"]) for row in rows)
    retrieved = sum(len(row["retrieved"]) for row in rows)
    recalled = sum(len(set(row["relevant"]) & set(row["retrieved"])) for row in rows)
    correct = sum(sum(page in row["relevant"] for page in row["retrieved"]) for row in rows)
    answerable = sum(bool(row["relevant"]) for row in rows)
    unanswerable = len(rows) - answerable
    exact = sum((row["retrieved"][0] in row["relevant"] if row["retrieved"]
                 else not row["relevant"]) for row in rows)
    return {
        "cases": len(rows), "top1_accuracy": ratio(exact, len(rows)),
        "citation_precision_at_3": ratio(correct, retrieved),
        "page_recall_at_3": ratio(recalled, relevant),
        "retrieval_coverage": ratio(sum(bool(r["retrieved"]) for r in rows), len(rows)),
        "answerable_abstention_rate": ratio(sum(bool(r["relevant"]) and not r["retrieved"] for r in rows), answerable),
        "unanswerable_correct_abstention_rate": ratio(sum(not r["relevant"] and not r["retrieved"] for r in rows), unanswerable),
        "integrity_rate": ratio(sum(len(r["retrieved"]) for r in rows if r["integrity_valid"]), retrieved),
    }


def evaluate():
    manifest, data = load_frozen()
    passages, scope = fixtures(data["corpus"])
    known = {item.evidence_id: item.to_dict() for item in passages}
    report = {
        "schema_version": 1, "scope": "synthetic_offline_retrieval_only",
        "protocol": manifest["protocol"], "input_sha256": manifest["files"],
        "documents": len(data["corpus"]["documents"]), "passages": len(passages),
        "external_model_calls": 0, "model_api_cost_usd": 0,
        "financial_reconciliation": "not_applicable_no_provider_calls",
        "production_authorized": False,
        "limitations": ["page-level manual synthetic labels; not semantic entailment",
                        "lexical proxy does not execute Jevbox choose or an LLM",
                        "no real identity, customer data, concurrency or scale validation",
                        "all benchmark pages fit in one window; long-window quality not measured"],
        "splits": {},
    }
    for split in ("development", "reserved"):
        report["splits"][split] = {}
        for method in METHODS:
            rows = []
            for case in data[split]:
                hits = search(case["query"], passages, scope, method=method)
                rows.append({
                    "id": case["id"], "relevant": case["relevant"],
                    "retrieved": [f"{hit.evidence.document_id}:{hit.evidence.page}" for hit in hits],
                    "evidence_ids": [hit.evidence.evidence_id for hit in hits],
                    "integrity_valid": all(known.get(h.evidence.evidence_id) == h.evidence.to_dict()
                                           and check_evidence(h.evidence, scope).supported for h in hits),
                })
            report["splits"][split][method] = {"metrics": summarize(rows), "cases": rows}
    flat = report["splits"]["reserved"]["flat"]["metrics"]
    tree = report["splits"]["reserved"]["hierarchical"]["metrics"]
    report["reserved_non_regression"] = all(tree[key] >= flat[key] for key in (
        "top1_accuracy", "citation_precision_at_3", "page_recall_at_3",
        "unanswerable_correct_abstention_rate"))
    report["decision"] = "retain_flat_baseline; hierarchy_remains_experimental"
    return report


def benchmark(repetitions=25):
    if type(repetitions) is not int or not 1 <= repetitions <= 100:
        raise ValueError("repetitions must be 1–100")
    manifest, data = load_frozen()
    passages, scope = fixtures(data["corpus"])
    result = {"scope": "single_process_synthetic_search_only", "python": platform.python_version(),
              "platform": platform.system(), "repetitions_per_case": repetitions,
              "input_sha256": manifest["files"], "methods": {},
              "excludes": ["ingestion", "Store revalidation", "network", "LLM", "concurrency", "RSS"]}
    for method in METHODS:
        timings = []
        for case in data["reserved"]:
            search(case["query"], passages, scope, method=method)
        for _ in range(repetitions):
            for case in data["reserved"]:
                start = time.perf_counter_ns()
                search(case["query"], passages, scope, method=method)
                timings.append((time.perf_counter_ns() - start) / 1_000_000)
        tracemalloc.start()
        for case in data["reserved"]:
            search(case["query"], passages, scope, method=method)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        result["methods"][method] = {
            "samples": len(timings), "p50_ms": statistics.median(timings),
            "p95_ms": sorted(timings)[(95 * len(timings) + 99) // 100 - 1],
            "python_traced_peak_bytes": peak,
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Compare deterministic results with committed snapshot")
    parser.add_argument("--performance", type=Path, help="Write optional observed timings; no scale claims")
    args = parser.parse_args()
    result = evaluate()
    if args.check:
        if result != json.loads((ROOT / "results.json").read_text()):
            raise SystemExit("Evaluation changed; inspect before accepting a new snapshot")
        print("Frozen evaluation reproduced; hierarchy remains experimental.")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.performance:
        args.performance.write_text(json.dumps(benchmark(), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
