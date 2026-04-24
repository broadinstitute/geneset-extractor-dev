#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "${repo_root}/src/run_gtex_harmonizome_analysis.v1.py" \
  --output_dir "${repo_root}/outputs/gtex_harmonizome_analysis_v1" \
  --workflow_repo "${repo_root}/dig-gene-set-extractors" \
  --reference_gmt_gz "${repo_root}/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz" \
  "$@"
