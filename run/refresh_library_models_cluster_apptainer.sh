#!/usr/bin/env bash
# Refresh metadata and provenance for completed library model outputs.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="${REPO_ROOT:-$(cd -- "${script_dir}/../.." && pwd -P)}"
library_id=""
library_root=""
out_root="${LIBRARY_OUT_ROOT:-${SUBMISSION_WORK_DIR:-}}"
targets_tsv=""
model_ids=""
partition_ids=""
submit=0
task_index="${SGE_TASK_ID:-${PBS_ARRAYID:-}}"
qsub_bin="${QSUB_BIN:-qsub}"
qsub_log_root="${QSUB_LOG_ROOT:-}"
worklist="${REFRESH_WORKLIST:-}"
dig_dir="${DIG_DIR:-${DIG_REPO:-${repo_root}/dig-gene-set-extractors}}"

usage() {
  cat <<'EOF'
Usage: refresh_library_models_cluster_apptainer.sh --library-id ID --library-root PATH --out-root PATH [options]

Options:
  --submit                                  Submit the refresh array. Without it, write a worklist only.
  --model-id ID[,ID...]                      Refresh only these model IDs.
  --partition-id ID[,ID...]                  Refresh only these partitions.
  --targets-tsv PATH                         Override config/refresh_targets.tsv.
  --refresh-metadata-and-provenance          Required operation marker; accepted for launcher compatibility.

Required environment for --submit: APPTAINER_IMAGE and a DIG checkout via
DIG_DIR or DIG_REPO. DESCRIPTION_TEMPLATE_TSV defaults to the library's
config/model_description_templates.tsv. Optional provenance environment:
PROVENANCE_MIRROR_LOCAL_PREFIX, PROVENANCE_MIRROR_REMOTE_PREFIX, and
LOCAL_INPUT_SOURCE_MAP_TSV.
EOF
}

contains_csv_value() {
  local csv="$1" value="$2" item
  [[ -z "${csv}" ]] && return 0
  IFS=',' read -r -a items <<< "${csv}"
  for item in "${items[@]}"; do
    [[ "${item//[[:space:]]/}" == "${value}" ]] && return 0
  done
  return 1
}

is_enabled_model() {
  local model_id="$1"
  local model_list="${library_root}/config/model_list.tsv"
  [[ -f "${model_list}" ]] || return 0
  awk -F $'\t' -v wanted="${model_id}" '
    NR == 1 {
      for (i = 1; i <= NF; i++) {
        if ($i == "model_id") model_col = i
        if ($i == "enabled") enabled_col = i
      }
      next
    }
    $model_col == wanted && $enabled_col == "true" { found = 1; exit }
    END { exit !found }
  ' "${model_list}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --library-id) library_id="$2"; shift 2 ;;
    --library-root) library_root="$2"; shift 2 ;;
    --out-root) out_root="$2"; shift 2 ;;
    --targets-tsv) targets_tsv="$2"; shift 2 ;;
    --model-id|--model_id|--models) model_ids="$2"; shift 2 ;;
    --partition-id|--partition_id|--tissue-id|--tissue_id) partition_ids="$2"; shift 2 ;;
    --submit) submit=1; shift ;;
    --refresh-metadata-and-provenance|--refresh_metadata_and_provenance) shift ;;
    --task-index) task_index="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "${library_id}" && -n "${library_root}" && -n "${out_root}" ]] || { usage >&2; exit 2; }
library_root="$(cd -- "${library_root}" && pwd -P)"
out_root="$(cd -- "${out_root}" && pwd -P)"
targets_tsv="${targets_tsv:-${library_root}/config/refresh_targets.tsv}"
description_template_tsv="${DESCRIPTION_TEMPLATE_TSV:-${library_root}/config/model_description_templates.tsv}"
qsub_log_root="${qsub_log_root:-${out_root}/qsub_logs_refresh}"
worklist="${worklist:-${qsub_log_root}/${library_id,,}_refresh_worklist.tsv}"

[[ -f "${targets_tsv}" ]] || { echo "Missing refresh target map: ${targets_tsv}" >&2; exit 1; }
[[ -f "${description_template_tsv}" ]] || { echo "Missing DESCRIPTION_TEMPLATE_TSV: ${description_template_tsv}" >&2; exit 1; }

