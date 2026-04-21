#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "${repo_root}/src/run_gene_set_comparison.v1.py" \
  --output_dir "${repo_root}/outputs/gene_set_comparison_v1" \
  "$@"
