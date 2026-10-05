#!/usr/bin/env bash
set -euo pipefail
mode="${1:---full}"; shift || true
case "${mode}" in --smoke|--full|full) ;; *) echo "usage: reproduce.sh [--smoke|--full|full]" >&2; exit 2 ;; esac
[[ "${mode}" == "full" ]] && mode="--full"
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
output_root="${SUBMISSION_WORK_DIR:-${root}/outputs/direct_import}"
mkdir -p "${output_root}"
exec bash "${root}/run/run_submission_models.sh" "${mode}" --out-root "${output_root}" "$@"
