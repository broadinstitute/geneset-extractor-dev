#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORK_ROOT="${WORK_ROOT:-$(pwd)}"

HUBMAP_CONFIG_ROOT="${HUBMAP_CONFIG_ROOT:-${REPO_ROOT}/geneset-extractor-dev/HuBMAP/planning}"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"

HUBMAP_MODEL_LIST="${HUBMAP_MODEL_LIST:-${HUBMAP_CONFIG_ROOT}/model_list.tsv}"
HUBMAP_MODEL_MANIFEST="${HUBMAP_MODEL_MANIFEST:-${HUBMAP_CONFIG_ROOT}/model_manifest.tsv}"

HUBMAP_OUT_ROOT="${HUBMAP_OUT_ROOT:-${WORK_ROOT}/hubmap_all_models}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_hubmap}"
HUBMAP_WORKLIST="${HUBMAP_WORKLIST:-${WORK_ROOT}/hubmap_qsub_worklist.tsv}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
QSUB_BIN="${QSUB_BIN:-qsub}"

HUBMAP_ARRAY_MEMORY="${HUBMAP_ARRAY_MEMORY:-16G}"
HUBMAP_ARRAY_WALLTIME="${HUBMAP_ARRAY_WALLTIME:-24:00:00}"
SUBMIT_MODE=0
FILTER_MODEL_GROUP=""
FILTER_MODEL_ID=""

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_hubmap_models_cluster.sh --submit [--model_group HZ] [--model_id MODEL]
  ./geneset-extractor-dev/run/submit_hubmap_models_cluster.sh --help

Required environment variables:
  HUBMAP_HUMAN_GENE_INFO
  HUBMAP_RAW_ASCTB_DIR

Optional environment variables:
  HUBMAP_INPUT_MATRIX
  HUBMAP_ASCTB_DIR
  WORK_ROOT
  DIG_DIR, PYTHON_BIN, QSUB_BIN
  HUBMAP_OUT_ROOT, QSUB_LOG_ROOT, HUBMAP_WORKLIST
  HUBMAP_ARRAY_MEMORY, HUBMAP_ARRAY_WALLTIME

Notes:
  - If HUBMAP_INPUT_MATRIX is omitted and both HZ1 and HZ2 are selected,
    the script submits HZ1 first and HZ2 with a hold dependency on HZ1.
  - If HUBMAP_INPUT_MATRIX is omitted and only HZ2 is selected, an existing
    HZ1 workflow matrix must already exist under HUBMAP_OUT_ROOT.
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
    HZ|hz_released_asctb) printf '%s\n' "HZ" ;;
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
      if ($family_col == "hz_released_asctb") print "HZ"
      exit
    }
  ' "${HUBMAP_MODEL_LIST}"
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
          echo "Unsupported HuBMAP model group: $2" >&2
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
      echo "Model not found in HuBMAP model list: ${FILTER_MODEL_ID}" >&2
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

  require_var HUBMAP_HUMAN_GENE_INFO
  require_var HUBMAP_RAW_ASCTB_DIR

  require_file "${HUBMAP_MODEL_LIST}"
  require_file "${HUBMAP_MODEL_MANIFEST}"
  require_file "${HUBMAP_HUMAN_GENE_INFO}"
  require_dir "${HUBMAP_RAW_ASCTB_DIR}"
  if [[ -n "${HUBMAP_INPUT_MATRIX:-}" ]]; then
    require_file "${HUBMAP_INPUT_MATRIX}"
  fi
  if [[ -n "${HUBMAP_ASCTB_DIR:-}" ]]; then
    require_dir "${HUBMAP_ASCTB_DIR}"
  fi
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
        if ($family_col == "hz_released_asctb") group = "HZ"
        if (group == "") next
        if (filter_group != "" && group != filter_group) next
        if (filter_model != "" && $model_id_col != filter_model) next
        task_id += 1
        printf "%d\t%s\t%s\n", task_id, group, $model_id_col
      }
    ' "${HUBMAP_MODEL_LIST}"
  } > "${HUBMAP_WORKLIST}"
}

worklist_task_count() {
  awk 'NR > 1 { n += 1 } END { print n + 0 }' "${HUBMAP_WORKLIST}"
}

worklist_has_model() {
  local worklist_path="$1"
  local model_id="$2"
  awk -F $'\t' -v model_id="${model_id}" 'NR > 1 && $3 == model_id { found = 1; exit } END { exit(found ? 0 : 1) }' "${worklist_path}"
}

filter_worklist_for_model() {
  local source_path="$1"
  local model_id="$2"
  local dest_path="$3"
  awk -F $'\t' -v model_id="${model_id}" '
    BEGIN { OFS = "\t" }
    NR == 1 { print $1, $2, $3; next }
    $3 == model_id {
      task += 1
      print task, $2, $3
    }
  ' "${source_path}" > "${dest_path}"
}

existing_hz1_matrix_path() {
  printf '%s\n' "${HUBMAP_OUT_ROOT}/genesets/all_signatures/models/HZ1/workflow/gene_attribute_matrix.txt.gz"
}

extract_qsub_job_id() {
  local qsub_output="$1"
  printf '%s\n' "${qsub_output}" | grep -Eo '[0-9]+' | head -n 1
}

