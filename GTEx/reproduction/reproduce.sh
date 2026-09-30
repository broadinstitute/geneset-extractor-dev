#!/usr/bin/env bash
set -euo pipefail

mode="${1:---smoke}"
case "${mode}" in
  --smoke|full) ;;
  *) echo "usage: reproduce.sh [--smoke|full]" >&2; exit 2 ;;
esac

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
output_root="${SUBMISSION_WORK_DIR:-${root}/work}"
mkdir -p "${output_root}"
bash "${root}/reproduction/download_inputs.sh" "${mode}"
bash "${root}/run/run_submission_models.sh" "${mode}" --out-root "${output_root}"
task_id="gtex_smoke_hz2_all_detailed_tissues"
if [[ "${mode}" == "full" ]]; then task_id="gtex_hz2_all_detailed_tissues"; fi
exec bash "${root}/run/build_gtex_genesets.sh" "${mode}" --task-id "${task_id}" --out-root "${output_root}"
