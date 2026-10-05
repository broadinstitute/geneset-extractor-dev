#!/usr/bin/env bash
set -euo pipefail
mode="--full"; submit=0; refresh=0
while [[ $# -gt 0 ]]; do case "$1" in
  --smoke|--full) mode="$1";; --submit) submit=1;;
  --refresh-metadata-and-provenance|--refresh_metadata_and_provenance) refresh=1;;
  -h|--help) echo "usage: submit_submission_models_cluster_apptainer.sh [--smoke|--full] [--refresh-metadata-and-provenance] [--submit]"; exit 0;;
  *) echo "Unknown argument: $1" >&2; exit 2;; esac; shift; done
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the checkout" >&2; exit 1; }
mkdir -p "${SUBMISSION_WORK_DIR}/qsub_logs"
if [[ ${refresh} -eq 1 ]]; then
  [[ "${mode}" == "--full" ]] || { echo "Refresh requires --full" >&2; exit 2; }
  command=(bash "${root}/../run/refresh_library_models_cluster_apptainer.sh" --library-id MetabolomicsWorkbench --library-root "${root}" --out-root "${SUBMISSION_WORK_DIR}" --refresh-metadata-and-provenance)
  [[ ${submit} -eq 1 ]] && command+=(--submit)
  exec "${command[@]}"
fi
cmd=(bash "${root}/run/run_submission_models_apptainer.sh" "${mode}")
if [[ ${submit} -eq 0 ]]; then printf 'Would submit MetabolomicsWorkbench HZ1: '; printf '%q ' "${cmd[@]}"; printf '\n'; exit 0; fi
exec "${QSUB_BIN:-qsub}" -V -b y -N metabolomics_workbench_hz1 -o "${SUBMISSION_WORK_DIR}/qsub_logs/metabolomics_workbench_hz1.out" -e "${SUBMISSION_WORK_DIR}/qsub_logs/metabolomics_workbench_hz1.err" -l "h_vmem=${SUBMISSION_ARRAY_MEMORY:-4G},h_rt=${SUBMISSION_ARRAY_WALLTIME:-04:00:00}" /bin/bash "${root}/run/run_submission_models_apptainer.sh" "${mode}"
