"""Comparação autoral sobre corpus congelado; sem API, servidor ou LLM."""
import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unicodedata

from experiments.mineru.isolation import MAX_INPUT, MAX_OUTPUT, MAX_PAGE_TEXT, WALL_SECONDS

ROOT = Path(__file__).resolve().parent
UPSTREAM = "ed50cc15bc2c9bfb00520dadfe61979866e62236"
ENGINES = ("pypdf", "mineru-flash")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def normalize(text, engine):
    # Somente escape de cifrão da serialização Markdown; não remove números/negações.
    if engine == "mineru-flash":
        text = text.replace("\\$", "$")
    return " ".join(unicodedata.normalize("NFC", text).split())


def validate_result(result, engine, source_hash, page_count):
    if not isinstance(result, dict) or type(result.get("schema")) is not int or result["schema"] != 1:
        raise ValueError("invalid_result")
    if (result.get("engine") != engine or result.get("source_sha256") != source_hash
            or result.get("review_state") != "pending"):
        raise ValueError("provenance_mismatch")
    seconds = result.get("parse_seconds")
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("invalid_duration")
    pages = result.get("pages")
    if not isinstance(pages, list) or len(pages) != page_count:
        raise ValueError("page_count_mismatch")
    for number, page in enumerate(pages, 1):
        if not isinstance(page, dict) or type(page.get("number")) is not int or page["number"] != number:
            raise ValueError("page_order_mismatch")
        text = page.get("text")
        if not isinstance(text, str) or len(text.encode()) > MAX_PAGE_TEXT:
            raise ValueError("invalid_page_text")
        if digest(text.encode()) != page.get("text_sha256"):
            raise ValueError("text_hash_mismatch")
    return result


def metrics(case, result):
    texts = [normalize(p["text"], result["engine"]) for p in result["pages"]]
    hits = [bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", texts[page - 1]))
            for page, phrase in case["critical"]]
    empty = sum(not text for text in texts)
    return {"critical_found": sum(hits), "critical_total": len(hits),
            "critical_recall": sum(hits) / len(hits) if hits else None,
            "empty_pages": empty,
            "needs_review_or_ocr": empty > 0,
            "critical_by_page": [{"page": page, "found": found}
                                 for (page, _), found in zip(case["critical"], hits)]}


def child_environment(directory):
    # Não herda chaves, proxies, PYTHONPATH, HOME real nem configuração de provedor.
    return {"PATH": "/usr/bin:/bin", "HOME": str(directory), "TMPDIR": str(directory),
            "XDG_CONFIG_HOME": str(directory / "config"),
            "XDG_CACHE_HOME": str(directory / "cache"), "LANG": "C.UTF-8",
            "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
            "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
            "DO_NOT_TRACK": "1", "GRADIO_ANALYTICS_ENABLED": "False"}


def bounded_process(command, directory, timeout=WALL_SECONDS):
    """Limita espera, descarta stderr, mata o grupo e não acumula stdout em RAM."""
    with tempfile.TemporaryFile(dir=directory) as output:
        process = subprocess.Popen(command, cwd=directory, env=child_environment(directory),
                                   stdin=subprocess.DEVNULL, stdout=output,
                                   stderr=subprocess.DEVNULL, close_fds=True,
                                   start_new_session=True)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise ValueError("worker_timeout") from error
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        output.seek(0)
        data = output.read(MAX_OUTPUT + 1)
        if len(data) > MAX_OUTPUT:
            raise ValueError("output_limit")
        if process.returncode:
            raise ValueError("worker_failed")
        return data


def run_case(case, engine, python):
    if engine not in ENGINES:
        raise ValueError("engine_not_allowed")
    # Sem entrada livre: manifest e fixtures versionados constituem o experimento.
    name = case["file"]
    if Path(name).name != name or not name.endswith(".pdf"):
        raise ValueError("invalid_fixture_path")
    fixture = ROOT / "fixtures" / name
    if fixture.is_symlink() or fixture.stat().st_size > MAX_INPUT:
        raise ValueError("invalid_fixture")
    data = fixture.read_bytes()
    if digest(data) != case["sha256"]:
        raise ValueError("fixture_changed")
    with tempfile.TemporaryDirectory(prefix="radar-mineru-") as temp:
        directory = Path(temp)
        path = directory / "input.pdf"
        path.write_bytes(data)
        start = time.monotonic()
        raw = bounded_process([python, "-E", "-s", "-B", str(ROOT / "worker.py"), engine, str(path)], directory)
        wall = time.monotonic() - start
    result = validate_result(json.loads(raw), engine, case["sha256"], len(case["pages"]))
    return {"id": case["id"], "split": case["split"], "kind": case["kind"],
            "engine": engine, "source_sha256": case["sha256"],
            "versions": result["versions"], "review_state": "pending",
            "parse_seconds": result["parse_seconds"], "worker_seconds": wall,
            "page_text_hashes": [p["text_sha256"] for p in result["pages"]],
            "metrics": metrics(case, result)}


def evaluate(python, engines=ENGINES):
    manifest_bytes = (ROOT / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    rows, failures = [], []
    for case in manifest["cases"]:
        for engine in engines:
            try:
                rows.append(run_case(case, engine, python))
            except (ValueError, OSError) as error:
                failures.append({"id": case["id"], "engine": engine,
                                 "error": type(error).__name__})
    smoke = not failures
    for row in rows:
        if row["kind"] == "digital":
            smoke = smoke and row["metrics"]["critical_recall"] == 1.0
        else:
            smoke = smoke and row["metrics"]["needs_review_or_ocr"]
    patch_hashes = [f"{digest(p.read_bytes())}  {p.name}"
                    for p in sorted((ROOT / "patches").glob("*.patch"))]
    return {"schema": 1, "decision": "B — STUDY", "synthetic_only": True,
            "mineru_upstream_commit": UPSTREAM, "patch_sha256": patch_hashes,
            "manifest_sha256": digest(manifest_bytes), "engines_requested": list(engines),
            "execution_complete": not failures and len(rows) == len(manifest["cases"]) * len(engines),
            "quality_gate_passed": smoke, "integration_approved": False,
            "paid_calls": 0, "results": rows, "failures": failures,
            "limits": ["Seven synthetic PDF pages; not a representative benchmark",
                       "Flash/txt only; no OCR, weights, GPU, LLM or retrieval evaluation",
                       "One cold worker per case; no p95, throughput or isolated RSS measurement",
                       "No filesystem sandbox: only frozen synthetic fixtures are allowed",
                       "Text hashes and page positions are not Evidence Kit approval"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable, help="Python do ambiente opcional")
    parser.add_argument("--engine", choices=(*ENGINES, "both"), default="both")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    engines = ENGINES if args.engine == "both" else (args.engine,)
    report = evaluate(str(Path(args.python).absolute()), engines)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"quality_gate_passed": report["quality_gate_passed"],
                      "execution_complete": report["execution_complete"],
                      "executions": len(report["results"]), "failures": len(report["failures"]),
                      "integration_approved": False}))
    # Comparação concluída pode ter resultado negativo. Promoção usa quality_gate.
    return 0 if report["execution_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
