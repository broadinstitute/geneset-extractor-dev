#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "${repo_root}/src/run_gtex_model_sweep.v1.py" \
  --output_dir "${repo_root}/outputs/gtex_model_sweep_v1" \
  --model_manifest_tsv "${repo_root}/outputs/gtex_model_sweep_v1/model_manifest.v1.tsv" \
  --reference_gmt_gz "${repo_root}/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz" \
  --workflow_repo "${repo_root}/../../dig-gene-set-extractors" \
  "$@"
