#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON_BIN="python3"

if [[ $# -ge 2 && "$1" == "--python_bin" ]]; then
  PYTHON_BIN="$2"
  shift 2
fi

exec "${PYTHON_BIN}" "${REPO_ROOT}/geneset-extractor-dev/GTEx/src/prepare_gtex_tissue_inputs.py" "$@"
