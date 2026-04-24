#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

bash "${repo_root}/run/execute_gtex_model_sweep_model.v1.sh" \
  --model_name 'modern_stratum_legacy200' \
  --model_run_plan_tsv "${repo_root}/outputs/gtex_model_sweep_v1/model_run_plan.v1.tsv" \
  --output_dir "${repo_root}/outputs/gtex_model_sweep_v1" \
  --reference_gmt_gz "${repo_root}/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz" \
  --workflow_repo '/home/ryank/software/geneset_extractors/dig-gene-set-extractors' \
  --resume \
  "$@"
