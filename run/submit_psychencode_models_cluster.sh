#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORK_ROOT="${WORK_ROOT:-$(pwd)}"

PSYCHENCODE_CONFIG_ROOT="${PSYCHENCODE_CONFIG_ROOT:-${REPO_ROOT}/geneset-extractor-dev/PsychENCODE/config}"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"

PSYCHENCODE_MODEL_LIST="${PSYCHENCODE_MODEL_LIST:-${PSYCHENCODE_CONFIG_ROOT}/model_list.tsv}"
PSYCHENCODE_MODEL_MANIFEST="${PSYCHENCODE_MODEL_MANIFEST:-${PSYCHENCODE_CONFIG_ROOT}/model_manifest.tsv}"

PSYCHENCODE_OUT_ROOT="${PSYCHENCODE_OUT_ROOT:-${WORK_ROOT}/psychencode_all_models}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_psychencode}"
PSYCHENCODE_WORKLIST="${PSYCHENCODE_WORKLIST:-${WORK_ROOT}/psychencode_qsub_worklist.tsv}"
PSYCHENCODE_DEX_CSV="${PSYCHENCODE_DEX_CSV:-}"
PSYCHENCODE_MODULES_CSV="${PSYCHENCODE_MODULES_CSV:-}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
QSUB_BIN="${QSUB_BIN:-qsub}"

PSYCHENCODE_ARRAY_MEMORY="${PSYCHENCODE_ARRAY_MEMORY:-16G}"
PSYCHENCODE_ARRAY_WALLTIME="${PSYCHENCODE_ARRAY_WALLTIME:-24:00:00}"
SUBMIT_MODE="${SUBMIT_MODE:-0}"
WRITE_MODEL_ONLY="${WRITE_MODEL_ONLY:-0}"
REFRESH_METADATA_AND_PROVENANCE="${REFRESH_METADATA_AND_PROVENANCE:-0}"
DESCRIPTION_TEMPLATE_TSV="${DESCRIPTION_TEMPLATE_TSV:-}"
PROVENANCE_MIRROR_LOCAL_PREFIX="${PROVENANCE_MIRROR_LOCAL_PREFIX:-}"
PROVENANCE_MIRROR_REMOTE_PREFIX="${PROVENANCE_MIRROR_REMOTE_PREFIX:-}"
LOCAL_INPUT_SOURCE_MAP_TSV="${LOCAL_INPUT_SOURCE_MAP_TSV:-}"
FILTER_MODEL_GROUP=""
FILTER_MODEL_IDS=""

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_psychencode_models_cluster.sh --submit [--write_model_only|--refresh_metadata_and_provenance] [--model_group HZ] [--model_id MODEL[,MODEL...]]
  ./geneset-extractor-dev/run/submit_psychencode_models_cluster.sh --help

Required environment variables:
  PSYCHENCODE_DEX_CSV       (released DER-13 Disorder DEX genes CSV, model HZ1)
  PSYCHENCODE_MODULES_CSV   (released DER-16 gene co-expression modules CSV, model HZ2)

Optional environment variables:
  WORK_ROOT
  DIG_DIR, PYTHON_BIN, QSUB_BIN
  PSYCHENCODE_OUT_ROOT, QSUB_LOG_ROOT, PSYCHENCODE_WORKLIST
  PSYCHENCODE_ARRAY_MEMORY, PSYCHENCODE_ARRAY_WALLTIME
  DESCRIPTION_TEMPLATE_TSV
  PROVENANCE_MIRROR_LOCAL_PREFIX, PROVENANCE_MIRROR_REMOTE_PREFIX
  LOCAL_INPUT_SOURCE_MAP_TSV

Notes:
  - Use --submit to submit the qsub array.
  - Add --write_model_only to write only geneset.model.json sidecars.
  - Add --refresh_metadata_and_provenance to patch metadata descriptions, rewrite
    provenance, and populate GMT descriptions for each selected model output.
  - When run inside a qsub array task, it auto-detects the task context and
    runs the assigned workload row.
  - No filters: one array covering all enabled PsychENCODE models.
  - --model_group currently supports only HZ.
  - --model_id submits an array for the selected model(s).
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

