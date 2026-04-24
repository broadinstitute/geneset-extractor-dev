#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

bash "${repo_root}/run/execute_gtex_model_sweep_workflow.v1.sh" \
  --workflow_name 'de=modern__balance=false__seed=0__scope=contrast__covariates=sex,smtsd__backend=lightweight' \
  --workflow_plan_tsv "${repo_root}/outputs/gtex_model_sweep_v1/workflow_run_plan.v1.tsv" \
  --output_dir "${repo_root}/outputs/gtex_model_sweep_v1" \
  --workflow_repo '/home/ryank/software/geneset_extractors/dig-gene-set-extractors' \
  --resume \
  "$@"
