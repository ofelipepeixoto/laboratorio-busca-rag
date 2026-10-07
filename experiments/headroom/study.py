"""Original Radar study (MIT). No package import, providers or telemetry.

Only the hash-pinned stdlib transform is loaded from an explicit checkout.
This is fixture evaluation, not an LLM benchmark or a runtime integration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

UPSTREAM_COMMIT = "87e05b68b8aa578f1439abfc8006b38cd09db14d"
SOURCE_DIGEST = "a1084e69edbad3a2cd9aa03bd89cab20f249f6162c076f384d2c57944bc2f0c8"
SOURCE_PATH = "headroom/transforms/lossless_compaction.py"
MAX_INPUT_BYTES = 65536
MAX_CORPUS_BYTES = 262144
MARKER = re.compile(r"^\.\.\. \((?:repeated|repeats) .+\)$", re.MULTILINE)
ROOT = Path(__file__).parent


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Evidence:
    source_id: str
    original: str
    original_digest: str
    anchors: tuple[tuple[int, int, str], ...]

    def validate(self) -> None:
        if digest(self.original) != self.original_digest:
            raise ValueError("Original evidence changed")
        for start, end, expected in self.anchors:
            if self.quote(start, end, self.original_digest) != expected:
                raise ValueError("Critical span changed")

    def quote(self, start: int, end: int, expected_digest: str) -> str:
        if expected_digest != self.original_digest or digest(self.original) != expected_digest:
            raise ValueError("Evidence integrity mismatch")
        if type(start) is not int or type(end) is not int:
            raise ValueError("Offsets must be integer character indices")
        if not 0 <= start < end <= len(self.original):
            raise ValueError("Invalid evidence span")
        return self.original[start:end]


def read_cases(path: Path = ROOT / "corpus.json") -> list[Evidence]:
    if path.stat().st_size > MAX_CORPUS_BYTES:
        raise ValueError("Corpus exceeds fixture budget")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not 1 <= len(data) <= 32:
        raise ValueError("Invalid fixture count")
    cases = [Evidence(row["id"], row["original"], row["sha256"],
                      tuple((a["start"], a["end"], a["text"]) for a in row["anchors"]))
             for row in data]
    if len({c.source_id for c in cases}) != len(cases):
        raise ValueError("Duplicate evidence id")
    for case in cases:
        if len(case.original.encode("utf-8")) > MAX_INPUT_BYTES:
            raise ValueError("Fixture exceeds input budget")
        case.validate()
    return cases


def load_transform(checkout: Path) -> ModuleType:
    """Load exact audited bytes, bypassing headroom/__init__ and all extras.

    Ordinary module execution is safe only because digest matches the reviewed
    stdlib-only file. This is not a sandbox for arbitrary Python or checkouts.
    """
    path = checkout / SOURCE_PATH
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Unexpected source size")
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_DIGEST:
        raise ValueError("Unexpected Headroom source; refusing execution")
    module = ModuleType("radar_audited_headroom_lossless")
    # S102: execution is restricted to exact hash-pinned, reviewed source bytes.
    exec(compile(source, SOURCE_PATH, "exec"), module.__dict__)  # noqa: S102
    return module


def present(evidence: Evidence, transform: ModuleType | None) -> tuple[str, str]:
    """Compress consecutive lines only; never call unbounded upstream inverse."""
    evidence.validate()
    original = evidence.original
    if len(original.encode("utf-8")) > MAX_INPUT_BYTES:
        return original, "input_budget_bypass"
    if transform is None:
        return original, "baseline_only"
    if MARKER.search(original):
        return original, "literal_marker_bypass"
    try:
        candidate = transform.collapse_runs(original)
        # Independent inverse with allocation bounded by the original length.
        recovered = expand_bounded(candidate, len(original))
        if recovered != original:
            return original, "roundtrip_bypass"
        if len(candidate.encode("utf-8")) >= len(original.encode("utf-8")):
            return original, "no_gain_bypass"
        return candidate, "compressed"
    except (ValueError, OverflowError):
        return original, "expansion_budget_bypass"


def expand_bounded(text: str, max_chars: int) -> str:
    """Original inverse of upstream run syntax, bounded before allocation.

    Characters are Python indices, not bytes or a total-process RSS budget.
    Caller independently bounds input bytes before entering the transform.
    """
    if type(max_chars) is not int or max_chars < 0:
        raise ValueError("Invalid output budget")
    if not text:
        return text
    trailing = text.endswith("\n")
    lines = (text[:-1] if trailing else text).split("\n")
    out: list[str] = []
    units = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        match = (re.fullmatch(r"\.\.\. \(repeated (\d+) times\)", lines[index + 1])
                 if index + 1 < len(lines) else None)
        count = int(match.group(1)) if match else 1
        if count < 1:
            raise ValueError("Invalid repetition count")
        units += (len(line) + 1) * count
        if units > max_chars + (0 if trailing else 1):
            raise ValueError("Expansion exceeds original budget")
        out.extend([line] * count)
        index += 2 if match else 1
    result = "\n".join(out) + ("\n" if trailing else "")
    if len(result) > max_chars:
        raise ValueError("Expansion exceeds original budget")
    return result


def compare(cases: list[Evidence], transform: ModuleType | None) -> dict:
    rows = []
    for case in cases:
        presentation, status = present(case, transform)
        recovered = expand_bounded(presentation, len(case.original)) if status == "compressed" else presentation
        originals_ok = digest(recovered) == case.original_digest
        anchors_ok = all(case.quote(a, b, case.original_digest) == text
                         for a, b, text in case.anchors)
        rows.append({"id": case.source_id, "original_sha256": case.original_digest,
                     "original_bytes": len(case.original.encode("utf-8")),
                     "presented_bytes": len(presentation.encode("utf-8")),
                     "status": status, "roundtrip_exact": originals_ok,
                     "original_spans_verified": anchors_ok})
    before = sum(row["original_bytes"] for row in rows)
    after = sum(row["presented_bytes"] for row in rows)
    return {"decision": "B-STUDY", "upstream_commit": UPSTREAM_COMMIT,
            "headroom_transform_executed": transform is not None,
            "mode": "stdlib-collapse-runs-only", "offset_unit": "python-unicode-characters",
            "cases": rows, "original_bytes": before, "presented_bytes": after,
            "byte_reduction_fraction": 1 - after / before if before else None,
            "integrity_gate_passed": all(r["roundtrip_exact"] and r["original_spans_verified"] for r in rows),
            "tokens_measured": False, "llm_executed": False,
            "answer_quality_gate_passed": None, "cost_savings_verified": False,
            "integration_approved": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headroom-source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare(read_cases(), load_transform(args.headroom_source) if args.headroom_source else None)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["integrity_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
