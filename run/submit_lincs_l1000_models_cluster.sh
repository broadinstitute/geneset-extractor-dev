#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORK_ROOT="${WORK_ROOT:-$(pwd)}"

LINCS_CONFIG_ROOT="${LINCS_CONFIG_ROOT:-${REPO_ROOT}/geneset-extractor-dev/LINCS_L1000/planning}"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"

LINCS_MODEL_LIST="${LINCS_MODEL_LIST:-${LINCS_CONFIG_ROOT}/model_list.tsv}"
LINCS_MODEL_MANIFEST="${LINCS_MODEL_MANIFEST:-${LINCS_CONFIG_ROOT}/model_manifest.tsv}"

LINCS_OUT_ROOT="${LINCS_OUT_ROOT:-${WORK_ROOT}/lincs_l1000_all_models}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_lincs_l1000}"
LINCS_WORKLIST="${LINCS_WORKLIST:-${WORK_ROOT}/lincs_l1000_qsub_worklist.tsv}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
QSUB_BIN="${QSUB_BIN:-qsub}"

LINCS_ARRAY_MEMORY="${LINCS_ARRAY_MEMORY:-16G}"
LINCS_ARRAY_WALLTIME="${LINCS_ARRAY_WALLTIME:-24:00:00}"
SUBMIT_MODE=0
FILTER_MODEL_GROUP=""
FILTER_MODEL_ID=""

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_lincs_l1000_models_cluster.sh --submit [--model_group HZ] [--model_id MODEL]
  ./geneset-extractor-dev/run/submit_lincs_l1000_models_cluster.sh --help

Required environment variables:
  LINCS_CHEMPERT_EXPRESSION_TSV
  LINCS_CRISPRKO_EXPRESSION_TSV
  LINCS_MAPPING_FILE

Optional environment variables:
  WORK_ROOT
  DIG_DIR, PYTHON_BIN, QSUB_BIN
  LINCS_OUT_ROOT, QSUB_LOG_ROOT, LINCS_WORKLIST
  LINCS_ARRAY_MEMORY, LINCS_ARRAY_WALLTIME

Notes:
  - Use --submit to submit the qsub array.
  - When run inside a qsub array task, it auto-detects the task context and
    runs the assigned workload row.
  - No filters: one array covering all enabled LINCS_L1000 models.
  - --model_group currently supports only HZ.
  - --model_id submits a single-task array for that model.
EOF
}

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 1
  fi
}

require_file() {
  local path="$1"
  if [[ ! -f "${path}" ]]; then
    echo "Missing required file: ${path}" >&2
    exit 1
  fi
}

require_dir() {
  local path="$1"
  if [[ ! -d "${path}" ]]; then
    echo "Missing required directory: ${path}" >&2
    exit 1
  fi
}

canonicalize_model_group() {
  case "$1" in
    HZ|hz_released_matrix) printf '%s\n' "HZ" ;;
    *) return 1 ;;
  esac
}

resolve_model_group_for_id() {
  local model_id="$1"
  awk -F $'\t' -v model_id="${model_id}" '
    NR == 1 {
      for (i = 1; i <= NF; i++) {
        if ($i == "model_id") model_id_col = i
        if ($i == "model_family") family_col = i
      }
      next
    }
    $model_id_col == model_id {
      if ($family_col == "hz_released_matrix") print "HZ"
      exit
    }
  ' "${LINCS_MODEL_LIST}"
}

parse_cli() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --submit)
        SUBMIT_MODE=1
        shift
        ;;
      --model_group)
        [[ $# -ge 2 ]] || { echo "Missing value for --model_group" >&2; exit 1; }
        FILTER_MODEL_GROUP="$(canonicalize_model_group "$2")" || {
          echo "Unsupported LINCS_L1000 model group: $2" >&2
          exit 1
        }
        shift 2
        ;;
      --model_id)
        [[ $# -ge 2 ]] || { echo "Missing value for --model_id" >&2; exit 1; }
        FILTER_MODEL_ID="$2"
        shift 2
        ;;
      -h|--help|help)
        usage
        exit 0
        ;;
      *)
        echo "Unknown argument: $1" >&2
        usage >&2
        exit 1
        ;;
    esac
  done

  if [[ -n "${FILTER_MODEL_ID}" ]]; then
    local derived_group
    derived_group="$(resolve_model_group_for_id "${FILTER_MODEL_ID}")"
    if [[ -z "${derived_group}" ]]; then
      echo "Model not found in LINCS_L1000 model list: ${FILTER_MODEL_ID}" >&2
      exit 1
    fi
    if [[ -n "${FILTER_MODEL_GROUP}" && "${FILTER_MODEL_GROUP}" != "${derived_group}" ]]; then
      echo "--model_id ${FILTER_MODEL_ID} conflicts with --model_group ${FILTER_MODEL_GROUP}" >&2
      exit 1
    fi
    FILTER_MODEL_GROUP="${derived_group}"
  fi

  if [[ ${SUBMIT_MODE} -ne 1 ]]; then
    usage
    exit 1
  fi
}

prepare_common() {
  mkdir -p "${WORK_ROOT}" "${QSUB_LOG_ROOT}"
  require_dir "${DIG_DIR}"

  require_var LINCS_CHEMPERT_EXPRESSION_TSV
  require_var LINCS_CRISPRKO_EXPRESSION_TSV
  require_var LINCS_MAPPING_FILE

  require_file "${LINCS_MODEL_LIST}"
  require_file "${LINCS_MODEL_MANIFEST}"
  require_file "${LINCS_CHEMPERT_EXPRESSION_TSV}"
  require_file "${LINCS_CRISPRKO_EXPRESSION_TSV}"
  require_file "${LINCS_MAPPING_FILE}"
}

