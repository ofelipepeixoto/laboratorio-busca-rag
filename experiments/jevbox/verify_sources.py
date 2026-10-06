# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
"""Verify recorded files and optional immutable upstream checkout before patches."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def verify(upstream=None):
    manifest = json.loads((ROOT / "source-manifest.json").read_text())
    for relative, expected in manifest["files"].items():
        path = (ROOT / relative).resolve(strict=True)
        if not path.is_relative_to(ROOT) or sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("source manifest mismatch: " + relative)
    if upstream is not None:
        upstream = upstream.resolve(strict=True)
        commit = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
        if commit != manifest["upstream"]["commit"]:
            raise ValueError("wrong upstream commit")
        source = (upstream / "server/beam-search.ts").read_bytes()
        if sha256(source).hexdigest() != manifest["upstream"]["source_file_sha256"]:
            raise ValueError("extracted source changed")
    print("Source, patch, probe and license hashes verified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path)
    verify(parser.parse_args().upstream)
