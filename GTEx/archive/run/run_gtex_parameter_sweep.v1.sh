#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "${repo_root}/src/run_gtex_parameter_sweep.v1.py" \
  --output_dir "${repo_root}/outputs/gtex_parameter_sweep_v1" \
  --workflow_repo "${repo_root}/dig-gene-set-extractors" \
  --reference_gmt_gz "${repo_root}/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz" \
  --deg_tsv "${repo_root}/outputs/gtex_no_harmonizome_analysis_v1/combined/deg_long_combined.v1.tsv" \
  "$@"
