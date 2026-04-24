#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workspace_root="$(cd "${repo_root}/../.." && pwd)"

python3 "${repo_root}/src/run_gtex_model_sweep_adipose.v1.py" \
  --output_dir "${repo_root}/outputs/gtex_model_sweep_adipose_v1" \
  --base_model_run_plan_tsv "${repo_root}/outputs/gtex_model_sweep_v1/model_run_plan.v1.tsv" \
  --base_workflow_run_plan_tsv "${repo_root}/outputs/gtex_model_sweep_v1/workflow_run_plan.v1.tsv" \
  --workflow_repo "${workspace_root}/dig-gene-set-extractors" \
  --pigean_repo "${workspace_root}/pigean" \
  --reference_gmt_gz "${repo_root}/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz" \
  --resume \
  "$@"
