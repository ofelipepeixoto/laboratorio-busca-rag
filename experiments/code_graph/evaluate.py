"""File-level retrieval experiment; no target code execution or LLM calls."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_fixture(root=ROOT):
    manifest = json.loads((root / "manifest.json").read_text())
    actual = {"tasks.json"} | {
        p.relative_to(root).as_posix() for p in (root / "corpus").rglob("*")
        if p.is_file() or p.is_symlink()
    }
    if actual != set(manifest):
        raise ValueError("FIXTURE_FILE_SET_CHANGED")
    for name, expected in manifest.items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("FIXTURE_PATH_REJECTED")
        if digest(path.read_bytes()) != expected:
            raise ValueError("FIXTURE_HASH_CHANGED")
    return manifest


def lexical(task, root=ROOT):
    # A reproducible literal-search baseline, not a simulation of human/Codex review.
    pattern = re.compile(r"\b" + re.escape(task["term"]) + r"\b")
    hits = []
    for path in sorted((root / "corpus").glob("*.py")):
        lines = [i for i, line in enumerate(path.read_text().splitlines(), 1)
                 if pattern.search(line)]
        if lines:
            hits.append({"file": path.name, "lines": lines})
    return sorted(hits, key=lambda hit: (-len(hit["lines"]), hit["file"]))[:3]


def grade(expected, hits):
    actual = {hit["file"] for hit in hits}
    expected = set(expected)
    return {"tp": len(actual & expected), "fp": len(actual - expected),
            "fn": len(expected - actual), "exact": actual == expected}


def evaluate(retrieve, root=ROOT):
    verify_fixture(root)
    rows = []
    for task in json.loads((root / "tasks.json").read_text()):
        hits = retrieve(task, root=root)
        rows.append({"id": task["id"], "split": task["split"],
                     "hits": hits, **grade(task["expected"], hits)})
    totals = {}
    for split in ("development", "reserved"):
        selected = [row for row in rows if row["split"] == split]
        tp, fp, fn = (sum(row[k] for row in selected) for k in ("tp", "fp", "fn"))
        totals[split] = {"tasks": len(selected),
                         "exact": sum(row["exact"] for row in selected),
                         "precision_at_3": tp / (tp + fp) if tp + fp else None,
                         "recall_at_3": tp / (tp + fn) if tp + fn else None}
    return {"totals": totals, "rows": rows}


if __name__ == "__main__":
    print(json.dumps(evaluate(lexical), sort_keys=True, indent=2))
