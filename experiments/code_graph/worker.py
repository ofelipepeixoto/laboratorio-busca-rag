"""Trusted, pinned parser over the frozen synthetic corpus ONLY. Not a sandbox."""
import contextlib
import hashlib
import json
import logging
import importlib.metadata
import os
import resource
import sys
from pathlib import Path


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024**2, 2 * 1024**2))
    sys.dont_write_bytecode = True
    upstream, corpus = map(Path, sys.argv[1:])
    sys.path.insert(0, str(upstream))
    logging.disable(logging.CRITICAL)
    from loguru import logger
    logger.remove()
    from codebase_rag.graph_updater import GraphUpdater
    from codebase_rag.parser_loader import load_parsers
    from evals.cgr_graph import _CapturingIngestor

    parsers, queries = load_parsers()
    # Only Python; fail instead of silently accepting an absent grammar/error tree.
    parser = parsers["python"]
    sources = {p.name: p.read_bytes() for p in corpus.glob("*.py")}
    for data in sources.values():
        if parser.parse(data).root_node.has_error:
            raise ValueError("PARSE_FAILED")
    ingestor = _CapturingIngestor()
    with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink):
        GraphUpdater(ingestor, corpus, {"python": parser},
                     {"python": queries["python"]}, project_name="radar_fixture",
                     skip_embeddings=True, state_dir=corpus.parent / "state").run(force=True)
    if {p.name: p.read_bytes() for p in corpus.glob("*.py")} != sources:
        raise ValueError("SOURCE_CHANGED_DURING_INDEXING")
    nodes = {}
    for (kind, uid), props in ingestor.nodes.items():
        name = props.get("path")
        if kind not in {"Module", "Class", "Function", "Method"} or name not in sources:
            continue
        start = props.get("start_line", 1)
        end = props.get("end_line", len(sources[name].splitlines()))
        if not (1 <= start <= end <= len(sources[name].splitlines())):
            raise ValueError("SPAN_INVALID")
        nodes[str(uid)] = {"file": name, "start": start, "end": end, "kind": kind}
    if {n["file"] for n in nodes.values() if n["kind"] == "Module"} != set(sources):
        raise ValueError("COVERAGE_INCOMPLETE")
    edges = sorted({(str(src), rel, str(dst)) for _, src, rel, _, dst in ingestor.rels
                    if rel in {"CALLS", "IMPORTS"}})
    runtime = {name: importlib.metadata.version(name)
               for name in ("tree-sitter", "tree-sitter-python", "code-graph-rag")}
    source_hashes = {name: hashlib.sha256(data).hexdigest() for name, data in sources.items()}
    print(json.dumps({"nodes": nodes, "edges": edges, "runtime": runtime,
                      "source_hashes": source_hashes}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Do not serialize upstream exceptions, source text, paths or prompts.
        sys.exit("CODE_GRAPH_WORKER_FAILED")