absolute_path() {
  local path="$1"
  if [[ "${path}" == /* ]]; then
    printf '%s\n' "${path}"
  else
    printf '%s/%s\n' "$(pwd)" "${path}"
  fi
}

canonicalize_model_group() {
  case "$1" in
    HZ|released_dex|released_modules) printf '%s\n' "HZ" ;;
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
      if ($family_col == "released_dex" || $family_col == "released_modules") print "HZ"
      exit
    }
  ' "${PSYCHENCODE_MODEL_LIST}"
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
      echo "Model not found in PsychENCODE model list: ${requested_model_id}" >&2
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
          echo "Unsupported PsychENCODE model group: $2" >&2
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

input_csv_for_model() {
  local model_id="$1"
  case "${model_id}" in
    HZ1) printf '%s\n' "${PSYCHENCODE_DEX_CSV}" ;;
    HZ2) printf '%s\n' "${PSYCHENCODE_MODULES_CSV}" ;;
    *) return 1 ;;
  esac
}

prepare_common() {
  mkdir -p "${WORK_ROOT}" "${QSUB_LOG_ROOT}"
  require_dir "${DIG_DIR}"

  require_file "${PSYCHENCODE_MODEL_LIST}"
  require_file "${PSYCHENCODE_MODEL_MANIFEST}"
  if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    require_file "${DESCRIPTION_TEMPLATE_TSV}"
  else
    require_var PSYCHENCODE_DEX_CSV
    require_var PSYCHENCODE_MODULES_CSV
    require_file "${PSYCHENCODE_DEX_CSV}"
    require_file "${PSYCHENCODE_MODULES_CSV}"
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
        if ($family_col == "released_dex" || $family_col == "released_modules") group = "HZ"
        if (group == "") next
        if (filter_group != "" && group != filter_group) next
        if (filter_models != "" && !($model_id_col in requested_model_lookup)) next
        task_id += 1
        printf "%d\t%s\t%s\n", task_id, group, $model_id_col
      }
    ' "${PSYCHENCODE_MODEL_LIST}"
  } > "${PSYCHENCODE_WORKLIST}"
}

filter_refresh_existing_worklist() {
  [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]] || return 0
  local filtered_worklist kept
  filtered_worklist="$(mktemp)"
  head -n 1 "${PSYCHENCODE_WORKLIST}" > "${filtered_worklist}"
  kept=0
  while IFS= read -r row; do
    [[ -n "${row}" ]] || continue
    local model_id suffix model_dir
    IFS=$'\t' read -r _task_id _model_group model_id <<< "${row}"
    suffix="${row#*$'\t'}"
    model_dir="${PSYCHENCODE_OUT_ROOT}/genesets/all_signatures/models/${model_id}"
    if [[ -d "${model_dir}/extractor" ]]; then
      kept=$((kept + 1))
      printf "%d\t%s\n" "${kept}" "${suffix}" >> "${filtered_worklist}"
    fi
  done < <(tail -n +2 "${PSYCHENCODE_WORKLIST}")
  mv "${filtered_worklist}" "${PSYCHENCODE_WORKLIST}"
  if [[ ${kept} -le 0 ]]; then
    echo "No PsychENCODE refresh tasks selected after excluding missing outputs." >&2
    exit 1
  fi
}

worklist_task_count() {
  awk 'NR > 1 { n += 1 } END { print n + 0 }' "${PSYCHENCODE_WORKLIST}"
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

  IFS=$'\t' read -r _task_id model_group model_id < <(awk -F $'\t' -v task_id="${task_id}" 'NR > 1 && $1 == task_id { print $0; exit }' "${PSYCHENCODE_WORKLIST}")
  if [[ -z "${model_id:-}" ]]; then
    echo "No PsychENCODE worklist row found for task_id=${task_id}" >&2
    exit 1
  fi

  local src_root
  local cmd input_csv
  src_root="${REPO_ROOT}/geneset-extractor-dev/PsychENCODE/src"

  build_model_only_cmd() {
    input_csv="$(input_csv_for_model "${model_id}")" || {
      echo "Unsupported PsychENCODE model for model-only mode: ${model_id}" >&2
      exit 1
    }
    cmd=(
      "${PYTHON_BIN}"
      "${src_root}/run_psychencode_hz_model.py"
      "--model_id" "${model_id}"
      "--run_root" "${PSYCHENCODE_OUT_ROOT}/genesets/all_signatures/models"
      "--python_bin" "${PYTHON_BIN}"
      "--dig_dir" "${DIG_DIR}"
      "--input_csv" "${input_csv}"
      "--model_manifest" "${PSYCHENCODE_MODEL_MANIFEST}"
      "--write_model_only"
    )
  }
  if [[ ${WRITE_MODEL_ONLY} -eq 1 ]]; then
    build_model_only_cmd
  elif [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    cmd=(
      bash "${REPO_ROOT}/geneset-extractor-dev/run/refresh_model_metadata_and_provenance.sh"
      --model_id "${model_id}"
      --model_dir "${PSYCHENCODE_OUT_ROOT}/genesets/all_signatures/models/${model_id}"
      --description_template_tsv "${DESCRIPTION_TEMPLATE_TSV}"
      --python_bin "${PYTHON_BIN}"
    )
  else
    input_csv="$(input_csv_for_model "${model_id}")" || {
      echo "Unsupported PsychENCODE model: ${model_id}" >&2
      exit 1
    }
    cmd=(
      "${PYTHON_BIN}"
      "${src_root}/build_psychencode_genesets.py"
      "--models" "${model_id}"
      "--python_bin" "${PYTHON_BIN}"
      "--dig_dir" "${DIG_DIR}"
      "--model_list" "${PSYCHENCODE_MODEL_LIST}"
      "--model_manifest" "${PSYCHENCODE_MODEL_MANIFEST}"
      "--out_root" "${PSYCHENCODE_OUT_ROOT}"
      "--overwrite"
      "--dex_csv" "${PSYCHENCODE_DEX_CSV}"
      "--modules_csv" "${PSYCHENCODE_MODULES_CSV}"
    )
  fi
  if [[ -n "${PROVENANCE_MIRROR_LOCAL_PREFIX:-}" ]]; then
    cmd+=(--provenance_mirror_local_prefix "${PROVENANCE_MIRROR_LOCAL_PREFIX}")
  fi
  if [[ -n "${PROVENANCE_MIRROR_REMOTE_PREFIX:-}" ]]; then
    cmd+=(--provenance_mirror_remote_prefix "${PROVENANCE_MIRROR_REMOTE_PREFIX}")
  fi
  if [[ -n "${LOCAL_INPUT_SOURCE_MAP_TSV:-}" ]]; then
    cmd+=(--local_input_source_map_tsv "${LOCAL_INPUT_SOURCE_MAP_TSV}")
  fi
  printf '$'
  printf ' %q' "${cmd[@]}"
  printf '\n'
  "${cmd[@]}"
}

submit_array() {
  write_worklist
  filter_refresh_existing_worklist
  local task_count
  task_count="$(worklist_task_count)"
  if [[ "${task_count}" -le 0 ]]; then
    echo "No PsychENCODE tasks selected." >&2
    exit 1
  fi

  "${QSUB_BIN}" \
    -N "psychencode_all_models" \
    -t "1-${task_count}" \
    -o "${QSUB_LOG_ROOT}/psychencode.\$TASK_ID.out" \
    -e "${QSUB_LOG_ROOT}/psychencode.\$TASK_ID.err" \
    -l "h_vmem=${PSYCHENCODE_ARRAY_MEMORY},h_rt=${PSYCHENCODE_ARRAY_WALLTIME}" \
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},PSYCHENCODE_WORKLIST=${PSYCHENCODE_WORKLIST},PSYCHENCODE_OUT_ROOT=${PSYCHENCODE_OUT_ROOT},PSYCHENCODE_MODEL_LIST=${PSYCHENCODE_MODEL_LIST},PSYCHENCODE_MODEL_MANIFEST=${PSYCHENCODE_MODEL_MANIFEST},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},WRITE_MODEL_ONLY=${WRITE_MODEL_ONLY},REFRESH_METADATA_AND_PROVENANCE=${REFRESH_METADATA_AND_PROVENANCE},DESCRIPTION_TEMPLATE_TSV=${DESCRIPTION_TEMPLATE_TSV},PROVENANCE_MIRROR_LOCAL_PREFIX=${PROVENANCE_MIRROR_LOCAL_PREFIX},PROVENANCE_MIRROR_REMOTE_PREFIX=${PROVENANCE_MIRROR_REMOTE_PREFIX},LOCAL_INPUT_SOURCE_MAP_TSV=${LOCAL_INPUT_SOURCE_MAP_TSV},PSYCHENCODE_DEX_CSV=${PSYCHENCODE_DEX_CSV},PSYCHENCODE_MODULES_CSV=${PSYCHENCODE_MODULES_CSV}" \
    "${REPO_ROOT}/geneset-extractor-dev/run/submit_psychencode_models_cluster.sh"
}

main() {
  WORK_ROOT="$(absolute_path "${WORK_ROOT}")"
  PSYCHENCODE_OUT_ROOT="$(absolute_path "${PSYCHENCODE_OUT_ROOT}")"
  QSUB_LOG_ROOT="$(absolute_path "${QSUB_LOG_ROOT}")"
  PSYCHENCODE_WORKLIST="$(absolute_path "${PSYCHENCODE_WORKLIST}")"

  if [[ $# -eq 0 ]] && task_id_from_env >/dev/null 2>&1; then
    prepare_common
    run_worker
  else
    parse_cli "$@"
    prepare_common
    submit_array
  fi
}

main "$@"
