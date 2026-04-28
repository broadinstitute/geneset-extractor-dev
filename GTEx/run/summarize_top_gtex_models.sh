#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd "${script_dir}/../../.." && pwd)
python_bin=${PYTHON_BIN:-python3}

exec "${python_bin}" \
  "${repo_root}/geneset-extractor-dev/GTEx/src/summarize_top_gtex_models.py" \
  "$@"
