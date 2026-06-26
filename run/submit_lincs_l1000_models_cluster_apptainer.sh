#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPO_ROOT="${REPO_ROOT:-${DEFAULT_REPO_ROOT}}"
SELF_PATH="${REPO_ROOT}/geneset-extractor-dev/run/submit_lincs_l1000_models_cluster_apptainer.sh"
WORK_ROOT="${WORK_ROOT:-$(pwd)}"

LINCS_CONFIG_ROOT="${LINCS_CONFIG_ROOT:-${REPO_ROOT}/geneset-extractor-dev/LINCS_L1000/config}"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"

LINCS_MODEL_LIST="${LINCS_MODEL_LIST:-${LINCS_CONFIG_ROOT}/model_list.tsv}"
LINCS_MODEL_MANIFEST="${LINCS_MODEL_MANIFEST:-${LINCS_CONFIG_ROOT}/model_manifest.tsv}"

LINCS_OUT_ROOT="${LINCS_OUT_ROOT:-${WORK_ROOT}/lincs_l1000_all_models}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_lincs_l1000}"
LINCS_WORKLIST="${LINCS_WORKLIST:-${WORK_ROOT}/lincs_l1000_qsub_worklist.tsv}"

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

LINCS_ARRAY_MEMORY="${LINCS_ARRAY_MEMORY:-16G}"
LINCS_ARRAY_WALLTIME="${LINCS_ARRAY_WALLTIME:-24:00:00}"
SUBMIT_MODE=0
WRITE_MODEL_ONLY=0
REFRESH_METADATA_AND_PROVENANCE=0
DESCRIPTION_TEMPLATE_TSV="${DESCRIPTION_TEMPLATE_TSV:-}"
FILTER_MODEL_GROUP=""
FILTER_MODEL_IDS=""

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_lincs_l1000_models_cluster_apptainer.sh --submit [--write_model_only|--refresh_metadata_and_provenance] [--model_group HZ] [--model_id MODEL[,MODEL...]]
  ./geneset-extractor-dev/run/submit_lincs_l1000_models_cluster_apptainer.sh --help

Required environment variables:
  APPTAINER_IMAGE
  LINCS_CHEMPERT_EXPRESSION_TSV
  LINCS_CRISPRKO_EXPRESSION_TSV
  LINCS_MAPPING_FILE

Optional environment variables:
  WORK_ROOT
  DIG_DIR, PYTHON_BIN, QSUB_BIN
  APPTAINER_BIN, APPTAINER_EXTRA_ARGS
  APPTAINER_PYTHON_BIN
  LINCS_OUT_ROOT, QSUB_LOG_ROOT, LINCS_WORKLIST
  LINCS_ARRAY_MEMORY, LINCS_ARRAY_WALLTIME
  DESCRIPTION_TEMPLATE_TSV
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

validate_model_ids() {
  local model_csv="$1"
  local requested_model_id
  IFS=',' read -r -a requested_model_ids <<< "${model_csv}"
  for requested_model_id in "${requested_model_ids[@]}"; do
    requested_model_id="${requested_model_id//[[:space:]]/}"
    [[ -n "${requested_model_id}" ]] || continue
    local derived_group
    derived_group="$(resolve_model_group_for_id "${requested_model_id}")"
    if [[ -z "${derived_group}" ]]; then
      echo "Model not found in LINCS_L1000 model list: ${requested_model_id}" >&2
      exit 1
    fi
    if [[ -n "${FILTER_MODEL_GROUP}" && "${FILTER_MODEL_GROUP}" != "${derived_group}" ]]; then
      echo "--model_id ${requested_model_id} conflicts with --model_group ${FILTER_MODEL_GROUP}" >&2
      exit 1
    fi
  done
}

parse_cli() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --submit)
        SUBMIT_MODE=1
        shift
        ;;
      --write_model_only)
        WRITE_MODEL_ONLY=1
        shift
        ;;
      --refresh_metadata_and_provenance)
        REFRESH_METADATA_AND_PROVENANCE=1
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
        FILTER_MODEL_IDS="$2"
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

  if [[ ${WRITE_MODEL_ONLY} -eq 1 && ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    echo "Use only one of --write_model_only or --refresh_metadata_and_provenance" >&2
    exit 1
  fi

  if [[ -n "${FILTER_MODEL_IDS}" ]]; then
    validate_model_ids "${FILTER_MODEL_IDS}"
  fi

  if [[ ${SUBMIT_MODE} -ne 1 ]]; then
    usage
    exit 1
  fi
}

expression_tsv_for_model() {
  local model_id="$1"
  case "${model_id}" in
    HZ1) printf '%s\n' "${LINCS_CHEMPERT_EXPRESSION_TSV}" ;;
    HZ2) printf '%s\n' "${LINCS_CRISPRKO_EXPRESSION_TSV}" ;;
    *) return 1 ;;
  esac
}