submit_one_array() {
  local worklist_path="$1"
  local job_name="$2"
  local hold_jid="${3:-}"
  local task_count
  task_count="$(awk 'NR > 1 { n += 1 } END { print n + 0 }' "${worklist_path}")"
  if [[ "${task_count}" -le 0 ]]; then
    echo ""
    return 0
  fi

  local -a qsub_cmd=(
    "${QSUB_BIN}"
    -N "${job_name}"
    -t "1-${task_count}"
    -o "${QSUB_LOG_ROOT}/hubmap.\$TASK_ID.out"
    -e "${QSUB_LOG_ROOT}/hubmap.\$TASK_ID.err"
    -l "h_vmem=${HUBMAP_ARRAY_MEMORY},h_rt=${HUBMAP_ARRAY_WALLTIME}"
  )
  if [[ -n "${hold_jid}" ]]; then
    qsub_cmd+=(-hold_jid "${hold_jid}")
  fi
  qsub_cmd+=(
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},HUBMAP_WORKLIST=${worklist_path},HUBMAP_OUT_ROOT=${HUBMAP_OUT_ROOT},HUBMAP_MODEL_LIST=${HUBMAP_MODEL_LIST},HUBMAP_MODEL_MANIFEST=${HUBMAP_MODEL_MANIFEST},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},HUBMAP_HUMAN_GENE_INFO=${HUBMAP_HUMAN_GENE_INFO},HUBMAP_RAW_ASCTB_DIR=${HUBMAP_RAW_ASCTB_DIR},HUBMAP_INPUT_MATRIX=${HUBMAP_INPUT_MATRIX:-},HUBMAP_ASCTB_DIR=${HUBMAP_ASCTB_DIR:-}"
    "${REPO_ROOT}/geneset-extractor-dev/run/submit_hubmap_models_cluster.sh"
  )

  local qsub_output job_id
  qsub_output="$("${qsub_cmd[@]}")"
  printf '%s\n' "${qsub_output}"
  job_id="$(extract_qsub_job_id "${qsub_output}")"
  if [[ -z "${job_id}" ]]; then
    echo "Failed to parse qsub job id from submission output: ${qsub_output}" >&2
    exit 1
  fi
  printf '%s\n' "${job_id}"
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

  IFS=$'\t' read -r _task_id model_group model_id < <(awk -F $'\t' -v task_id="${task_id}" 'NR > 1 && $1 == task_id { print $0; exit }' "${HUBMAP_WORKLIST}")
  if [[ -z "${model_id:-}" ]]; then
    echo "No HuBMAP worklist row found for task_id=${task_id}" >&2
    exit 1
  fi

  local src_root
  src_root="${REPO_ROOT}/geneset-extractor-dev/HuBMAP/src"

  local cmd=(
    "${PYTHON_BIN}"
    "${src_root}/build_hubmap_genesets.py"
    "--models" "${model_id}"
    "--python_bin" "${PYTHON_BIN}"
    "--human_gene_info" "${HUBMAP_HUMAN_GENE_INFO}"
    "--raw_asctb_dir" "${HUBMAP_RAW_ASCTB_DIR}"
    "--dig_dir" "${DIG_DIR}"
    "--model_list" "${HUBMAP_MODEL_LIST}"
    "--model_manifest" "${HUBMAP_MODEL_MANIFEST}"
    "--out_root" "${HUBMAP_OUT_ROOT}"
    "--overwrite"
  )
  if [[ -n "${HUBMAP_INPUT_MATRIX:-}" ]]; then
    cmd+=(--input_matrix "${HUBMAP_INPUT_MATRIX}")
  fi
  if [[ -n "${HUBMAP_ASCTB_DIR:-}" ]]; then
    cmd+=(--asctb_dir "${HUBMAP_ASCTB_DIR}")
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

submit_array() {
  write_worklist
  local task_count
  task_count="$(worklist_task_count)"
  if [[ "${task_count}" -le 0 ]]; then
    echo "No HuBMAP tasks selected." >&2
    exit 1
  fi
  if [[ -n "${HUBMAP_INPUT_MATRIX:-}" ]]; then
    submit_one_array "${HUBMAP_WORKLIST}" "hubmap_all_models" >/dev/null
    return
  fi

  local has_hz1 has_hz2 existing_matrix
  has_hz1=0
  has_hz2=0
  worklist_has_model "${HUBMAP_WORKLIST}" "HZ1" && has_hz1=1 || true
  worklist_has_model "${HUBMAP_WORKLIST}" "HZ2" && has_hz2=1 || true
  existing_matrix="$(existing_hz1_matrix_path)"

  if [[ "${has_hz2}" -eq 1 && "${has_hz1}" -eq 0 && ! -f "${existing_matrix}" ]]; then
    echo "HZ2 requires HUBMAP_INPUT_MATRIX or an existing HZ1 workflow matrix at ${existing_matrix}" >&2
    exit 1
  fi

  if [[ "${has_hz1}" -eq 1 && "${has_hz2}" -eq 1 ]]; then
    local hz1_worklist hz2_worklist hz1_job_id
    hz1_worklist="${HUBMAP_WORKLIST%.tsv}.hz1.tsv"
    hz2_worklist="${HUBMAP_WORKLIST%.tsv}.hz2.tsv"
    filter_worklist_for_model "${HUBMAP_WORKLIST}" "HZ1" "${hz1_worklist}"
    filter_worklist_for_model "${HUBMAP_WORKLIST}" "HZ2" "${hz2_worklist}"
    hz1_job_id="$(submit_one_array "${hz1_worklist}" "hubmap_hz1")"
    submit_one_array "${hz2_worklist}" "hubmap_hz2" "${hz1_job_id}" >/dev/null
    return
  fi

  submit_one_array "${HUBMAP_WORKLIST}" "hubmap_all_models" >/dev/null
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
