#!/usr/bin/env bash
# Submit one Apptainer job per enabled GlyGen model.
set -euo pipefail

mode="--full"; submit=0; models="HZ1,HZ2"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke|--full) mode="$1" ;;
    --submit) submit=1 ;;
    --model-id|--models) [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 2; }; models="$2"; shift ;;
    -h|--help) echo "usage: submit_submission_models_cluster_apptainer.sh [--smoke|--full] [--model-id HZ1,HZ2] [--submit]"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the GlyGen checkout" >&2; exit 1; }
mkdir -p "${SUBMISSION_WORK_DIR}/qsub_logs"
IFS=',' read -r -a selected <<< "${models}"
for model in "${selected[@]}"; do
  [[ "${model}" == "HZ1" || "${model}" == "HZ2" ]] || { echo "Unknown GlyGen model: ${model}" >&2; exit 2; }
  command=(bash "${root}/run/run_submission_models_apptainer.sh" "${mode}" --models "${model}")
  if [[ ${submit} -eq 0 ]]; then printf 'Would submit GlyGen %s: ' "${model}"; printf '%q ' "${command[@]}"; printf '\n'; continue; fi
  "${QSUB_BIN:-qsub}" -V -b y -N "glygen_${model}" -o "${SUBMISSION_WORK_DIR}/qsub_logs/glygen_${model}.out" -e "${SUBMISSION_WORK_DIR}/qsub_logs/glygen_${model}.err" -l "h_vmem=${SUBMISSION_ARRAY_MEMORY:-4G},h_rt=${SUBMISSION_ARRAY_WALLTIME:-04:00:00}" /bin/bash "${root}/run/run_submission_models_apptainer.sh" "${mode}" --models "${model}"
done
