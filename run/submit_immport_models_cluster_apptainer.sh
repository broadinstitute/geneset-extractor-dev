#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPO_ROOT="${REPO_ROOT:-${DEFAULT_REPO_ROOT}}"
SELF_PATH="${REPO_ROOT}/geneset-extractor-dev/run/submit_immport_models_cluster_apptainer.sh"
WORK_ROOT="${WORK_ROOT:-$(pwd)}"

IMMPORT_CONFIG_ROOT="${IMMPORT_CONFIG_ROOT:-${REPO_ROOT}/geneset-extractor-dev/ImmPort/config}"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"

IMMPORT_MODEL_LIST="${IMMPORT_MODEL_LIST:-${IMMPORT_CONFIG_ROOT}/model_list.tsv}"
IMMPORT_MODEL_MANIFEST="${IMMPORT_MODEL_MANIFEST:-${IMMPORT_CONFIG_ROOT}/model_manifest.tsv}"
IMMPORT_STUDY_LIST="${IMMPORT_STUDY_LIST:-${IMMPORT_CONFIG_ROOT}/study_list.tsv}"

IMMPORT_OUT_ROOT="${IMMPORT_OUT_ROOT:-${WORK_ROOT}/immport_all_models}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_immport}"
IMMPORT_WORKLIST="${IMMPORT_WORKLIST:-${WORK_ROOT}/immport_qsub_worklist.tsv}"
IMMPORT_INPUTS_ROOT="${IMMPORT_INPUTS_ROOT:-}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
QSUB_BIN="${QSUB_BIN:-qsub}"
APPTAINER_BIN="${APPTAINER_BIN:-apptainer}"
APPTAINER_IMAGE="${APPTAINER_IMAGE:-}"
APPTAINER_EXTRA_ARGS="${APPTAINER_EXTRA_ARGS:-}"
APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}"