run_worker() {
  local row model_id partition_id model_dir
  row="$(awk -F $'\t' -v index="${task_index}" 'NR > 1 && $1 == index { print; exit }' "${worklist}")"
  [[ -n "${row}" ]] || { echo "No refresh worklist row for task ${task_index}" >&2; exit 1; }
  IFS=$'\t' read -r _ model_id partition_id model_dir <<< "${row}"
  [[ -d "${model_dir}" ]] || { echo "Missing model output: ${model_dir}" >&2; exit 1; }
  [[ -d "${dig_dir}" ]] || { echo "Missing DIG checkout: ${dig_dir}" >&2; exit 1; }
  command=(bash "${script_dir}/refresh_model_metadata_and_provenance_apptainer.sh"
    --model_id "${model_id}" --model_dir "${model_dir}"
    --description_template_tsv "${description_template_tsv}")
  [[ -n "${PROVENANCE_MIRROR_LOCAL_PREFIX:-}" ]] && command+=(--provenance_mirror_local_prefix "${PROVENANCE_MIRROR_LOCAL_PREFIX}")
  [[ -n "${PROVENANCE_MIRROR_REMOTE_PREFIX:-}" ]] && command+=(--provenance_mirror_remote_prefix "${PROVENANCE_MIRROR_REMOTE_PREFIX}")
  [[ -n "${LOCAL_INPUT_SOURCE_MAP_TSV:-}" ]] && command+=(--local_input_source_map_tsv "${LOCAL_INPUT_SOURCE_MAP_TSV}")
  printf '$ '; printf '%q ' "${command[@]}"; printf '\n'
  DIG_DIR="${dig_dir}" "${command[@]}"
}

if [[ -n "${task_index}" ]]; then
  run_worker
  exit 0
fi

mkdir -p "${qsub_log_root}"
printf 'task_index\tmodel_id\tpartition_id\tmodel_dir\n' > "${worklist}"
target_count=0
while IFS=$'\t' read -r target_id target_model_id target_partition_id enabled model_dir_glob; do
  [[ "${target_id}" == "target_id" || "${enabled}" != "true" ]] && continue
  # Globs are intentionally expanded only under the declared output root.
  shopt -s nullglob
  matches=("${out_root}"/${model_dir_glob})
  shopt -u nullglob
  for model_dir in "${matches[@]}"; do
    [[ -d "${model_dir}" && -d "${model_dir}/extractor" || -d "${model_dir}/tissue_extractor" ]] || continue
    model_id="${target_model_id}"
    partition_id="${target_partition_id}"
    [[ "${model_id}" == "*" ]] && model_id="$(basename "${model_dir}")"
    if [[ "${partition_id}" == "*" ]]; then
      partition_id="$(basename "$(dirname "$(dirname "${model_dir}")")")"
    fi
    contains_csv_value "${model_ids}" "${model_id}" || continue
    contains_csv_value "${partition_ids}" "${partition_id}" || continue
    is_enabled_model "${model_id}" || continue
    target_count=$((target_count + 1))
    printf '%s\t%s\t%s\t%s\n' "${target_count}" "${model_id}" "${partition_id}" "${model_dir}" >> "${worklist}"
  done
done < "${targets_tsv}"

[[ ${target_count} -gt 0 ]] || { echo "No completed refresh targets matched the requested filters." >&2; exit 1; }
echo "Refresh worklist written: ${worklist} (${target_count} targets)"
if [[ ${submit} -eq 0 ]]; then
  echo "Set --submit to call qsub."
  exit 0
fi
[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "--submit requires APPTAINER_IMAGE" >&2; exit 1; }
[[ -d "${dig_dir}" ]] || { echo "--submit requires DIG_DIR or DIG_REPO" >&2; exit 1; }
environment="REPO_ROOT=${repo_root},WORK_ROOT=${out_root},REFRESH_WORKLIST=${worklist},DIG_DIR=${dig_dir},APPTAINER_IMAGE=${APPTAINER_IMAGE},APPTAINER_BIN=${APPTAINER_BIN:-apptainer},APPTAINER_EXTRA_ARGS=${APPTAINER_EXTRA_ARGS:-},APPTAINER_PYTHON_BIN=${APPTAINER_PYTHON_BIN:-python},DESCRIPTION_TEMPLATE_TSV=${description_template_tsv},PROVENANCE_MIRROR_LOCAL_PREFIX=${PROVENANCE_MIRROR_LOCAL_PREFIX:-},PROVENANCE_MIRROR_REMOTE_PREFIX=${PROVENANCE_MIRROR_REMOTE_PREFIX:-},LOCAL_INPUT_SOURCE_MAP_TSV=${LOCAL_INPUT_SOURCE_MAP_TSV:-}"
exec "${qsub_bin}" -N "${library_id,,}_refresh" -t "1-${target_count}" \
  -o "${qsub_log_root}/${library_id,,}_refresh.\$TASK_ID.out" \
  -e "${qsub_log_root}/${library_id,,}_refresh.\$TASK_ID.err" \
  -l "h_vmem=${SUBMISSION_ARRAY_MEMORY:-16G},h_rt=${SUBMISSION_ARRAY_WALLTIME:-24:00:00}" \
  -v "${environment}" "$0" --library-id "${library_id}" --library-root "${library_root}" --out-root "${out_root}" --targets-tsv "${targets_tsv}" --submit
