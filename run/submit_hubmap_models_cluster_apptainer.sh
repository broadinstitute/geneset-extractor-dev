#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPO_ROOT="${REPO_ROOT:-${DEFAULT_REPO_ROOT}}"
SELF_PATH="${REPO_ROOT}/geneset-extractor-dev/run/submit_hubmap_models_cluster_apptainer.sh"
WORK_ROOT="${WORK_ROOT:-$(pwd)}"

HUBMAP_CONFIG_ROOT="${HUBMAP_CONFIG_ROOT:-${REPO_ROOT}/geneset-extractor-dev/HuBMAP/config}"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"

HUBMAP_MODEL_LIST="${HUBMAP_MODEL_LIST:-${HUBMAP_CONFIG_ROOT}/model_list.tsv}"
HUBMAP_MODEL_MANIFEST="${HUBMAP_MODEL_MANIFEST:-${HUBMAP_CONFIG_ROOT}/model_manifest.tsv}"

HUBMAP_OUT_ROOT="${HUBMAP_OUT_ROOT:-${WORK_ROOT}/hubmap_all_models}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_hubmap}"
HUBMAP_WORKLIST="${HUBMAP_WORKLIST:-${WORK_ROOT}/hubmap_qsub_worklist.tsv}"

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

HUBMAP_ARRAY_MEMORY="${HUBMAP_ARRAY_MEMORY:-16G}"
HUBMAP_ARRAY_WALLTIME="${HUBMAP_ARRAY_WALLTIME:-24:00:00}"
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
  ./geneset-extractor-dev/run/submit_hubmap_models_cluster_apptainer.sh --submit [--write_model_only|--refresh_metadata_and_provenance] [--model_group HZ] [--model_id MODEL[,MODEL...]]
  ./geneset-extractor-dev/run/submit_hubmap_models_cluster_apptainer.sh --help

Required environment variables:
  APPTAINER_IMAGE
  HUBMAP_HUMAN_GENE_INFO
  HUBMAP_RAW_ASCTB_DIR

Optional environment variables:
  HUBMAP_INPUT_MATRIX
  HUBMAP_ASCTB_DIR
  WORK_ROOT
  DIG_DIR, PYTHON_BIN, QSUB_BIN
  APPTAINER_BIN, APPTAINER_EXTRA_ARGS
  APPTAINER_PYTHON_BIN
  HUBMAP_OUT_ROOT, QSUB_LOG_ROOT, HUBMAP_WORKLIST
  HUBMAP_ARRAY_MEMORY, HUBMAP_ARRAY_WALLTIME
  DESCRIPTION_TEMPLATE_TSV
  PROVENANCE_MIRROR_LOCAL_PREFIX, PROVENANCE_MIRROR_REMOTE_PREFIX
  LOCAL_INPUT_SOURCE_MAP_TSV

Notes:
  - Add --write_model_only to write only geneset.model.json sidecars.
  - Add --refresh_metadata_and_provenance to patch metadata descriptions and
    rebuild provenance for each selected model output.
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
      echo "Model not found in HuBMAP model list: ${requested_model_id}" >&2
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
          echo "Unsupported HuBMAP model group: $2" >&2
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
  WORK_ROOT="$(absolute_path "${WORK_ROOT}")"
  HUBMAP_OUT_ROOT="$(absolute_path "${HUBMAP_OUT_ROOT}")"
  QSUB_LOG_ROOT="$(absolute_path "${QSUB_LOG_ROOT}")"
  HUBMAP_WORKLIST="$(absolute_path "${HUBMAP_WORKLIST}")"
  mkdir -p "${WORK_ROOT}" "${QSUB_LOG_ROOT}"
  require_dir "${DIG_DIR}"

  if [[ -z "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
    require_var APPTAINER_IMAGE
    require_file "${APPTAINER_IMAGE}"
  fi
  require_file "${HUBMAP_MODEL_LIST}"
  require_file "${HUBMAP_MODEL_MANIFEST}"
  if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    require_file "${DESCRIPTION_TEMPLATE_TSV}"
  else
    require_var HUBMAP_HUMAN_GENE_INFO
    require_file "${HUBMAP_HUMAN_GENE_INFO}"
  fi
  if [[ ${WRITE_MODEL_ONLY} -ne 1 && ${REFRESH_METADATA_AND_PROVENANCE} -ne 1 ]]; then
    require_var HUBMAP_RAW_ASCTB_DIR
    require_dir "${HUBMAP_RAW_ASCTB_DIR}"
  fi
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
        if ($family_col == "hz_released_asctb") group = "HZ"
        if (group == "") next
        if (filter_group != "" && group != filter_group) next
        if (filter_models != "" && !($model_id_col in requested_model_lookup)) next
        task_id += 1
        printf "%d\t%s\t%s\n", task_id, group, $model_id_col
      }
    ' "${HUBMAP_MODEL_LIST}"
  } > "${HUBMAP_WORKLIST}"
}