append_bind_path() {
  local path="$1"
  if [[ -z "${path}" ]]; then
    return
  fi
  if [[ -d "${path}" ]]; then
    printf '%s\n' "${path}"
  elif [[ -e "${path}" ]]; then
    dirname "${path}"
  fi
}

prepare_common() {
  mkdir -p "${WORK_ROOT}" "${QSUB_LOG_ROOT}"
  require_dir "${DIG_DIR}"

  if [[ -z "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
    require_var APPTAINER_IMAGE
    require_file "${APPTAINER_IMAGE}"
  fi
  require_file "${LINCS_MODEL_LIST}"
  require_file "${LINCS_MODEL_MANIFEST}"
  if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    require_file "${DESCRIPTION_TEMPLATE_TSV}"
  else
    require_var LINCS_CHEMPERT_EXPRESSION_TSV
    require_var LINCS_CRISPRKO_EXPRESSION_TSV
    require_var LINCS_MAPPING_FILE
    require_file "${LINCS_CHEMPERT_EXPRESSION_TSV}"
    require_file "${LINCS_CRISPRKO_EXPRESSION_TSV}"
    require_file "${LINCS_MAPPING_FILE}"
  fi
}

write_worklist() {
  {
    printf "task_id\tmodel_group\tmodel_id\n"
    awk -F $'\t' \
      -v filter_group="${FILTER_MODEL_GROUP}" \
      -v filter_models="${FILTER_MODEL_IDS}" '
      NR == 1 {
        for (i = 1; i <= NF; i++) {
          if ($i == "model_id") model_id_col = i
          if ($i == "model_family") family_col = i
          if ($i == "enabled") enabled_col = i
        }
        next
      }
      BEGIN {
        split(filter_models, requested_models, ",")
        for (requested_index in requested_models) {
          requested_model = requested_models[requested_index]
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", requested_model)
          if (requested_model != "") {
            requested_model_lookup[requested_model] = 1
          }
        }
      }
      $enabled_col == "true" {
        group = ""
        if ($family_col == "hz_released_matrix") group = "HZ"
        if (group == "") next
        if (filter_group != "" && group != filter_group) next
        if (filter_models != "" && !($model_id_col in requested_model_lookup)) next
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

run_inner_worker() {
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
  local cmd expression_tsv
  if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    cmd=(
      bash "${REPO_ROOT}/geneset-extractor-dev/run/refresh_model_metadata_and_provenance.sh"
      --model_id "${model_id}"
      --model_dir "${LINCS_OUT_ROOT}/genesets/all_signatures/models/${model_id}"
      --description_template_tsv "${DESCRIPTION_TEMPLATE_TSV}"
      --python_bin "${PYTHON_BIN}"
    )
  elif [[ ${WRITE_MODEL_ONLY} -eq 1 ]]; then
    expression_tsv="$(expression_tsv_for_model "${model_id}")" || {
      echo "Unsupported LINCS_L1000 model for model-only mode: ${model_id}" >&2
      exit 1
    }
    cmd=(
      "${PYTHON_BIN}"
      "${src_root}/run_lincs_l1000_hz_model.py"
      "--model_id" "${model_id}"
      "--run_root" "${LINCS_OUT_ROOT}/genesets/all_signatures/models"
      "--python_bin" "${PYTHON_BIN}"
      "--dig_dir" "${DIG_DIR}"
      "--expression_tsv" "${expression_tsv}"
      "--mapping_file" "${LINCS_MAPPING_FILE}"
      "--model_manifest" "${LINCS_MODEL_MANIFEST}"
      "--write_model_only"
    )
  else
    cmd=(
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
  fi
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

run_outer_worker() {
  local binds bind_csv
  binds="$(
    {
      append_bind_path "${REPO_ROOT}"
      append_bind_path "${WORK_ROOT}"
      append_bind_path "${DIG_DIR}"
      append_bind_path "${LINCS_MODEL_LIST}"
      append_bind_path "${LINCS_MODEL_MANIFEST}"
      append_bind_path "${DESCRIPTION_TEMPLATE_TSV:-}"
      append_bind_path "${LINCS_CHEMPERT_EXPRESSION_TSV}"
      append_bind_path "${LINCS_CRISPRKO_EXPRESSION_TSV}"
      append_bind_path "${LINCS_MAPPING_FILE}"
    } | sort -u
  )"
  bind_csv="$(printf '%s\n' "${binds}" | paste -sd, -)"

  env \
    APPTAINERENV_GENESET_EXTRACTORS_IN_APPTAINER=1 \
    APPTAINERENV_PBS_ARRAYID="${PBS_ARRAYID:-}" \
    APPTAINERENV_SGE_TASK_ID="${SGE_TASK_ID:-}" \
    APPTAINERENV_REPO_ROOT="${REPO_ROOT}" \
    APPTAINERENV_WORK_ROOT="${WORK_ROOT}" \
    APPTAINERENV_LINCS_WORKLIST="${LINCS_WORKLIST}" \
    APPTAINERENV_LINCS_OUT_ROOT="${LINCS_OUT_ROOT}" \
    APPTAINERENV_LINCS_MODEL_LIST="${LINCS_MODEL_LIST}" \
    APPTAINERENV_LINCS_MODEL_MANIFEST="${LINCS_MODEL_MANIFEST}" \
    APPTAINERENV_DIG_DIR="${DIG_DIR}" \
    APPTAINERENV_PYTHON_BIN="${PYTHON_BIN}" \
    APPTAINERENV_APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN}" \
    APPTAINERENV_WRITE_MODEL_ONLY="${WRITE_MODEL_ONLY}" \
    APPTAINERENV_REFRESH_METADATA_AND_PROVENANCE="${REFRESH_METADATA_AND_PROVENANCE}" \
    APPTAINERENV_DESCRIPTION_TEMPLATE_TSV="${DESCRIPTION_TEMPLATE_TSV}" \
    APPTAINERENV_LINCS_CHEMPERT_EXPRESSION_TSV="${LINCS_CHEMPERT_EXPRESSION_TSV}" \
    APPTAINERENV_LINCS_CRISPRKO_EXPRESSION_TSV="${LINCS_CRISPRKO_EXPRESSION_TSV}" \
    APPTAINERENV_LINCS_MAPPING_FILE="${LINCS_MAPPING_FILE}" \
    "${APPTAINER_BIN}" exec \
      --bind "${bind_csv}" \
      ${APPTAINER_EXTRA_ARGS} \
      "${APPTAINER_IMAGE}" \
      bash "${SELF_PATH}"
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
    -N "lincs_l1000_all_models_apptainer" \
    -t "1-${task_count}" \
    -o "${QSUB_LOG_ROOT}/lincs_l1000.\$TASK_ID.out" \
    -e "${QSUB_LOG_ROOT}/lincs_l1000.\$TASK_ID.err" \
    -l "h_vmem=${LINCS_ARRAY_MEMORY},h_rt=${LINCS_ARRAY_WALLTIME}" \
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},LINCS_WORKLIST=${LINCS_WORKLIST},LINCS_OUT_ROOT=${LINCS_OUT_ROOT},LINCS_MODEL_LIST=${LINCS_MODEL_LIST},LINCS_MODEL_MANIFEST=${LINCS_MODEL_MANIFEST},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},APPTAINER_BIN=${APPTAINER_BIN},APPTAINER_IMAGE=${APPTAINER_IMAGE},APPTAINER_EXTRA_ARGS=${APPTAINER_EXTRA_ARGS},APPTAINER_PYTHON_BIN=${APPTAINER_PYTHON_BIN},WRITE_MODEL_ONLY=${WRITE_MODEL_ONLY},REFRESH_METADATA_AND_PROVENANCE=${REFRESH_METADATA_AND_PROVENANCE},DESCRIPTION_TEMPLATE_TSV=${DESCRIPTION_TEMPLATE_TSV},LINCS_CHEMPERT_EXPRESSION_TSV=${LINCS_CHEMPERT_EXPRESSION_TSV},LINCS_CRISPRKO_EXPRESSION_TSV=${LINCS_CRISPRKO_EXPRESSION_TSV},LINCS_MAPPING_FILE=${LINCS_MAPPING_FILE}" \
    "${SELF_PATH}"
}

main() {
  if [[ -n "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
    prepare_common
    run_inner_worker
  elif task_id_from_env >/dev/null 2>&1; then
    prepare_common
    run_outer_worker
  else
    parse_cli "$@"
    prepare_common
    submit_array
  fi
}

main "$@"
