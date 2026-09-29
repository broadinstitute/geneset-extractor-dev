#!/usr/bin/env bash
set -euo pipefail

mode="${1:---smoke}"
case "${mode}" in --smoke|full) ;; *) echo "usage: reproduce.sh [--smoke|full]" >&2; exit 2 ;; esac
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
output_root="${SUBMISSION_WORK_DIR:-${root}/work}"
mkdir -p "${output_root}"
bash "${root}/reproduction/download_inputs.sh" "${mode}"
exec bash "${root}/run/run_submission_models.sh" "${mode}" --out-root "${output_root}"