filter_refresh_existing_worklist() {
  [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]] || return 0
  local filtered_worklist kept
  filtered_worklist="$(mktemp)"
  head -n 1 "${HUBMAP_WORKLIST}" > "${filtered_worklist}"
  kept=0
  while IFS= read -r row; do
    [[ -n "${row}" ]] || continue
    local model_id suffix model_dir
    IFS=$'\t' read -r _task_id _model_group model_id <<< "${row}"
    suffix="${row#*$'\t'}"
    model_dir="${HUBMAP_OUT_ROOT}/genesets/all_signatures/models/${model_id}"
    if [[ -d "${model_dir}/extractor" ]]; then
      kept=$((kept + 1))
      printf "%d\t%s\n" "${kept}" "${suffix}" >> "${filtered_worklist}"
    fi
  done < <(tail -n +2 "${HUBMAP_WORKLIST}")
  mv "${filtered_worklist}" "${HUBMAP_WORKLIST}"
  if [[ ${kept} -le 0 ]]; then
    echo "No HuBMAP refresh tasks selected after excluding missing outputs." >&2
    exit 1
  fi
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
  IFS=$'\t' read -r _task_id model_group model_id < <(awk -F $'\t' -v task_id="${task_id}" 'NR > 1 && $1 == task_id { print $0; exit }' "${HUBMAP_WORKLIST}")
  if [[ -z "${model_id:-}" ]]; then
    echo "No HuBMAP worklist row found for task_id=${task_id}" >&2
    exit 1
  fi

  local src_root
  src_root="${REPO_ROOT}/geneset-extractor-dev/HuBMAP/src"
  local cmd
  build_model_only_cmd() {
    cmd=(
      "${PYTHON_BIN}"
      "${src_root}/run_hubmap_hz_model.py"
      "--model_id" "${model_id}"
      "--run_root" "${HUBMAP_OUT_ROOT}/genesets/all_signatures/models"
      "--python_bin" "${PYTHON_BIN}"
      "--dig_dir" "${DIG_DIR}"
      "--human_gene_info" "${HUBMAP_HUMAN_GENE_INFO}"
      "--model_manifest" "${HUBMAP_MODEL_MANIFEST}"
      "--write_model_only"
    )
  }
  if [[ ${WRITE_MODEL_ONLY} -eq 1 ]]; then
    build_model_only_cmd
  elif [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    build_model_only_cmd
    printf '$'
    printf ' %q' "${cmd[@]}"
    printf '\n'
    "${cmd[@]}"
    cmd=(
      bash "${REPO_ROOT}/geneset-extractor-dev/run/refresh_model_metadata_and_provenance.sh"
      --model_id "${model_id}"
      --model_dir "${HUBMAP_OUT_ROOT}/genesets/all_signatures/models/${model_id}"
      --description_template_tsv "${DESCRIPTION_TEMPLATE_TSV}"
      --python_bin "${PYTHON_BIN}"
    )
  else
    cmd=(
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

run_outer_worker() {
  local binds bind_csv
  binds="$(
    {
      append_bind_path "${REPO_ROOT}"
      append_bind_path "${WORK_ROOT}"
      append_bind_path "${DIG_DIR}"
      append_bind_path "${HUBMAP_MODEL_LIST}"
      append_bind_path "${HUBMAP_MODEL_MANIFEST}"
      append_bind_path "${DESCRIPTION_TEMPLATE_TSV:-}"
      append_bind_path "${PROVENANCE_MIRROR_LOCAL_PREFIX:-}"
      append_bind_path "${LOCAL_INPUT_SOURCE_MAP_TSV:-}"
      append_bind_path "${HUBMAP_HUMAN_GENE_INFO:-}"
      append_bind_path "${HUBMAP_RAW_ASCTB_DIR}"
      append_bind_path "${HUBMAP_INPUT_MATRIX:-}"
      append_bind_path "${HUBMAP_ASCTB_DIR:-}"
    } | sort -u
  )"
  bind_csv="$(printf '%s\n' "${binds}" | paste -sd, -)"

  env \
    APPTAINERENV_GENESET_EXTRACTORS_IN_APPTAINER=1 \
    APPTAINERENV_PBS_ARRAYID="${PBS_ARRAYID:-}" \
    APPTAINERENV_SGE_TASK_ID="${SGE_TASK_ID:-}" \
    APPTAINERENV_REPO_ROOT="${REPO_ROOT}" \
    APPTAINERENV_WORK_ROOT="${WORK_ROOT}" \
    APPTAINERENV_HUBMAP_WORKLIST="${HUBMAP_WORKLIST}" \
    APPTAINERENV_HUBMAP_OUT_ROOT="${HUBMAP_OUT_ROOT}" \
    APPTAINERENV_HUBMAP_MODEL_LIST="${HUBMAP_MODEL_LIST}" \
    APPTAINERENV_HUBMAP_MODEL_MANIFEST="${HUBMAP_MODEL_MANIFEST}" \
    APPTAINERENV_DIG_DIR="${DIG_DIR}" \
    APPTAINERENV_PYTHON_BIN="${PYTHON_BIN}" \
    APPTAINERENV_APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN}" \
    APPTAINERENV_WRITE_MODEL_ONLY="${WRITE_MODEL_ONLY}" \
    APPTAINERENV_REFRESH_METADATA_AND_PROVENANCE="${REFRESH_METADATA_AND_PROVENANCE}" \
    APPTAINERENV_DESCRIPTION_TEMPLATE_TSV="${DESCRIPTION_TEMPLATE_TSV}" \
    APPTAINERENV_PROVENANCE_MIRROR_LOCAL_PREFIX="${PROVENANCE_MIRROR_LOCAL_PREFIX}" \
    APPTAINERENV_PROVENANCE_MIRROR_REMOTE_PREFIX="${PROVENANCE_MIRROR_REMOTE_PREFIX}" \
    APPTAINERENV_LOCAL_INPUT_SOURCE_MAP_TSV="${LOCAL_INPUT_SOURCE_MAP_TSV}" \
    APPTAINERENV_HUBMAP_HUMAN_GENE_INFO="${HUBMAP_HUMAN_GENE_INFO:-}" \
    APPTAINERENV_HUBMAP_RAW_ASCTB_DIR="${HUBMAP_RAW_ASCTB_DIR}" \
    APPTAINERENV_HUBMAP_INPUT_MATRIX="${HUBMAP_INPUT_MATRIX:-}" \
    APPTAINERENV_HUBMAP_ASCTB_DIR="${HUBMAP_ASCTB_DIR:-}" \
    "${APPTAINER_BIN}" exec \
      --bind "${bind_csv}" \
      ${APPTAINER_EXTRA_ARGS} \
      "${APPTAINER_IMAGE}" \
      bash "${SELF_PATH}"
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
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},HUBMAP_WORKLIST=${worklist_path},HUBMAP_OUT_ROOT=${HUBMAP_OUT_ROOT},HUBMAP_MODEL_LIST=${HUBMAP_MODEL_LIST},HUBMAP_MODEL_MANIFEST=${HUBMAP_MODEL_MANIFEST},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},APPTAINER_BIN=${APPTAINER_BIN},APPTAINER_IMAGE=${APPTAINER_IMAGE},APPTAINER_EXTRA_ARGS=${APPTAINER_EXTRA_ARGS},APPTAINER_PYTHON_BIN=${APPTAINER_PYTHON_BIN},WRITE_MODEL_ONLY=${WRITE_MODEL_ONLY},REFRESH_METADATA_AND_PROVENANCE=${REFRESH_METADATA_AND_PROVENANCE},DESCRIPTION_TEMPLATE_TSV=${DESCRIPTION_TEMPLATE_TSV},PROVENANCE_MIRROR_LOCAL_PREFIX=${PROVENANCE_MIRROR_LOCAL_PREFIX},PROVENANCE_MIRROR_REMOTE_PREFIX=${PROVENANCE_MIRROR_REMOTE_PREFIX},LOCAL_INPUT_SOURCE_MAP_TSV=${LOCAL_INPUT_SOURCE_MAP_TSV},HUBMAP_HUMAN_GENE_INFO=${HUBMAP_HUMAN_GENE_INFO:-},HUBMAP_RAW_ASCTB_DIR=${HUBMAP_RAW_ASCTB_DIR:-},HUBMAP_INPUT_MATRIX=${HUBMAP_INPUT_MATRIX:-},HUBMAP_ASCTB_DIR=${HUBMAP_ASCTB_DIR:-}"
    "${SELF_PATH}"
  )

  local qsub_output job_id
  printf '$' >&2
  printf ' %q' "${qsub_cmd[@]}" >&2
  printf '\n' >&2
  if ! qsub_output="$("${qsub_cmd[@]}" 2>&1)"; then
    printf '%s\n' "${qsub_output}" >&2
    echo "HuBMAP qsub submission failed." >&2
    exit 1
  fi
  printf '%s\n' "${qsub_output}" >&2
  job_id="$(extract_qsub_job_id "${qsub_output}")"
  if [[ -z "${job_id}" ]]; then
    echo "Failed to parse qsub job id from submission output: ${qsub_output}" >&2
    exit 1
  fi
  printf '%s\n' "${job_id}"
}

