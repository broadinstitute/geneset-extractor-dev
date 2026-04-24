#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "${repo_root}/src/run_eaggl_gene_list_batch.v1.py" \
  --output_dir "${repo_root}/outputs/eaggl_gene_list_batch_v1" \
  --pigean_repo "${repo_root}/pigean" \
  "$@"
