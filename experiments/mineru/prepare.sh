#!/usr/bin/env bash
# Preparação usa rede para baixar código/dependências. A execução fica sem rede.
set -euo pipefail
experiment_dir="$(cd "$(dirname "$0")" && pwd)"
source_dir="${1:?Informe um diretório NOVO para o checkout MinerU}"
python_bin="${2:?Informe o Python 3.12 de um virtualenv dedicado}"
"$python_bin" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 necessário"'
if [ -e "$source_dir" ]; then
  echo 'O destino já existe; escolha um novo diretório para preservar o trabalho.' >&2
  exit 1
fi
git clone --no-checkout https://github.com/opendatalab/MinerU.git "$source_dir"
git -C "$source_dir" checkout --detach ed50cc15bc2c9bfb00520dadfe61979866e62236
for candidate_patch in "$experiment_dir"/patches/*.patch; do
  git -C "$source_dir" apply --check "$candidate_patch"
  git -C "$source_dir" apply "$candidate_patch"
done
"$python_bin" -m pip install -c "$experiment_dir/constraints.txt" -e "$source_dir" pypdf==6.19.0 pytest==9.1.1
"$python_bin" -m pip check
echo 'Snapshot e três patches preparados; executar testes e experimento conforme README.'