submit_array() {
  write_worklist
  filter_refresh_existing_worklist
  local task_count
  local job_id
  task_count="$(worklist_task_count)"
  if [[ "${task_count}" -le 0 ]]; then
    echo "No HuBMAP tasks selected." >&2
    exit 1
  fi

  if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    job_id="$(submit_one_array "${HUBMAP_WORKLIST}" "hubmap_all_models_apptainer")"
    printf 'Submitted HuBMAP array job %s\n' "${job_id}" >&2
    return
  fi

  if [[ ${WRITE_MODEL_ONLY} -eq 1 ]]; then
    job_id="$(submit_one_array "${HUBMAP_WORKLIST}" "hubmap_all_models_apptainer")"
    printf 'Submitted HuBMAP array job %s\n' "${job_id}" >&2
    return
  fi

  if [[ -n "${HUBMAP_INPUT_MATRIX:-}" ]]; then
    job_id="$(submit_one_array "${HUBMAP_WORKLIST}" "hubmap_all_models_apptainer")"
    printf 'Submitted HuBMAP array job %s\n' "${job_id}" >&2
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
    hz1_job_id="$(submit_one_array "${hz1_worklist}" "hubmap_hz1_apptainer")"
    printf 'Submitted HuBMAP array job %s\n' "${hz1_job_id}" >&2
    job_id="$(submit_one_array "${hz2_worklist}" "hubmap_hz2_apptainer" "${hz1_job_id}")"
    printf 'Submitted HuBMAP array job %s\n' "${job_id}" >&2
    return
  fi

  job_id="$(submit_one_array "${HUBMAP_WORKLIST}" "hubmap_all_models_apptainer")"
  printf 'Submitted HuBMAP array job %s\n' "${job_id}" >&2
}

main() {
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
