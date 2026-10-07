"""Fixture-only comparison. No persistent index, arbitrary corpus or service API."""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from evaluate import ROOT, evaluate, lexical, verify_fixture

UPSTREAM_SHA = "14b47e1d55f8c22395158567a894dbffdeb1e3ae"
CORPUS_COMMIT = "543107a28342fba6e02242d66a702c8c0f605113"


def build_index(upstream):
    manifest = verify_fixture()
    upstream = Path(upstream).resolve()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(upstream), *args],
                                       text=True, stderr=subprocess.DEVNULL).strip()
    if git("rev-parse", "HEAD") != UPSTREAM_SHA or git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("UPSTREAM_REVISION_MISMATCH")
    # A fresh fixture-only subprocess, scrubbed environment and bounded resources.
    # This is NOT OS isolation: never offer this runner arbitrary/private code.
    with tempfile.TemporaryDirectory(prefix="radar-code-graph-") as temp:
        root = Path(temp)
        corpus = root / "corpus"
        shutil.copytree(ROOT / "corpus", corpus)
        for path in corpus.iterdir():
            path.chmod(0o444)
        result = subprocess.run(
            [str(upstream / ".venv/bin/python"), "-I", str(ROOT / "worker.py"),
             str(upstream), str(corpus)],
            cwd=root, env={"HOME": temp, "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            capture_output=True, text=True, timeout=90, check=False)
        if result.returncode or len(result.stdout) > 2 * 1024**2:
            raise ValueError("INDEX_BUILD_FAILED")
        index = json.loads(result.stdout)
        expected_hashes = {name.removeprefix("corpus/"): value
                           for name, value in manifest.items() if name.startswith("corpus/")}
        if index.get("source_hashes") != expected_hashes:
            raise ValueError("SOURCE_HASH_MISMATCH")
    index.update(upstream_sha=UPSTREAM_SHA, manifest=manifest)
    validate_index(index)
    return index


def validate_index(index, root=ROOT):
    if index["upstream_sha"] != UPSTREAM_SHA or index["manifest"] != verify_fixture(root):
        raise ValueError("STALE_INDEX")
    files = {name.removeprefix("corpus/") for name in index["manifest"] if name.startswith("corpus/")}
    if {n["file"] for n in index["nodes"].values() if n["kind"] == "Module"} != files:
        raise ValueError("COVERAGE_INCOMPLETE")
    for node in index["nodes"].values():
        if node["file"] not in files:
            raise ValueError("OUT_OF_SCOPE_EVIDENCE")
        lines = (root / "corpus" / node["file"]).read_text().splitlines()
        if not (1 <= node["start"] <= node["end"] <= len(lines)):
            raise ValueError("INVALID_EVIDENCE_SPAN")


def graph_search(index, task, root=ROOT):
    validate_index(index, root)
    target = "radar_fixture." + task["symbol"]
    nodes = index["nodes"]
    if task["operation"] == "definition":
        selected = [target] if target in nodes else []
    elif task["operation"] in {"callers", "importers"}:
        relation = "CALLS" if task["operation"] == "callers" else "IMPORTS"
        selected = [src for src, rel, dst in index["edges"] if rel == relation and
                    (dst == target or (relation == "IMPORTS" and dst.startswith(target + ".")))]
    else:
        raise ValueError("OPERATION_NOT_ALLOWED")
    by_file = {}
    for key in sorted(set(selected)):
        if key not in nodes:
            continue
        node = nodes[key]
        by_file.setdefault(node["file"], set()).add(node["start"])
    return [{"file": file, "lines": sorted(lines)} for file, lines in sorted(by_file.items())][:3]


def compare(upstream):
    index = build_index(upstream)
    return {"upstream_sha": UPSTREAM_SHA, "corpus_commit": CORPUS_COMMIT,
            "manifest": index["manifest"], "runtime": index["runtime"],
            "lexical": evaluate(lexical),
            "graph": evaluate(lambda task, root: graph_search(index, task, root))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(compare(args.upstream), sort_keys=True, indent=2))
    except Exception:
        raise SystemExit("CODE_GRAPH_COMPARISON_FAILED") from None
