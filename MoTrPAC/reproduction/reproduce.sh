#!/usr/bin/env bash
set -euo pipefail
mode="${1:---smoke}"
case "${mode}" in
  --smoke) download_mode="--smoke"; dispatch_mode="--smoke" ;;
  --full|full) download_mode="full"; dispatch_mode="--full" ;;
  *) echo "usage: reproduce.sh [--smoke|--full]" >&2; exit 2 ;;
esac
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
output_root="${SUBMISSION_WORK_DIR:-${root}/work}"
mkdir -p "${output_root}"
bash "${root}/reproduction/download_inputs.sh" "${download_mode}"
exec bash "${root}/run/run_submission_models.sh" "${dispatch_mode}" --out-root "${output_root}"
