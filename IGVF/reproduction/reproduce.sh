#!/usr/bin/env bash
set -euo pipefail
library_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
mode=${1:---smoke}
case "${mode}" in --smoke|full) ;; *) echo 'usage: reproduce.sh [--smoke|full]' >&2; exit 2;; esac
# Isolated workspaces provide this external location for generated artifacts.
output_root=${SUBMISSION_WORK_DIR:?SUBMISSION_WORK_DIR must be set to the isolated output directory}
mkdir -p "${output_root}"
if [[ "${mode}" == "full" ]]; then bash "${library_root}/reproduction/download_inputs.sh"; fi
# The builder is the single local execution path; select smoke tasks from the manifest.
bash "${library_root}/run/build_igvf_genesets.sh" "${mode}" --out-root "${output_root}"