if [[ -n "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
  PYTHON_BIN="${APPTAINER_PYTHON_BIN}"
  PYTHON_BIN="$(command -v "${PYTHON_BIN}")"
fi

IMMPORT_ARRAY_MEMORY="${IMMPORT_ARRAY_MEMORY:-16G}"
IMMPORT_ARRAY_WALLTIME="${IMMPORT_ARRAY_WALLTIME:-24:00:00}"
SUBMIT_MODE="${SUBMIT_MODE:-0}"
WRITE_MODEL_ONLY="${WRITE_MODEL_ONLY:-0}"
REFRESH_METADATA_AND_PROVENANCE="${REFRESH_METADATA_AND_PROVENANCE:-0}"
DESCRIPTION_TEMPLATE_TSV="${DESCRIPTION_TEMPLATE_TSV:-}"
PROVENANCE_MIRROR_LOCAL_PREFIX="${PROVENANCE_MIRROR_LOCAL_PREFIX:-}"
PROVENANCE_MIRROR_REMOTE_PREFIX="${PROVENANCE_MIRROR_REMOTE_PREFIX:-}"
LOCAL_INPUT_SOURCE_MAP_TSV="${LOCAL_INPUT_SOURCE_MAP_TSV:-}"
FILTER_MODEL_IDS=""
FILTER_STUDY_IDS=""

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_immport_models_cluster_apptainer.sh --submit [--write_model_only|--refresh_metadata_and_provenance] [--study_id STUDY[,STUDY...]] [--model_id MODEL[,MODEL...]]
  ./geneset-extractor-dev/run/submit_immport_models_cluster_apptainer.sh --help

Required environment variables:
  APPTAINER_IMAGE
  IMMPORT_INPUTS_ROOT          (root holding per-study input subdirs: <root>/<study_id>/<expression_object>)

Optional environment variables:
  WORK_ROOT
  DIG_DIR, PYTHON_BIN, QSUB_BIN
  APPTAINER_BIN, APPTAINER_EXTRA_ARGS, APPTAINER_PYTHON_BIN
  IMMPORT_OUT_ROOT, QSUB_LOG_ROOT, IMMPORT_WORKLIST, IMMPORT_STUDY_LIST
  IMMPORT_ARRAY_MEMORY, IMMPORT_ARRAY_WALLTIME
  DESCRIPTION_TEMPLATE_TSV
  PROVENANCE_MIRROR_LOCAL_PREFIX, PROVENANCE_MIRROR_REMOTE_PREFIX
  LOCAL_INPUT_SOURCE_MAP_TSV
EOF
}

require_var() { [[ -n "${!1:-}" ]] || { echo "Missing required environment variable: $1" >&2; exit 1; }; }
require_file() { [[ -f "$1" ]] || { echo "Missing required file: $1" >&2; exit 1; }; }
require_dir() { [[ -d "$1" ]] || { echo "Missing required directory: $1" >&2; exit 1; }; }

absolute_path() {
  local path="$1"
  if [[ "${path}" == /* ]]; then printf '%s\n' "${path}"; else printf '%s/%s\n' "$(pwd)" "${path}"; fi
}

parse_cli() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --submit) SUBMIT_MODE=1; shift ;;
      --write_model_only) WRITE_MODEL_ONLY=1; shift ;;
      --refresh_metadata_and_provenance) REFRESH_METADATA_AND_PROVENANCE=1; shift ;;
      --model_id)
        [[ $# -ge 2 ]] || { echo "Missing value for --model_id" >&2; exit 1; }
        FILTER_MODEL_IDS="$2"; shift 2 ;;
      --study_id)
        [[ $# -ge 2 ]] || { echo "Missing value for --study_id" >&2; exit 1; }
        FILTER_STUDY_IDS="$2"; shift 2 ;;
      -h|--help|help) usage; exit 0 ;;
      *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
  done

  if [[ ${WRITE_MODEL_ONLY} -eq 1 && ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    echo "Use only one of --write_model_only or --refresh_metadata_and_provenance" >&2
    exit 1
  fi
  if [[ ${SUBMIT_MODE} -ne 1 ]]; then usage; exit 1; fi
}

append_bind_path() {
  local path="$1"
  [[ -n "${path}" ]] || return
  if [[ -d "${path}" ]]; then printf '%s\n' "${path}"; elif [[ -e "${path}" ]]; then dirname "${path}"; fi
}

prepare_common() {
  mkdir -p "${WORK_ROOT}" "${QSUB_LOG_ROOT}"
  require_dir "${DIG_DIR}"
  if [[ -z "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
    require_var APPTAINER_IMAGE
    require_file "${APPTAINER_IMAGE}"
  fi
  require_file "${IMMPORT_MODEL_LIST}"
  require_file "${IMMPORT_MODEL_MANIFEST}"
  require_file "${IMMPORT_STUDY_LIST}"
  if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    require_file "${DESCRIPTION_TEMPLATE_TSV}"
  else
    require_var IMMPORT_INPUTS_ROOT
    require_dir "${IMMPORT_INPUTS_ROOT}"
  fi
}

# Emit enabled ids (optionally filtered by a CSV allowlist) from a TSV keyed by key_field.
enabled_ids_from_tsv() {
  local tsv="$1" key_field="$2" filter_csv="$3"
  awk -F $'\t' -v key_field="${key_field}" -v filter_csv="${filter_csv}" '
    NR == 1 {
      for (i = 1; i <= NF; i++) { if ($i == key_field) key_col = i; if ($i == "enabled") en_col = i }
      next
    }
    BEGIN {
      split(filter_csv, req, ",")
      for (r in req) { gsub(/^[[:space:]]+|[[:space:]]+$/, "", req[r]); if (req[r] != "") want[req[r]] = 1 }
    }
    (en_col == 0 || $en_col == "true") {
      id = $key_col
      if (filter_csv != "" && !(id in want)) next
      if (id != "") print id
    }
  ' "${tsv}"
}

write_worklist() {
  {
    printf "task_id\tstudy_id\tmodel_id\n"
    local task_id=0 study_id model_id
    while IFS= read -r study_id; do
      [[ -n "${study_id}" ]] || continue
      while IFS= read -r model_id; do
        [[ -n "${model_id}" ]] || continue
        task_id=$((task_id + 1))
        printf "%d\t%s\t%s\n" "${task_id}" "${study_id}" "${model_id}"
      done < <(enabled_ids_from_tsv "${IMMPORT_MODEL_LIST}" "model_id" "${FILTER_MODEL_IDS}")
    done < <(enabled_ids_from_tsv "${IMMPORT_STUDY_LIST}" "study_id" "${FILTER_STUDY_IDS}")
  } > "${IMMPORT_WORKLIST}"
}

filter_refresh_existing_worklist() {
  [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]] || return 0
  local filtered_worklist kept
  filtered_worklist="$(mktemp)"
  head -n 1 "${IMMPORT_WORKLIST}" > "${filtered_worklist}"
  kept=0
  while IFS= read -r row; do
    [[ -n "${row}" ]] || continue
    local study_id model_id suffix model_dir
    IFS=$'\t' read -r _task_id study_id model_id <<< "${row}"
    suffix="${row#*$'\t'}"
    model_dir="${IMMPORT_OUT_ROOT}/genesets/${study_id}/models/${model_id}"
    if [[ -d "${model_dir}/extractor" ]]; then
      kept=$((kept + 1))
      printf "%d\t%s\n" "${kept}" "${suffix}" >> "${filtered_worklist}"
    fi
  done < <(tail -n +2 "${IMMPORT_WORKLIST}")
  mv "${filtered_worklist}" "${IMMPORT_WORKLIST}"
  if [[ ${kept} -le 0 ]]; then
    echo "No ImmPort refresh tasks selected after excluding missing outputs." >&2
    exit 1
  fi
}

worklist_task_count() { awk 'NR > 1 { n += 1 } END { print n + 0 }' "${IMMPORT_WORKLIST}"; }

task_id_from_env() {
  if [[ -n "${PBS_ARRAYID:-}" ]]; then printf '%s\n' "${PBS_ARRAYID}"; return; fi
  if [[ -n "${SGE_TASK_ID:-}" ]]; then printf '%s\n' "${SGE_TASK_ID}"; return; fi
  return 1
}

run_inner_worker() {
  local task_id study_id model_id
  task_id="$(task_id_from_env)" || { echo "Unable to determine array task id" >&2; exit 1; }
  IFS=$'\t' read -r _task_id study_id model_id < <(awk -F $'\t' -v task_id="${task_id}" 'NR > 1 && $1 == task_id { print $0; exit }' "${IMMPORT_WORKLIST}")
  if [[ -z "${model_id:-}" || -z "${study_id:-}" ]]; then
    echo "No ImmPort worklist row found for task_id=${task_id}" >&2
    exit 1
  fi

  local src_root="${REPO_ROOT}/geneset-extractor-dev/ImmPort/src"
  local cmd
  if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    cmd=(
      bash "${REPO_ROOT}/geneset-extractor-dev/run/refresh_model_metadata_and_provenance.sh"
      --model_id "${model_id}"
      --model_dir "${IMMPORT_OUT_ROOT}/genesets/${study_id}/models/${model_id}"
      --description_template_tsv "${DESCRIPTION_TEMPLATE_TSV}"
      --python_bin "${PYTHON_BIN}"
    )
  else
    cmd=(
      "${PYTHON_BIN}"
      "${src_root}/build_immport_genesets.py"
      "--models" "${model_id}"
      "--studies" "${study_id}"
      "--python_bin" "${PYTHON_BIN}"
      "--inputs_root" "${IMMPORT_INPUTS_ROOT}"
      "--dig_dir" "${DIG_DIR}"
      "--model_list" "${IMMPORT_MODEL_LIST}"
      "--model_manifest" "${IMMPORT_MODEL_MANIFEST}"
      "--study_list" "${IMMPORT_STUDY_LIST}"
      "--out_root" "${IMMPORT_OUT_ROOT}"
      "--overwrite"
    )
  fi
  if [[ -n "${PROVENANCE_MIRROR_LOCAL_PREFIX:-}" ]]; then cmd+=(--provenance_mirror_local_prefix "${PROVENANCE_MIRROR_LOCAL_PREFIX}"); fi
  if [[ -n "${PROVENANCE_MIRROR_REMOTE_PREFIX:-}" ]]; then cmd+=(--provenance_mirror_remote_prefix "${PROVENANCE_MIRROR_REMOTE_PREFIX}"); fi
  if [[ -n "${LOCAL_INPUT_SOURCE_MAP_TSV:-}" ]]; then cmd+=(--local_input_source_map_tsv "${LOCAL_INPUT_SOURCE_MAP_TSV}"); fi
  printf '$'; printf ' %q' "${cmd[@]}"; printf '\n'
  "${cmd[@]}"
}

run_outer_worker() {
  local binds bind_csv
  binds="$(
    {
      append_bind_path "${REPO_ROOT}"
      append_bind_path "${WORK_ROOT}"
      append_bind_path "${DIG_DIR}"
      append_bind_path "${IMMPORT_MODEL_LIST}"
      append_bind_path "${IMMPORT_MODEL_MANIFEST}"
      append_bind_path "${IMMPORT_STUDY_LIST}"
      append_bind_path "${IMMPORT_INPUTS_ROOT:-}"
      append_bind_path "${DESCRIPTION_TEMPLATE_TSV:-}"
      append_bind_path "${PROVENANCE_MIRROR_LOCAL_PREFIX:-}"
      append_bind_path "${LOCAL_INPUT_SOURCE_MAP_TSV:-}"
    } | sort -u
  )"
  bind_csv="$(printf '%s\n' "${binds}" | paste -sd, -)"

  env \
    APPTAINERENV_GENESET_EXTRACTORS_IN_APPTAINER=1 \
    APPTAINERENV_PBS_ARRAYID="${PBS_ARRAYID:-}" \
    APPTAINERENV_SGE_TASK_ID="${SGE_TASK_ID:-}" \
    APPTAINERENV_REPO_ROOT="${REPO_ROOT}" \
    APPTAINERENV_WORK_ROOT="${WORK_ROOT}" \
    APPTAINERENV_IMMPORT_WORKLIST="${IMMPORT_WORKLIST}" \
    APPTAINERENV_IMMPORT_OUT_ROOT="${IMMPORT_OUT_ROOT}" \
    APPTAINERENV_IMMPORT_MODEL_LIST="${IMMPORT_MODEL_LIST}" \
    APPTAINERENV_IMMPORT_MODEL_MANIFEST="${IMMPORT_MODEL_MANIFEST}" \
    APPTAINERENV_IMMPORT_STUDY_LIST="${IMMPORT_STUDY_LIST}" \
    APPTAINERENV_IMMPORT_INPUTS_ROOT="${IMMPORT_INPUTS_ROOT}" \
    APPTAINERENV_DIG_DIR="${DIG_DIR}" \
    APPTAINERENV_PYTHON_BIN="${PYTHON_BIN}" \
    APPTAINERENV_APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN}" \
    APPTAINERENV_WRITE_MODEL_ONLY="${WRITE_MODEL_ONLY}" \
    APPTAINERENV_REFRESH_METADATA_AND_PROVENANCE="${REFRESH_METADATA_AND_PROVENANCE}" \
    APPTAINERENV_DESCRIPTION_TEMPLATE_TSV="${DESCRIPTION_TEMPLATE_TSV}" \
    APPTAINERENV_PROVENANCE_MIRROR_LOCAL_PREFIX="${PROVENANCE_MIRROR_LOCAL_PREFIX}" \
    APPTAINERENV_PROVENANCE_MIRROR_REMOTE_PREFIX="${PROVENANCE_MIRROR_REMOTE_PREFIX}" \
    APPTAINERENV_LOCAL_INPUT_SOURCE_MAP_TSV="${LOCAL_INPUT_SOURCE_MAP_TSV}" \
    "${APPTAINER_BIN}" exec \
      --bind "${bind_csv}" \
      ${APPTAINER_EXTRA_ARGS} \
      "${APPTAINER_IMAGE}" \
      bash "${SELF_PATH}"
}

submit_array() {
  write_worklist
  filter_refresh_existing_worklist
  local task_count
  task_count="$(worklist_task_count)"
  if [[ "${task_count}" -le 0 ]]; then
    echo "No ImmPort tasks selected." >&2
    exit 1
  fi

  "${QSUB_BIN}" \
    -N "immport_all_models_apptainer" \
    -t "1-${task_count}" \
    -o "${QSUB_LOG_ROOT}/immport.\$TASK_ID.out" \
    -e "${QSUB_LOG_ROOT}/immport.\$TASK_ID.err" \
    -l "h_vmem=${IMMPORT_ARRAY_MEMORY},h_rt=${IMMPORT_ARRAY_WALLTIME}" \
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},IMMPORT_WORKLIST=${IMMPORT_WORKLIST},IMMPORT_OUT_ROOT=${IMMPORT_OUT_ROOT},IMMPORT_MODEL_LIST=${IMMPORT_MODEL_LIST},IMMPORT_MODEL_MANIFEST=${IMMPORT_MODEL_MANIFEST},IMMPORT_STUDY_LIST=${IMMPORT_STUDY_LIST},IMMPORT_INPUTS_ROOT=${IMMPORT_INPUTS_ROOT},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},APPTAINER_BIN=${APPTAINER_BIN},APPTAINER_IMAGE=${APPTAINER_IMAGE},APPTAINER_EXTRA_ARGS=${APPTAINER_EXTRA_ARGS},APPTAINER_PYTHON_BIN=${APPTAINER_PYTHON_BIN},WRITE_MODEL_ONLY=${WRITE_MODEL_ONLY},REFRESH_METADATA_AND_PROVENANCE=${REFRESH_METADATA_AND_PROVENANCE},DESCRIPTION_TEMPLATE_TSV=${DESCRIPTION_TEMPLATE_TSV},PROVENANCE_MIRROR_LOCAL_PREFIX=${PROVENANCE_MIRROR_LOCAL_PREFIX},PROVENANCE_MIRROR_REMOTE_PREFIX=${PROVENANCE_MIRROR_REMOTE_PREFIX},LOCAL_INPUT_SOURCE_MAP_TSV=${LOCAL_INPUT_SOURCE_MAP_TSV}" \
    "${SELF_PATH}"
}

main() {
  WORK_ROOT="$(absolute_path "${WORK_ROOT}")"
  IMMPORT_OUT_ROOT="$(absolute_path "${IMMPORT_OUT_ROOT}")"
  QSUB_LOG_ROOT="$(absolute_path "${QSUB_LOG_ROOT}")"
  IMMPORT_WORKLIST="$(absolute_path "${IMMPORT_WORKLIST}")"

  if [[ $# -eq 0 ]] && [[ -n "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
    prepare_common
    run_inner_worker
  elif [[ $# -eq 0 ]] && task_id_from_env >/dev/null 2>&1; then
    prepare_common
    run_outer_worker
  else
    parse_cli "$@"
    prepare_common
    submit_array
  fi
}

main "$@"
