#!/usr/bin/env bash
set -euo pipefail

root="${GAULTONLAB_SCRIPT_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)}"
self_path="${root}/run/submit_submission_models_cluster_apptainer.sh"
mode="--full"; submit=0; refresh=0; models="all"; partitions="all"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke|--full) mode="$1" ;;
    --submit) submit=1 ;;
    --refresh-metadata-and-provenance|--refresh_metadata_and_provenance) refresh=1 ;;
    --model-id|--models) models="$2"; shift ;;
    --partition-id|--partitions) partitions="$2"; shift ;;
    -h|--help)
      echo "usage: $0 [--smoke|--full] [--model-id HZ1[,HZ2,HZ3]] [--partition-id heart[,liver,lung,spleen]] [--refresh-metadata-and-provenance] [--submit]"
      exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the checkout" >&2; exit 1; }
if [[ ${refresh} -eq 1 ]]; then
  [[ "${mode}" == "--full" ]] || { echo "Refresh requires --full" >&2; exit 2; }
  command=(bash "${root}/run/refresh_submission_models_apptainer.sh")
  [[ "${models}" != "all" ]] && command+=(--model-id "${models}")
  [[ "${partitions}" != "all" ]] && command+=(--partition-id "${partitions}")
  [[ ${submit} -eq 1 ]] && command+=(--submit)
  exec "${command[@]}"
fi

mkdir -p "${SUBMISSION_WORK_DIR}/qsub_logs"
worklist="${SUBMISSION_WORK_DIR}/gaultonlab_qsub_worklist.tsv"
awk -F $'\t' -v models="${models}" -v partitions="${partitions}" '
  function selected(value, csv, n, items, i) {
    if (csv == "all") return 1
    n = split(csv, items, ",")
    for (i = 1; i <= n; i++) if (items[i] == value) return 1
    return 0
  }
  BEGIN { print "task_index\tmodel_id\tpartition_id" }
  NR > 1 && $4 == "true" && selected($2, models) && selected($3, partitions) {
    n++; print n "\t" $2 "\t" $3
  }
  END { if (n == 0) exit 1 }
' "${root}/config/task_manifest.tsv" > "${worklist}" || { echo "No enabled tasks match the requested model/partition filters" >&2; exit 2; }

if [[ -n "${SGE_TASK_ID:-}" || -n "${PBS_ARRAYID:-}" ]]; then
  task="${SGE_TASK_ID:-${PBS_ARRAYID}}"
  row="$(awk -F $'\t' -v task="${task}" 'NR > 1 && $1 == task { print; exit }' "${GAULTONLAB_WORKLIST}")"
  [[ -n "${row}" ]] || { echo "No GaultonLab task for array index ${task}" >&2; exit 1; }
  IFS=$'\t' read -r _ model_id partition_id <<< "${row}"
  exec bash "${root}/run/run_submission_models_apptainer.sh" "${GAULTONLAB_MODE}" --models "${model_id}" --partitions "${partition_id}"
fi

count="$(awk 'END { print NR - 1 }' "${worklist}")"
job="gaultonlab_${mode#--}"
command=("${QSUB_BIN:-qsub}" -N "${job}" -t "1-${count}"
  -o "${SUBMISSION_WORK_DIR}/qsub_logs/${job}.\$TASK_ID.out"
  -e "${SUBMISSION_WORK_DIR}/qsub_logs/${job}.\$TASK_ID.err"
  -l "h_vmem=${SUBMISSION_ARRAY_MEMORY:-4G},h_rt=${SUBMISSION_ARRAY_WALLTIME:-04:00:00}"
  -v "GAULTONLAB_SCRIPT_ROOT=${root},GAULTONLAB_WORKLIST=${worklist},GAULTONLAB_MODE=${mode},SUBMISSION_WORK_DIR=${SUBMISSION_WORK_DIR},DIG_REPO=${DIG_REPO:-},APPTAINER_IMAGE=${APPTAINER_IMAGE:-},APPTAINER_BIN=${APPTAINER_BIN:-},APPTAINER_PYTHON_BIN=${APPTAINER_PYTHON_BIN:-python},GAULTONLAB_GMT_DIR=${GAULTONLAB_GMT_DIR:-},GAULTONLAB_GMT_MAP_TSV=${GAULTONLAB_GMT_MAP_TSV:-}"
  "${self_path}")
if [[ ${submit} -eq 0 ]]; then
  printf 'Would submit GaultonLab array: '; printf '%q ' "${command[@]}"; printf '\nSet --submit to call qsub.\n'
  exit 0
fi
exec "${command[@]}"
