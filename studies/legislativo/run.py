# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
"""Local fixture replay; creates new output only, no publication authority."""
import argparse
from pathlib import Path
from .core import canonical, evaluate, sha
from .fixtures import fixture


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    documents,cases=fixture()
    replay=evaluate(documents,cases)
    package={'schema':'radar-legislative-package/v1','corpus':documents,'cases':cases,'replay':replay}
    with args.output.open('xb') as stream:
        stream.write(canonical(package)+b'\n')
    print(f'Fixture: {len(documents)} documentos, {len(cases)} casos; SHA-256 canônico={sha(package)}. Revisão pendente.')

if __name__=='__main__':main()