write_worklist() {
  {
    printf "task_id\tmodel_group\tmodel_id\n"
    awk -F $'\t' \
      -v filter_group="${FILTER_MODEL_GROUP}" \
      -v filter_model="${FILTER_MODEL_ID}" '
      NR == 1 {
        for (i = 1; i <= NF; i++) {
          if ($i == "model_id") model_id_col = i
          if ($i == "model_family") family_col = i
          if ($i == "enabled") enabled_col = i
        }
        next
      }
      $enabled_col == "true" {
        group = ""
        if ($family_col == "hz_released_matrix") group = "HZ"
        if (group == "") next
        if (filter_group != "" && group != filter_group) next
        if (filter_model != "" && $model_id_col != filter_model) next
        task_id += 1
        printf "%d\t%s\t%s\n", task_id, group, $model_id_col
      }
    ' "${LINCS_MODEL_LIST}"
  } > "${LINCS_WORKLIST}"
}

worklist_task_count() {
  awk 'NR > 1 { n += 1 } END { print n + 0 }' "${LINCS_WORKLIST}"
}

task_id_from_env() {
  if [[ -n "${PBS_ARRAYID:-}" ]]; then
    printf '%s\n' "${PBS_ARRAYID}"
    return
  fi
  if [[ -n "${SGE_TASK_ID:-}" ]]; then
    printf '%s\n' "${SGE_TASK_ID}"
    return
  fi
  return 1
}

run_worker() {
  local task_id model_group model_id
  task_id="$(task_id_from_env)" || {
    echo "Unable to determine array task id from PBS_ARRAYID or SGE_TASK_ID" >&2
    exit 1
  }

  IFS=$'\t' read -r _task_id model_group model_id < <(awk -F $'\t' -v task_id="${task_id}" 'NR > 1 && $1 == task_id { print $0; exit }' "${LINCS_WORKLIST}")
  if [[ -z "${model_id:-}" ]]; then
    echo "No LINCS_L1000 worklist row found for task_id=${task_id}" >&2
    exit 1
  fi

  local src_root
  src_root="${REPO_ROOT}/geneset-extractor-dev/LINCS_L1000/src"

  local cmd=(
    "${PYTHON_BIN}"
    "${src_root}/build_lincs_l1000_genesets.py"
    "--models" "${model_id}"
    "--python_bin" "${PYTHON_BIN}"
    "--mapping_file" "${LINCS_MAPPING_FILE}"
    "--dig_dir" "${DIG_DIR}"
    "--model_list" "${LINCS_MODEL_LIST}"
    "--model_manifest" "${LINCS_MODEL_MANIFEST}"
    "--out_root" "${LINCS_OUT_ROOT}"
    "--overwrite"
    "--chempert_expression_tsv" "${LINCS_CHEMPERT_EXPRESSION_TSV}"
    "--crisprko_expression_tsv" "${LINCS_CRISPRKO_EXPRESSION_TSV}"
  )
  if [[ -n "${PROVENANCE_MIRROR_LOCAL_PREFIX:-}" ]]; then
    cmd+=(--provenance_mirror_local_prefix "${PROVENANCE_MIRROR_LOCAL_PREFIX}")
  fi
  if [[ -n "${PROVENANCE_MIRROR_REMOTE_PREFIX:-}" ]]; then
    cmd+=(--provenance_mirror_remote_prefix "${PROVENANCE_MIRROR_REMOTE_PREFIX}")
  fi
  printf '$'
  printf ' %q' "${cmd[@]}"
  printf '\n'
  "${cmd[@]}"
}

submit_array() {
  write_worklist
  local task_count
  task_count="$(worklist_task_count)"
  if [[ "${task_count}" -le 0 ]]; then
    echo "No LINCS_L1000 tasks selected." >&2
    exit 1
  fi

  "${QSUB_BIN}" \
    -N "lincs_l1000_all_models" \
    -t "1-${task_count}" \
    -o "${QSUB_LOG_ROOT}/lincs_l1000.\$TASK_ID.out" \
    -e "${QSUB_LOG_ROOT}/lincs_l1000.\$TASK_ID.err" \
    -l "h_vmem=${LINCS_ARRAY_MEMORY},h_rt=${LINCS_ARRAY_WALLTIME}" \
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},LINCS_WORKLIST=${LINCS_WORKLIST},LINCS_OUT_ROOT=${LINCS_OUT_ROOT},LINCS_MODEL_LIST=${LINCS_MODEL_LIST},LINCS_MODEL_MANIFEST=${LINCS_MODEL_MANIFEST},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},LINCS_CHEMPERT_EXPRESSION_TSV=${LINCS_CHEMPERT_EXPRESSION_TSV},LINCS_CRISPRKO_EXPRESSION_TSV=${LINCS_CRISPRKO_EXPRESSION_TSV},LINCS_MAPPING_FILE=${LINCS_MAPPING_FILE}" \
    "${REPO_ROOT}/geneset-extractor-dev/run/submit_lincs_l1000_models_cluster.sh"
}

main() {
  parse_cli "$@"
  prepare_common
  if task_id_from_env >/dev/null 2>&1; then
    run_worker
  else
    submit_array
  fi
}

main "$@"
