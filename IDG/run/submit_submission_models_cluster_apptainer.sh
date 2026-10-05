#!/usr/bin/env bash
set -euo pipefail
root="${IDG_SCRIPT_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)}"
self_path="${root}/run/submit_submission_models_cluster_apptainer.sh"
mode="--full"; submit=0; refresh=0; models="all"
while [[ $# -gt 0 ]]; do case "$1" in --smoke|--full) mode="$1";; --submit) submit=1;; --refresh-metadata-and-provenance) refresh=1;; --model-id) models="$2"; shift;; -h|--help) echo "usage: $0 [--smoke|--full] [--model-id HZ1[,HZ2]] [--refresh-metadata-and-provenance] [--submit]"; exit 0;; *) echo "unknown argument: $1" >&2; exit 2;; esac; shift; done
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR" >&2; exit 1; }
if [[ ${refresh} -eq 1 ]]; then
  [[ "${mode}" == "--full" ]] || { echo "Refresh requires --full" >&2; exit 2; }
  command=(bash "${root}/../run/refresh_library_models_cluster_apptainer.sh" --library-id IDG --library-root "${root}" --out-root "${SUBMISSION_WORK_DIR}" --refresh-metadata-and-provenance)
  [[ "${models}" != "all" ]] && command+=(--model-id "${models}")
  [[ ${submit} -eq 1 ]] && command+=(--submit)
  exec "${command[@]}"
fi
mkdir -p "${SUBMISSION_WORK_DIR}/qsub_logs"; worklist="${SUBMISSION_WORK_DIR}/idg_qsub_worklist.tsv"
{ echo -e "task_id\tmodel_id"; if [[ "${models}" == all ]]; then echo -e "1\tHZ1\n2\tHZ2"; else n=0; IFS=',' read -r -a ids <<< "${models}"; for id in "${ids[@]}"; do [[ "${id}" =~ ^HZ[12]$ ]] || { echo "unknown IDG model: ${id}" >&2; exit 2; }; n=$((n+1)); echo -e "${n}\t${id}"; done; fi; } > "${worklist}"
if [[ -n "${SGE_TASK_ID:-}" || -n "${PBS_ARRAYID:-}" ]]; then
  task="${SGE_TASK_ID:-${PBS_ARRAYID}}"; model="$(awk -F $'\t' -v task="${task}" 'NR>1 && $1==task {print $2}' "${IDG_WORKLIST}")"
  [[ -n "${model}" ]] || { echo "no model for array task" >&2; exit 1; }
  if [[ "${IDG_REFRESH:-0}" == 1 ]]; then exec bash "${root}/run/refresh_submission_models_apptainer.sh" --models "${model}"; fi
  exec bash "${root}/run/run_submission_models_apptainer.sh" "${IDG_MODE}" --models "${model}"
fi
count="$(awk 'END {print NR-1}' "${worklist}")"; job="idg_${mode#--}"; [[ ${refresh} -eq 1 ]] && job="idg_refresh"
command=("${QSUB_BIN:-qsub}" -N "${job}" -t "1-${count}" -o "${SUBMISSION_WORK_DIR}/qsub_logs/${job}.\$TASK_ID.out" -e "${SUBMISSION_WORK_DIR}/qsub_logs/${job}.\$TASK_ID.err" -v "IDG_SCRIPT_ROOT=${root},IDG_WORKLIST=${worklist},IDG_MODE=${mode},IDG_REFRESH=${refresh},SUBMISSION_WORK_DIR=${SUBMISSION_WORK_DIR},DIG_REPO=${DIG_REPO:-},APPTAINER_IMAGE=${APPTAINER_IMAGE:-},APPTAINER_BIN=${APPTAINER_BIN:-},IDG_DRUG_TARGETS_GMT=${IDG_DRUG_TARGETS_GMT:-},IDG_ARCHS4_COEXP_GMT=${IDG_ARCHS4_COEXP_GMT:-},IDG_DRUG_TARGETS_SOURCE_URL=${IDG_DRUG_TARGETS_SOURCE_URL:-},IDG_ARCHS4_COEXP_SOURCE_URL=${IDG_ARCHS4_COEXP_SOURCE_URL:-}" "${self_path}")
if [[ ${submit} -eq 0 ]]; then printf 'Would submit IDG array: '; printf '%q ' "${command[@]}"; printf '\nSet --submit to call qsub.\n'; exit 0; fi
exec "${command[@]}"
